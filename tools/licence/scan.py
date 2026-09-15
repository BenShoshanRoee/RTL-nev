#!/usr/bin/env python3
"""Licence firewall scanner. Minimal version from sub-chunk 1.1.2; 1.1.3 extends it add-only.

Modes:
  nc           Assert no CC BY-NC content is present under sim/ (CI-safe, needs no upstream).
  purge-audit  Assert tools/licence/nc_purge_manifest.json exactly equals upstream minus sim/,
               with matching SHA-256 per deleted file. Needs the upstream clone (local only).

Exit 0 on zero findings, 1 otherwise. Every finding is one line: "<check>: <path or detail>".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
MANIFEST = ROOT / "tools" / "licence" / "nc_purge_manifest.json"
SKIP_DIRS = {"node_modules", "dist", ".venv", "__pycache__", ".git"}
NC_STRINGS = ("mobilegym-data", "BY-NC", "NonCommercial", "Non-Commercial")
# The fork NOTICE must preserve upstream's text, which names the data licence we removed.
NC_STRING_EXEMPT = {"sim/NOTICE"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sim_files() -> list[Path]:
    out: list[Path] = []
    for p in SIM.rglob("*"):
        if p.is_file() and not (set(p.relative_to(SIM).parts) & SKIP_DIRS):
            out.append(p)
    return out


def load_manifest() -> dict:
    if not MANIFEST.exists():
        print(f"manifest-missing: {MANIFEST.relative_to(ROOT)}")
        sys.exit(1)
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def mode_nc() -> int:
    findings = 0
    if not SIM.is_dir():
        print("sim-missing: sim/ does not exist")
        return 1
    manifest = load_manifest()
    for entry in manifest["entries"]:
        target = SIM / entry["path"]
        # A file of ours at a purged path is fine; upstream's bytes at that path are not.
        if target.is_file() and sha256(target) == entry["sha256"]:
            print(f"purged-content-present: sim/{entry['path']}")
            findings += 1
    # apps/*/{data,assets} and system/*/assets must not exist at all. system/*/data may exist
    # for kept system apps: it holds the Apache-2.0 loader plus our empty stubs, and any
    # upstream bytes there are caught by the purged-content-present check above.
    for parent, subs in (("apps", ("data", "assets")), ("system", ("assets",))):
        base = SIM / parent
        if base.is_dir():
            for app in sorted(base.iterdir()):
                for sub in subs:
                    if (app / sub).exists():
                        print(f"nc-dir-present: {(app / sub).relative_to(ROOT)}")
                        findings += 1
    for p in sim_files():
        if str(p.relative_to(ROOT)) in NC_STRING_EXEMPT:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle in NC_STRINGS:
            if needle in text:
                print(f"nc-string[{needle}]: {p.relative_to(ROOT)}")
                findings += 1
                break
    return findings


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
    present = {str(p.relative_to(SIM)) for p in sim_files()}
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
    ap.add_argument("--mode", choices=["nc", "purge-audit"], required=True)
    ap.add_argument("--upstream", type=Path, default=ROOT / "refs" / "upstream" / "mobilegym")
    args = ap.parse_args()
    findings = mode_nc() if args.mode == "nc" else mode_purge_audit(args.upstream)
    print(f"scan[{args.mode}]: {findings} finding(s)")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
