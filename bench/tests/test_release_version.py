"""Release versions come from the git tag and nowhere else."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "release" / "version.py"


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True
    )


@pytest.mark.parametrize(
    "tag,version", [("v0.0.1", "0.0.1"), ("v1.2.3", "1.2.3"), ("v2.0.0-rc.1", "2.0.0-rc.1")]
)
def test_version_from_tag(tag: str, version: str) -> None:
    proc = run("--from-tag", tag)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == version


@pytest.mark.parametrize("tag", ["0.0.1", "v1.2", "release-1", "v01.2.3", ""])
def test_rejects_malformed_tags(tag: str) -> None:
    proc = run("--from-tag", tag)
    assert proc.returncode != 0
    assert tag in proc.stderr or "tag" in proc.stderr


def test_apply_writes_every_manifest(tmp_path: Path) -> None:
    work = tmp_path / "repo"
    for rel in (
        "package.json",
        "pyproject.toml",
        "sim/package.json",
        "bench/pyproject.toml",
        "packages_py/rtl_commerce/pyproject.toml",
        "packages/core-semantic/package.json",
    ):
        dst = work / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)
    proc = run("--from-tag", "v3.4.5", "--apply", cwd=work)
    assert proc.returncode == 0, proc.stderr
    assert json.loads((work / "package.json").read_text())["version"] == "3.4.5"
    assert json.loads((work / "sim/package.json").read_text())["version"] == "3.4.5"
    assert (
        json.loads((work / "packages/core-semantic/package.json").read_text())["version"] == "3.4.5"
    )
    for rel in (
        "pyproject.toml",
        "bench/pyproject.toml",
        "packages_py/rtl_commerce/pyproject.toml",
    ):
        assert 'version = "3.4.5"' in (work / rel).read_text()
    assert (work / "packages/core-semantic/package.json").read_text().endswith("}\n")
