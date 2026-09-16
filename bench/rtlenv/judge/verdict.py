"""The judge's output. Fixed top-level field order and sorted nested keys, so two runs over the
same rollout serialise byte-identically. Floats are kept (progress and reward are fractional
from 2.2.2 on) using Python's shortest-repr formatting, which is deterministic; NaN and
infinity are refused.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

FIELDS = ("task_id", "success", "progress", "side_effects", "false_complete", "reward", "evidence")


@dataclass(frozen=True)
class Verdict:
    task_id: str
    success: bool
    progress: float
    side_effects: list[dict[str, Any]]
    false_complete: bool
    reward: float
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in FIELDS}

    def to_json(self) -> str:
        """One line: FIELDS order at the top level, sorted keys below, no whitespace."""
        parts = []
        for k in FIELDS:
            v = getattr(self, k)
            _reject_non_finite(v)
            body = json.dumps(
                v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            )
            parts.append(f'"{k}":{body}')
        return "{" + ",".join(parts) + "}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Verdict:
        return cls(**{k: d[k] for k in FIELDS})


def _reject_non_finite(v: Any) -> None:
    if isinstance(v, float) and not math.isfinite(v):
        raise ValueError("verdict contains a non-finite number")
    if isinstance(v, dict):
        for x in v.values():
            _reject_non_finite(x)
    elif isinstance(v, list):
        for x in v:
            _reject_non_finite(x)
