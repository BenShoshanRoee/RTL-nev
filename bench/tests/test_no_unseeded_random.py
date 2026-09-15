"""Lint: unseeded randomness is forbidden outside bench/rtlenv/rng.py.

Scans every tracked Python file under bench/, tools/ and packages_py/ for the standard
library and numpy entropy sources. Fails naming file and line.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {"bench/rtlenv/rng.py"}
PATTERNS = [
    re.compile(r"^\s*import random\b"),
    re.compile(r"^\s*from random import"),
    re.compile(r"\bnp\.random\.|\bnumpy\.random\."),
    re.compile(r"\buuid4\("),
    re.compile(r"\bos\.urandom\("),
    re.compile(r"\bsecrets\.(token_|choice|randbelow)"),
]


def tracked_python_files() -> list[str]:
    out = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "-co",
            "--exclude-standard",
            "--",
            "bench",
            "tools",
            "packages_py",
        ],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.split("\n")
    return sorted(p for p in out if p.endswith(".py") and (ROOT / p).is_file())


def test_no_unseeded_randomness_outside_rng() -> None:
    hits: list[str] = []
    for path in tracked_python_files():
        if path in ALLOWED or path == "bench/tests/test_no_unseeded_random.py":
            continue
        for n, line in enumerate((ROOT / path).read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in PATTERNS):
                hits.append(f"{path}:{n}: {line.strip()}")
    assert not hits, "unseeded randomness outside rng.py:\n" + "\n".join(hits)
