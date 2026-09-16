"""Shaped reward: dense enough for RL gradient, not gameable.

  reward = w_success * success + w_progress * progress
           - w_side * min(side_effects, side_cap) - w_false * false_complete
  clamped to [min, max]

Defaults (documented here, overridable per task under ``reward`` and validated):
  w_success 0.6, w_progress 0.4  -> full success with every milestone = 1.0 = max
  w_side    0.25 per side effect, side_cap 4
  w_false   0.5
  min -1.0, max 1.0

Invariants the validator enforces, because they are what make partial credit safe:
  - w_false >= w_progress: any false-complete transcript scores below any honest failure,
    whatever their progress. Non-negotiable per the plan.
  - w_success > w_progress: success reached by a shortcut still outranks every failure.
  - w_success + w_progress <= max: full success is not clamped into ambiguity.
"""

from __future__ import annotations

from typing import Any

DEFAULT_WEIGHTS: dict[str, float] = {
    "w_success": 0.6,
    "w_progress": 0.4,
    "w_side": 0.25,
    "side_cap": 4,
    "w_false": 0.5,
    "min": -1.0,
    "max": 1.0,
}
KEYS = tuple(DEFAULT_WEIGHTS)


class RewardConfigError(ValueError):
    """Reward weights violate a documented invariant. The message names the weight."""


def validate_weights(weights: dict[str, Any]) -> dict[str, float]:
    unknown = set(weights) - set(KEYS)
    if unknown:
        raise RewardConfigError(f"unknown reward weight(s): {sorted(unknown)}")
    w = {**DEFAULT_WEIGHTS, **weights}
    for k in KEYS:
        v = w[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise RewardConfigError(f"{k}: must be a number")
        if k not in ("min", "max") and v < 0:
            raise RewardConfigError(f"{k}: must not be negative")
    if w["min"] > 0 or w["max"] <= 0 or w["min"] >= w["max"]:
        raise RewardConfigError("min/max: need min <= 0 < max")
    if w["w_false"] < w["w_progress"]:
        raise RewardConfigError(
            "w_false must be >= w_progress so a false-complete never outscores an honest failure"
        )
    if w["w_success"] <= w["w_progress"]:
        raise RewardConfigError(
            "w_success must exceed w_progress so success outranks every failure"
        )
    if w["w_success"] + w["w_progress"] > w["max"]:
        raise RewardConfigError(
            "max must be at least w_success + w_progress so full success is not clamped"
        )
    return {k: float(w[k]) for k in KEYS}


def compute_reward(
    *,
    success: bool,
    progress: float,
    side_effects: int,
    false_complete: bool,
    weights: dict[str, Any] | None = None,
) -> float:
    w = validate_weights(weights or {})
    if not 0.0 <= progress <= 1.0:
        raise RewardConfigError(f"progress must be in [0, 1], got {progress}")
    raw = (
        w["w_success"] * (1.0 if success else 0.0)
        + w["w_progress"] * progress
        - w["w_side"] * min(max(side_effects, 0), w["side_cap"])
        - w["w_false"] * (1.0 if false_complete else 0.0)
    )
    return max(w["min"], min(w["max"], raw))
