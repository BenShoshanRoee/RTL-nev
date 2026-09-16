"""The judge's output. Fixed field order and canonical serialisation so two runs over the
same rollout are byte-identical."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rtlenv.domain_protocol import canonical_json

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
        """One canonical line: top-level fields in FIELDS order, nested content with sorted keys."""
        return (
            "{"
            + ",".join(f'"{k}":{canonical_json(_floats_as_ints(getattr(self, k)))}' for k in FIELDS)
            + "}"
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Verdict:
        return cls(**{k: d[k] for k in FIELDS})


def _floats_as_ints(v: Any) -> Any:
    """Floats become integers for canonical JSON: 1.0 -> 1, else six-decimal fixed point."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, float):
        return int(round(v * 1_000_000))  # six-decimal fixed point, documented in reward.py (2.2.2)
    if isinstance(v, list):
        return [_floats_as_ints(x) for x in v]
    if isinstance(v, dict):
        return {k: _floats_as_ints(x) for k, x in v.items()}
    return v
