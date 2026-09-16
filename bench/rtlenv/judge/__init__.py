"""Public API of the state-diff judge (contract version in JUDGE_CONTRACT_VERSION).

The leaf modules (matchers, progress, reward, verdict) import eagerly. The three names from
``core`` resolve lazily on first access because ``core`` depends on ``rtlenv.task.schema``,
which itself depends on the leaf modules here; importing ``core`` at package import time made
``import rtlenv.task.schema`` fail in a fresh interpreter (bench/tests/test_import_order.py).
"""

from __future__ import annotations

from typing import Any

from rtlenv.judge.matchers import KINDS, MatcherSpecError, MatchResult, parse, strict_equal
from rtlenv.judge.progress import ProgressResult, compute_progress, replay
from rtlenv.judge.reward import DEFAULT_WEIGHTS, RewardConfigError, compute_reward, validate_weights
from rtlenv.judge.verdict import FIELDS, Verdict

_CORE_NAMES = ("JUDGE_CONTRACT_VERSION", "Rollout", "judge")

__all__ = [
    "FIELDS",
    "JUDGE_CONTRACT_VERSION",
    "KINDS",
    "MatchResult",
    "MatcherSpecError",
    "ProgressResult",
    "RewardConfigError",
    "Rollout",
    "DEFAULT_WEIGHTS",
    "compute_progress",
    "compute_reward",
    "replay",
    "validate_weights",
    "Verdict",
    "judge",
    "parse",
    "strict_equal",
]


def __getattr__(name: str) -> Any:
    if name in _CORE_NAMES:
        from rtlenv.judge import core

        value = getattr(core, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
