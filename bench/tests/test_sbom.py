"""The SBOM covers both ecosystems, validates as CycloneDX, and is deterministic."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "tools" / "sbom" / "generate.py"


def _generate(tmp: Path, name: str) -> dict:
    out = tmp / name
    subprocess.run(
        [sys.executable, str(GEN), "--output", str(out), "--timestamp", "2026-09-15T00:00:00Z"],
        check=True,
        cwd=ROOT,
        capture_output=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_sbom_is_cyclonedx_with_both_ecosystems(tmp_path: Path) -> None:
    bom = _generate(tmp_path, "a.json")
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.5"
    purls = {c["purl"] for c in bom["components"]}
    assert any(p.startswith("pkg:npm/react@") for p in purls), "JS components missing"
    assert any(p.startswith("pkg:pypi/pytest@") for p in purls), "Python components missing"
    for c in bom["components"]:
        assert c["purl"] and c["name"] and c["version"], c
        assert c.get("licenses"), f"{c['purl']} has no licence recorded"
    assert bom["metadata"]["component"]["name"] == "rtl-environments"


def test_sbom_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    for out in (a, b):
        subprocess.run(
            [sys.executable, str(GEN), "--output", str(out), "--timestamp", "2026-09-15T00:00:00Z"],
            check=True,
            cwd=ROOT,
            capture_output=True,
        )
    assert a.read_bytes() == b.read_bytes()


def test_sbom_validates_against_the_official_schema(tmp_path: Path) -> None:
    out = tmp_path / "v.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(GEN),
            "--output",
            str(out),
            "--timestamp",
            "2026-09-15T00:00:00Z",
            "--validate",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "valid CycloneDX 1.5" in proc.stdout
