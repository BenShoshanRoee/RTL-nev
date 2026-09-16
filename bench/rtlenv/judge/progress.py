"""Progress: the fraction of a task's ordered milestones reached, in order.

Milestones are matcher specs evaluated over the states the agent actually passed through. The
trace is replayed from the setup state by applying each step's changeset and checking every
hash in the chain; a trace that does not reconstruct is invalid and earns no partial credit
(a forged or inconsistent trace is a cheat surface, not a rounding error).

A milestone is "reached" at the first step where it holds. It counts only if every earlier
milestone was reached at an earlier-or-equal step: out-of-order achievement is not progress.
Without a trace, milestones are evaluated on the final state only and their order cannot be
verified; a milestone that no longer holds at the end is then unreached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rtlenv.domain_protocol import hash_state, patch
from rtlenv.judge.matchers import parse


@dataclass(frozen=True)
class ProgressResult:
    rate: float
    counted: int
    total: int
    reached_at: list[int | None]
    trace_valid: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate": self.rate,
            "counted": self.counted,
            "total": self.total,
            "reached_at": self.reached_at,
            "trace_valid": self.trace_valid,
            "reason": self.reason,
        }


def replay(before: dict, trace: list[dict], after: dict) -> tuple[list[dict], str | None]:
    """States after each step, or a reason the trace is inconsistent."""
    states: list[dict] = []
    current = before
    expected_before = hash_state(before)
    for i, entry in enumerate(trace):
        if not isinstance(entry, dict) or "changes" not in entry:
            return [], f"trace[{i}]: missing changes"
        if entry.get("beforeHash") != expected_before:
            return [], f"trace[{i}]: beforeHash does not match the reconstructed state hash"
        try:
            current = patch(current, entry["changes"])
        except Exception as e:  # noqa: BLE001 - any malformed changeset invalidates the trace
            return [], f"trace[{i}]: changeset could not be applied ({e})"
        h = hash_state(current)
        if entry.get("afterHash") != h:
            return [], f"trace[{i}]: afterHash does not match the reconstructed state hash"
        expected_before = h
        states.append(current)
    if trace and expected_before != hash_state(after):
        return [], "trace: final reconstructed state hash does not match the after-state"
    return states, None


def compute_progress(
    milestones: list[dict], before: dict, after: dict, trace: list[dict]
) -> ProgressResult:
    total = len(milestones)
    if total == 0:
        return ProgressResult(rate=0.0, counted=0, total=0, reached_at=[], trace_valid=True)
    matchers = [parse(m) for m in milestones]
    states, reason = replay(before, trace, after)
    if reason is not None:
        return ProgressResult(
            rate=0.0,
            counted=0,
            total=total,
            reached_at=[None] * total,
            trace_valid=False,
            reason=reason,
        )
    if not trace:
        states = [after]  # step 0 = final state only
    reached: list[int | None] = []
    for m in matchers:
        step = next(
            (i for i, s in enumerate(states, start=1 if trace else 0) if m.evaluate(before, s).ok),
            None,
        )
        reached.append(step)
    counted = 0
    last = -1
    for step in reached:
        if step is None or step < last:
            break
        counted += 1
        last = step
    return ProgressResult(
        rate=counted / total, counted=counted, total=total, reached_at=reached, trace_valid=True
    )
