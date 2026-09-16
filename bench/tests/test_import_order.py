"""Every public module must import first, alone, in a fresh interpreter.

A buyer's first line may be ``from rtlenv.task import Registry``. Before 2.2.4 that raised an
ImportError from a judge <-> task.schema cycle that every in-repo entry point happened to mask
by importing the judge package first.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

MODULES = [
    "rtlenv",
    "rtlenv.rng",
    "rtlenv.logging",
    "rtlenv.domain_protocol",
    "rtlenv.judge",
    "rtlenv.judge.core",
    "rtlenv.judge.matchers",
    "rtlenv.judge.progress",
    "rtlenv.judge.reward",
    "rtlenv.judge.verdict",
    "rtlenv.task",
    "rtlenv.task.schema",
    "rtlenv.task.registry",
    "rtlenv.task.validate",
    "rtlenv.metatest.harness",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", f"import {module}"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_lazy_judge_names_resolve_and_are_listed() -> None:
    import rtlenv.judge as j

    assert callable(j.judge) and isinstance(j.JUDGE_CONTRACT_VERSION, str)
    assert {"judge", "Rollout", "JUDGE_CONTRACT_VERSION"} <= set(dir(j))
    with pytest.raises(AttributeError):
        j.no_such_name  # noqa: B018
