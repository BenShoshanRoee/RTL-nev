#!/usr/bin/env python3
"""Release versions come from the git tag and nowhere else.

version.py --from-tag v1.2.3            -> prints 1.2.3
version.py --from-tag v1.2.3 --apply    -> also writes it into every workspace manifest
                                           under the current directory (never committed;
                                           the release workflow builds from the result)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z][0-9A-Za-z.-]*)?$")
JSON_MANIFESTS = (
    "package.json",
    "sim/package.json",
    "packages/*/package.json",
    "packages/domains/*/package.json",
)
TOML_MANIFESTS = ("pyproject.toml", "bench/pyproject.toml", "packages_py/*/pyproject.toml")


def version_from_tag(tag: str) -> str:
    if not TAG.match(tag):
        sys.exit(f"tag {tag!r} is not vMAJOR.MINOR.PATCH[-prerelease]")
    return tag[1:]


def apply(version: str, root: Path) -> list[Path]:
    touched: list[Path] = []
    for pattern in JSON_MANIFESTS:
        for path in sorted(root.glob(pattern)):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["version"] = version
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            touched.append(path)
    for pattern in TOML_MANIFESTS:
        for path in sorted(root.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            new, n = re.subn(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{version}"', text, count=1)
            if n != 1:
                sys.exit(f"{path}: no version line to rewrite")
            path.write_text(new, encoding="utf-8")
            touched.append(path)
    return touched


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--from-tag", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    version = version_from_tag(args.from_tag)
    if args.apply:
        for p in apply(version, Path.cwd()):
            print(f"set {p} -> {version}", file=sys.stderr)
    print(version)


if __name__ == "__main__":
    main()
