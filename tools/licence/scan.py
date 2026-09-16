#!/usr/bin/env python3
"""Licence firewall scanner. Every mode prints one line per finding and exits 1 on any finding.

Modes (sub-chunk 1.1.2 defined nc and purge-audit; 1.1.3 extended nc and added deps, brand, all):
  nc           No CC BY-NC content under sim/; every file under content/ has a manifest entry
               with a matching hash and an allowlisted licence; the manifest validates against
               tools/provenance/schema.json. CI-safe.
  deps         Every JS (pnpm) and Python (uv) dependency's licence is on the allowlist or
               carries an unexpired waiver in policy.yaml. CI-safe.
  brand        No term from brandlist.txt appears in a tracked or untracked-not-ignored file
               name or text, outside policy exemptions and unexpired path-scoped waivers.
  all          nc + deps + brand, in that order. `make licence` runs this; CI runs the same.
  purge-audit  Manifest equals upstream minus sim/ with matching hashes. Local only (needs the
               upstream clone under refs/).

Policy (allowlist, waivers, scopes) lives in tools/licence/policy.yaml. Waivers expire; an
expired waiver is itself a finding. Output is sorted and deterministic so local and CI runs
are byte-comparable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import importlib.metadata as md
import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
CONTENT = ROOT / "content"
MANIFEST = ROOT / "tools" / "licence" / "nc_purge_manifest.json"
POLICY = ROOT / "tools" / "licence" / "policy.yaml"
BRANDLIST = ROOT / "tools" / "licence" / "brandlist.txt"
SCHEMA = ROOT / "tools" / "provenance" / "schema.json"
CONTENT_MANIFEST = CONTENT / "MANIFEST.json"
SKIP_DIRS = {"node_modules", "dist", ".venv", "__pycache__", ".git"}
NC_STRINGS = ("mobilegym-data", "BY-NC", "NonCommercial", "Non-Commercial")
# The fork NOTICE must preserve upstream's text, which names the data licence we removed.
NC_STRING_EXEMPT = {"sim/NOTICE"}
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".wasm",
    ".mp4",
    ".webm",
    ".mp3",
    ".zip",
    ".gz",
    ".pdf",
    ".lock",
}
HEBREW = "֐-׿"
HEBREW_PREFIXES = (
    "בלהומשכ"  # one attached prefix letter: "in", "to", "the", "and", "from", "that", "as"
)


# ----------------------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Anchored glob: '**' spans directories, '*' does not. 'docs/**' matches only root docs."""
    out = "^"
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        out += "[^/]*" if c == "*" else re.escape(c)
        i += 1
    return re.compile(out + "$")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


def git_files() -> list[str]:
    """Tracked plus untracked-but-not-ignored files, repo-relative, sorted."""
    raw = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return sorted(p for p in raw.split("\0") if p and (ROOT / p).is_file())


def sim_files() -> list[Path]:
    return [
        p for p in SIM.rglob("*") if p.is_file() and not (set(p.relative_to(SIM).parts) & SKIP_DIRS)
    ]


def read_text(path: Path) -> str | None:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_policy() -> dict:
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    assert policy.get("schema_version") == 1, "policy.yaml: unsupported schema_version"
    return policy


def load_manifest() -> dict:
    if not MANIFEST.exists():
        print(f"manifest-missing: {rel(MANIFEST)}")
        sys.exit(1)
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def expired(waiver: dict, label: str, today: dt.date) -> str | None:
    exp = waiver.get("expires")
    if not isinstance(exp, dt.date):
        return f"waiver-missing-expiry: {label}"
    if exp < today:
        return f"waiver-expired[{exp.isoformat()}]: {label}"
    if not waiver.get("reason"):
        return f"waiver-missing-reason: {label}"
    return None


# ----------------------------------------------------------------------------- SPDX
def spdx_allowed(expr: str, allow: set[str]) -> bool:
    """True if the SPDX expression is satisfiable by allowlisted licences.
    OR: any branch; AND: all branches; WITH exception: the base licence. Parentheses honoured."""
    tokens = re.findall(r"\(|\)|\bAND\b|\bOR\b|\bWITH\b|[^\s()]+", expr, flags=re.IGNORECASE)
    pos = 0

    def parse_or() -> bool:
        nonlocal pos
        value = parse_and()
        while pos < len(tokens) and tokens[pos].upper() == "OR":
            pos += 1
            value = parse_and() or value
        return value

    def parse_and() -> bool:
        nonlocal pos
        value = parse_atom()
        while pos < len(tokens) and tokens[pos].upper() == "AND":
            pos += 1
            value = parse_atom() and value
        return value

    def parse_atom() -> bool:
        nonlocal pos
        if pos >= len(tokens):
            return False
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            value = parse_or()
            if pos < len(tokens) and tokens[pos] == ")":
                pos += 1
            return value
        if pos < len(tokens) and tokens[pos].upper() == "WITH":
            pos += 2  # skip the exception; the base licence decides
        return tok.rstrip("+") in allow

    try:
        return parse_or() and pos == len(tokens)
    except IndexError:
        return False


PY_LICENCE_TEXT = {
    "mit license": "MIT",
    "mit": "MIT",
    "apache software license": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "bsd license": "BSD-3-Clause",
    "bsd": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "isc license (iscl)": "ISC",
    "isc": "ISC",
    "python software foundation license": "PSF-2.0",
    "psfl": "PSF-2.0",
    "psf": "PSF-2.0",
    "the unlicense (unlicense)": "Unlicense",
    "cc0 1.0 universal (cc0 1.0) public domain dedication": "CC0-1.0",
}


def python_licence(dist: md.Distribution) -> str | None:
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License ::"):
            key = c.split("::")[-1].strip().lower()
            if key in PY_LICENCE_TEXT:
                return PY_LICENCE_TEXT[key]
    text = (meta.get("License") or "").strip()
    if text:
        first = text.splitlines()[0].strip().lower()
        return PY_LICENCE_TEXT.get(first, text.splitlines()[0].strip()[:40])
    return None


# ----------------------------------------------------------------------------- modes
def mode_nc(policy: dict) -> int:
    findings: list[str] = []
    if not SIM.is_dir():
        print("sim-missing: sim/ does not exist")
        return 1
    manifest = load_manifest()
    for entry in manifest["entries"]:
        target = SIM / entry["path"]
        # A file of ours at a purged path is fine; upstream's bytes at that path are not.
        if target.is_file() and sha256(target) == entry["sha256"]:
            findings.append(f"purged-content-present: sim/{entry['path']}")
    # apps/*/{data,assets} and system/*/assets must not exist. system/*/data may: it holds the
    # Apache-2.0 loader plus our stubs; upstream bytes there are caught above.
    for parent, subs in (("apps", ("data", "assets")), ("system", ("assets",))):
        base = SIM / parent
        if base.is_dir():
            for app in sorted(base.iterdir()):
                for sub in subs:
                    if (app / sub).exists():
                        findings.append(f"nc-dir-present: {rel(app / sub)}")
    for p in sim_files():
        if rel(p) in NC_STRING_EXEMPT:
            continue
        text = read_text(p)
        if text is None:
            continue
        for needle in NC_STRINGS:
            if needle in text:
                findings.append(f"nc-string[{needle}]: {rel(p)}")
                break

    # content/: manifest validates; every asset listed with a matching hash and an allowed licence
    allow = set(policy["licence_allowlist"])
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        cm = json.loads(CONTENT_MANIFEST.read_text(encoding="utf-8"))
        jsonschema.validate(cm, schema)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as e:
        findings.append(f"content-manifest-invalid: {str(e).splitlines()[0][:120]}")
        cm = {"assets": []}
    listed = {a["path"]: a for a in cm["assets"]}
    exempt = policy.get("content_exempt", [])
    on_disk = sorted(
        p.relative_to(CONTENT).as_posix()
        for p in CONTENT.rglob("*")
        if p.is_file() and not matches_any(p.relative_to(CONTENT).as_posix(), exempt)
    )
    for path in on_disk:
        if path not in listed:
            findings.append(f"unlisted-asset: content/{path}")
        elif sha256(CONTENT / path) != listed[path]["sha256"]:
            findings.append(f"asset-hash-mismatch: content/{path}")
    for path, a in sorted(listed.items()):
        if path not in on_disk:
            findings.append(f"orphan-manifest-entry: content/{path}")
        if a["licence"] not in allow or "NC" in a["licence"].upper().split("-"):
            findings.append(f"asset-licence-not-allowed[{a['licence']}]: content/{path}")
    for f in sorted(findings):
        print(f)
    return len(findings)


def mode_deps(policy: dict, today: dt.date) -> int:
    findings: list[str] = []
    allow = set(policy["licence_allowlist"]) - {"proprietary"}
    waivers: dict[tuple[str, str], dict] = {}
    for w in policy.get("dependency_waivers", []):
        label = f"{w.get('ecosystem')}:{w.get('package')} ({w.get('licence')})"
        if problem := expired(w, label, today):
            findings.append(problem)
        else:
            waivers[(w["ecosystem"], w["package"])] = w

    def check(eco: str, name: str, version: str, licence: str | None) -> None:
        if licence is None:
            verdict = "licence-unknown"
        elif spdx_allowed(licence, allow):
            return
        else:
            verdict = f"licence-not-allowed[{licence}]"
        for (weco, wpkg), w in waivers.items():
            if weco == eco and fnmatch.fnmatchcase(name, wpkg):
                if licence is None or w.get("licence") == licence:
                    return
        findings.append(f"{verdict}: {eco}:{name}@{version}")

    # JS: every package pnpm resolved for any workspace project, dev and optional included,
    # link/file installs too. The licence is read from each package's own package.json on disk;
    # `pnpm licenses list` is not used because it silently omits link-installed packages.
    raw = subprocess.run(
        ["pnpm", "ls", "-r", "--depth", "Infinity", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if raw.returncode != 0 or not raw.stdout.strip():
        findings.append("deps-enumeration-failed: pnpm ls")
    else:
        seen: dict[tuple[str, str], str] = {}

        def walk(node: dict) -> None:
            for key in ("dependencies", "devDependencies", "optionalDependencies"):
                for name, dep in (node.get(key) or {}).items():
                    if dep.get("path"):
                        seen[(name, dep.get("version", "?"))] = dep["path"]
                    walk(dep)

        for project in json.loads(raw.stdout):
            walk(project)
        for (name, version), path in sorted(seen.items()):
            pkg_json = Path(path) / "package.json"
            if not Path(path).is_dir():
                # pnpm lists every platform variant of a package but installs only the one for
                # this OS/arch. A directory that does not exist is not installed: nothing of it
                # ships from here, and CI evaluates its own platform's variant the same way.
                continue
            try:
                meta = json.loads(pkg_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                findings.append(f"not-installed: npm:{name}@{version}")
                continue
            lic = meta.get("license")
            if isinstance(lic, dict):
                lic = lic.get("type")
            if not lic and isinstance(meta.get("licenses"), list) and meta["licenses"]:
                lic = " OR ".join(
                    x.get("type", "") if isinstance(x, dict) else str(x) for x in meta["licenses"]
                )
            if not lic and meta.get("private") and (ROOT / "packages") in Path(path).parents:
                continue  # our own private workspace packages carry no licence field
            check("npm", name, version, lic or None)

    # Python: every distribution in the uv environment except our own workspace members
    own = set()
    for member in ("bench", "packages_py/rtl_commerce"):
        text = (ROOT / member / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        if m:
            own.add(m.group(1).lower().replace("_", "-"))
    for dist in md.distributions():
        name = dist.metadata["Name"]
        if name.lower().replace("_", "-") in own:
            continue
        check("pypi", name, dist.metadata["Version"], python_licence(dist))

    for f in sorted(set(findings)):
        print(f)
    return len(set(findings))


def load_brand_terms() -> list[tuple[str, bool]]:
    """(term, ambiguous) pairs. Ambiguous terms start with '~' in brandlist.txt."""
    terms = []
    for line in BRANDLIST.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        terms.append((t.lstrip("~").strip(), t.startswith("~")))
    return terms


def term_regex(term: str, ambiguous: bool = False) -> re.Pattern[str]:
    """Strict terms match in any case. Ambiguous Latin terms (ordinary words such as Next,
    Max, Delta) match only in the brand's own casing or all caps: a lowercase "next" in prose
    is the word, not the retailer. Hebrew has no case, so its ambiguous terms are unchanged."""
    words = [re.escape(w) for w in term.split()]
    body = r"[\s_-]+".join(words)
    if re.search(f"[{HEBREW}]", term):
        return re.compile(f"(?<![{HEBREW}])[{HEBREW_PREFIXES}]?{body}(?![{HEBREW}])")
    if ambiguous:
        upper = r"[\s_-]+".join(re.escape(w.upper()) for w in term.split())
        return re.compile(rf"(?<![A-Za-z0-9])(?:{body}|{upper})(?![A-Za-z0-9])")
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def mode_brand(policy: dict, today: dt.date) -> int:
    findings: list[str] = []
    exempt = policy.get("brand_exempt_paths", [])
    scope = policy.get("brand_content_scope", [])
    waived: dict[str, list[str]] = {}
    for w in policy.get("brand_waivers", []):
        label = f"brand term {w.get('term')!r}"
        if problem := expired(w, label, today):
            findings.append(problem)
        else:
            waived[w["term"].lower()] = w.get("paths", [])
    terms = [(t, amb, term_regex(t, amb)) for t, amb in load_brand_terms()]

    def is_waived(term: str, path: str) -> bool:
        # a waiver with term "*" covers every term inside its paths (reference apps until 3.3.1)
        return matches_any(path, waived.get(term.lower(), [])) or matches_any(
            path, waived.get("*", [])
        )

    for path in git_files():
        if matches_any(path, exempt):
            continue
        in_scope = matches_any(path, scope)
        # file name: every tier, every path
        for t, _amb, rx in terms:
            if rx.search(path.rsplit("/", 1)[-1]) and not is_waived(t, path):
                findings.append(f"brand-filename[{t}]: {path}")
        text = read_text(ROOT / path)
        if text is None:
            continue
        for t, amb, rx in terms:
            if amb and not in_scope:
                continue
            m = rx.search(text)
            if m and not is_waived(t, path):
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"brand[{t}]: {path}:{line}")
    for f in sorted(findings):
        print(f)
    return len(findings)


def mode_purge_audit(upstream: Path) -> int:
    findings = 0
    manifest = load_manifest()
    tracked = (
        subprocess.run(
            ["git", "-C", str(upstream), "ls-files", "-z"], capture_output=True, check=True
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    upstream_set = {t for t in tracked if t}
    head = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    if head != manifest["upstream"]["commit"]:
        print(
            f"upstream-commit-mismatch: clone at {head},"
            f" manifest says {manifest['upstream']['commit']}"
        )
        findings += 1
    present = {p.relative_to(SIM).as_posix() for p in sim_files()}
    listed = {e["path"]: e["sha256"] for e in manifest["entries"]}
    # "replaced": a listed path exists in sim/ with different bytes (our file, e.g. README.md)
    replaced = {p for p in listed if p in present and sha256(SIM / p) != listed[p]}
    deleted = (upstream_set - present) | replaced
    for p in sorted(deleted - set(listed)):
        print(f"deleted-but-unlisted: {p}")
        findings += 1
    for p in sorted(set(listed) - deleted):
        print(f"listed-but-not-deleted: {p}")
        findings += 1
    for e in manifest["entries"]:
        src = upstream / e["path"]
        if not src.is_file():
            print(f"listed-but-not-in-upstream: {e['path']}")
            findings += 1
            continue
        if sha256(src) != e["sha256"]:
            print(f"sha256-mismatch: {e['path']}")
            findings += 1
        if not e.get("reason"):
            print(f"missing-reason: {e['path']}")
            findings += 1
    print(
        f"purge-audit: upstream={len(upstream_set)} kept={len(upstream_set & present)} "
        f"deleted={len(deleted)} listed={len(listed)} replaced={len(replaced)}"
        f" added={len(present - upstream_set)}"
    )
    return findings


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--mode", choices=["nc", "deps", "brand", "all", "purge-audit"], required=True)
    ap.add_argument("--upstream", type=Path, default=ROOT / "refs" / "upstream" / "mobilegym")
    ap.add_argument(
        "--today", type=dt.date.fromisoformat, default=dt.date.today(), help="override for tests"
    )
    args = ap.parse_args()
    policy = load_policy()
    runners = {
        "nc": lambda: mode_nc(policy),
        "deps": lambda: mode_deps(policy, args.today),
        "brand": lambda: mode_brand(policy, args.today),
        "purge-audit": lambda: mode_purge_audit(args.upstream),
    }
    modes = ["nc", "deps", "brand"] if args.mode == "all" else [args.mode]
    total = 0
    for m in modes:
        n = runners[m]()
        print(f"scan[{m}]: {n} finding(s)")
        total += n
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
