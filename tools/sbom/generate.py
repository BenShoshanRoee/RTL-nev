#!/usr/bin/env python3
"""Generate one CycloneDX 1.5 SBOM covering the JS (pnpm) and Python (uv) workspaces.

JS packages are enumerated exactly as tools/licence/scan.py does (pnpm ls, licence read from
each package's own manifest); Python packages from the uv environment's installed metadata.
Output is deterministic: components sorted by purl, timestamp and serial number injectable
or derived from content, so two runs on the same tree are byte-identical.

  uv run python tools/sbom/generate.py --output dist/sbom.cdx.json --validate
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata as md
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.model.license import DisjunctiveLicense, LicenseExpression
from cyclonedx.output.json import JsonV1Dot5
from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from packageurl import PackageURL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "licence"))
from scan import python_licence  # noqa: E402  (shared mapping of Python licence metadata)

SPDX_ID = re.compile(r"^[A-Za-z0-9.+-]+$")


def licence_of(text: str | None):
    """A CycloneDX licence entry: SPDX id, expression, or a named licence."""
    if not text:
        return None
    if SPDX_ID.match(text):
        return (
            DisjunctiveLicense(id=text)
            if "-" in text or text in ("MIT", "ISC")
            else DisjunctiveLicense(name=text)
        )
    try:
        return LicenseExpression(text)
    except Exception:  # noqa: BLE001 - fall back to a named licence for odd strings
        return DisjunctiveLicense(name=text)


def js_components() -> list[Component]:
    raw = subprocess.run(
        ["pnpm", "ls", "-r", "--depth", "Infinity", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    seen: dict[tuple[str, str], str] = {}

    def walk(node: dict) -> None:
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, dep in (node.get(key) or {}).items():
                if dep.get("path"):
                    seen[(name, dep.get("version", "?"))] = dep["path"]
                walk(dep)

    for project in json.loads(raw):
        walk(project)
    out: list[Component] = []
    for (name, version), path in sorted(seen.items()):
        pkg_json = Path(path) / "package.json"
        if not Path(path).is_dir():
            continue  # other platforms' optional binaries are not installed here
        meta = json.loads(pkg_json.read_text(encoding="utf-8"))
        if meta.get("private") and (ROOT / "packages") in Path(path).parents:
            continue  # our own workspace packages are the subject, not dependencies
        if version.startswith("link:"):
            continue
        lic = meta.get("license")
        if isinstance(lic, dict):
            lic = lic.get("type")
        ns, _, short = name.rpartition("/") if name.startswith("@") else ("", "", name)
        purl = PackageURL(type="npm", namespace=ns or None, name=short, version=version)
        comp = Component(
            type=ComponentType.LIBRARY,
            name=name,
            version=version,
            purl=purl,
            bom_ref=purl.to_string(),
        )
        entry = licence_of(lic)
        if entry:
            comp.licenses.add(entry)
        out.append(comp)
    return out


def python_components() -> list[Component]:
    own = set()
    for member in ("bench", "packages_py/rtl_commerce"):
        m = re.search(
            r'^name\s*=\s*"([^"]+)"',
            (ROOT / member / "pyproject.toml").read_text(encoding="utf-8"),
            flags=re.M,
        )
        if m:
            own.add(m.group(1).lower().replace("_", "-"))
    out: list[Component] = []
    for dist in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower().replace("_", "-") in own:
            continue
        version = dist.metadata["Version"]
        purl = PackageURL(type="pypi", name=name.lower().replace("_", "-"), version=version)
        comp = Component(
            type=ComponentType.LIBRARY,
            name=name,
            version=version,
            purl=purl,
            bom_ref=purl.to_string(),
        )
        entry = licence_of(python_licence(dist))
        if entry:
            comp.licenses.add(entry)
        out.append(comp)
    return out


def build(timestamp: str, version: str) -> Bom:
    bom = Bom()
    bom.metadata.timestamp = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    bom.metadata.component = Component(
        type=ComponentType.APPLICATION,
        name="rtl-environments",
        version=version,
        bom_ref=f"rtl-environments@{version}",
    )
    comps = sorted(js_components() + python_components(), key=lambda c: c.purl.to_string())
    for c in comps:
        bom.components.add(c)
        bom.register_dependency(bom.metadata.component, [c])
    digest = hashlib.sha256("\n".join(c.purl.to_string() for c in comps).encode()).hexdigest()
    bom.serial_number = uuid.UUID(
        digest[:32]
    )  # content-derived, so equal trees give equal documents
    bom.version = 1
    return bom


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--timestamp", default=None, help="ISO-8601 UTC; defaults to now")
    ap.add_argument("--version", default="0.0.0", help="application version recorded in metadata")
    ap.add_argument(
        "--validate", action="store_true", help="validate against the CycloneDX 1.5 JSON schema"
    )
    args = ap.parse_args()
    ts = args.timestamp or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    bom = build(ts, args.version)
    text = JsonV1Dot5(bom).output_as_string(indent=2)
    if args.validate:
        errors = JsonStrictValidator(SchemaVersion.V1_5).validate_str(text)
        if errors:
            sys.exit(f"SBOM invalid: {errors}")
        print("valid CycloneDX 1.5")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    n_js = sum(1 for c in bom.components if c.purl.type == "npm")
    n_py = sum(1 for c in bom.components if c.purl.type == "pypi")
    print(f"wrote {args.output} ({n_js} npm + {n_py} pypi components)")


if __name__ == "__main__":
    main()
