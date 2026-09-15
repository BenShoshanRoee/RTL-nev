#!/usr/bin/env python3
"""Build sim/ from the upstream MobileGym clone, purging CC BY-NC content and unused parts.

Reads tracked files from the upstream clone (git ls-files), applies the ordered DELETE rules
below, copies everything else into sim/, and writes tools/licence/nc_purge_manifest.json with
a SHA-256 for every file NOT copied. Deterministic: same clone commit, same output.

This script is the audit trail for sub-chunk 1.1.2. Re-running it is safe:
  - kept files already present in sim/ are never overwritten (our edits live in git)
  - files at purged paths are removed only if their bytes are upstream's (our stubs survive)
  - files sim/ has that upstream does not are never touched
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
MANIFEST = ROOT / "tools" / "licence" / "nc_purge_manifest.json"
UPSTREAM_REPO = "https://github.com/Purewhiter/mobilegym"

RETAINED_APPS = ("Ebay", "TencentMeeting")  # code-only structural reference; deleted in 3.3.1
ALL_APPS = (
    "Alipay",
    "Bilibili",
    "Ebay",
    "Map",
    "Railway12306",
    "RedBook",
    "Reddit",
    "Spotify",
    "TencentMeeting",
    "Weather",
    "Wechat",
    "WechatReading",
    "X",
)
DELETED_APPS = tuple(a for a in ALL_APPS if a not in RETAINED_APPS)
# System apps the OS shell needs (Clock widget, Contacts/Sms providers) or the bench
# protocol needs (AnswerSheet) stay. The rest are phone-vendor UI replicas we never use.
KEPT_SYSTEM_APPS = ("AnswerSheet", "Clock", "Contacts", "Sms")
DELETED_SYSTEM_APPS = (
    "Browser",
    "Calculator",
    "Calculator2",
    "Calendar",
    "Compass",
    "FileManager",
    "Gallery",
    "Notes",
    "Settings",
    "ThemeStore",
)

# Ordered (regex on upstream-relative path, reason). First match wins. No match = keep.
RULES: list[tuple[str, str]] = [
    (r"^apps/[^/]+/(data|assets)/", "nc-data"),
    (r"^apps/(" + "|".join(DELETED_APPS) + r")/", "unused-upstream-app"),
    (r"^system/(" + "|".join(DELETED_SYSTEM_APPS) + r")/", "unused-upstream-system-app"),
    # kept system apps: data/index.ts is the Apache-2.0 loader code and stays; the content
    # files (defaults.json, cities.json, *.generated.ts, ...) go and are replaced by stubs
    (r"^system/[^/]+/(data/(?!index\.ts$)|assets/)", "system-app-data"),
    (r"^public/(sdcard|ime|icons)/", "nc-public-asset"),
    (r"^public/logos/", "brand-asset"),
    (r"^public/tailwind\.css$", "generated-artifact"),
    (r"^mobilegym-rl/", "vendored-training-stack"),
    (r"^bench_env/(task|tests)/", "upstream-benchmark"),
    (r"^scripts/ime/", "unused-upstream-tooling"),
    (r"^scripts/dev/prepare-themes\.py$", "unused-upstream-tooling"),
    (r"^(web|assets)/", "project-surface"),
    (
        r"^(README\.md|README_zh\.md|CONTRIBUTING\.md|\.env\.example|AGENTS\.md|CLAUDE\.md)$",
        "project-surface",
    ),
    (r"^(\.github|\.claude)/", "project-surface"),
    (r"^package-lock\.json$", "replaced-by-workspace"),
    (r"^(LICENSE-DATA|DISCLAIMER\.md)$", "nc-licence-text"),
]
REASONS = {
    "nc-data": "CC BY-NC 4.0 per upstream LICENSE-DATA (apps/*/data, apps/*/assets)",
    "unused-upstream-app": (
        "Apache-2.0 code for a brand-named app we do not ship; dead without its data"
    ),
    "system-app-data": "Synthetic content bundled with kept system apps; replaced by empty stubs",
    "unused-upstream-system-app": "System app the OS shell does not need; phone-vendor UI replica",
    "nc-public-asset": ("Fake storage, IME dictionary and icons; LICENSE-DATA names icons as data"),
    "brand-asset": "Logos of real companies",
    "generated-artifact": "Build output; regenerated from source",
    "vendored-training-stack": "rLLM/verl vendored copy; Phase 7 uses our own training/",
    "upstream-benchmark": "MobileGym-Bench task definitions and tests for deleted apps",
    "unused-upstream-tooling": "Tooling for purged data (IME, themes)",
    "project-surface": "Upstream website, README images, agent config, CI",
    "replaced-by-workspace": "npm lockfile replaced by the pnpm workspace lockfile",
    "nc-licence-text": (
        "Licence and disclaimer for data we no longer carry; recorded in UPSTREAM.md"
    ),
    "dead-test": "Test importing a deleted app",
}

DEAD_TEST_PATTERN = re.compile(
    r"apps/(" + "|".join(DELETED_APPS) + r")\b"
    r"|['\"](" + "|".join(DELETED_APPS) + r")['\"]"
    r"|system/(" + "|".join(DELETED_SYSTEM_APPS) + r")\b"
    r"|\bweb/"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(rel: str, upstream: Path) -> str | None:
    for pattern, reason in RULES:
        if re.search(pattern, rel):
            return reason
    if rel.startswith("tests/") and rel.endswith(".ts"):
        text = (upstream / rel).read_text(encoding="utf-8", errors="replace")
        if DEAD_TEST_PATTERN.search(text):
            return "dead-test"
    return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--upstream", type=Path, default=ROOT / "refs" / "upstream" / "mobilegym")
    ap.add_argument("--dry-run", action="store_true", help="classify only; write nothing")
    args = ap.parse_args()
    upstream = args.upstream.resolve()
    if not (upstream / ".git").exists():
        sys.exit(f"upstream clone not found at {upstream}")
    commit = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    tracked = sorted(
        t
        for t in subprocess.run(
            ["git", "-C", str(upstream), "ls-files", "-z"], capture_output=True, check=True
        )
        .stdout.decode("utf-8")
        .split("\0")
        if t
    )

    entries: list[dict] = []
    kept: list[str] = []
    by_reason: dict[str, int] = {}
    for rel in tracked:
        reason = classify(rel, upstream)
        if reason is None:
            kept.append(rel)
            continue
        src = upstream / rel
        entries.append(
            {"path": rel, "sha256": sha256(src), "bytes": src.stat().st_size, "reason": reason}
        )
        by_reason[reason] = by_reason.get(reason, 0) + 1
        stale = SIM / rel
        if not args.dry_run and stale.is_file() and sha256(stale) == entries[-1]["sha256"]:
            # a re-run with widened rules removes upstream content it now classifies;
            # a file of ours at the same path (different bytes, e.g. a stub) is left alone
            stale.unlink()
            print(f"removed stale: sim/{rel}")

    print(
        f"upstream {commit[:12]}: {len(tracked)} tracked files"
        f" -> keep {len(kept)}, delete {len(entries)}"
    )
    for reason, n in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        print(f"  {n:6d}  {reason}")
    if args.dry_run:
        return

    copied = 0
    for rel in kept:
        dst = SIM / rel
        if dst.exists():
            continue  # never overwrite: our modifications to kept files are tracked in git
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(upstream / rel, dst)
        copied += 1
    # unlinking stale files leaves empty directories behind; drop them (deepest first)
    for d in sorted((d for d in SIM.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    manifest = {
        "schema_version": 1,
        "upstream": {"repo": UPSTREAM_REPO, "commit": commit},
        "generated_by": "tools/licence/purge_fork.py",
        "retained_apps": list(RETAINED_APPS),
        "reasons": REASONS,
        "entries": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"copied {copied} missing files into sim/ ({len(kept)} kept);"
        f" wrote {MANIFEST.relative_to(ROOT)} ({len(entries)} entries)"
    )


if __name__ == "__main__":
    main()
