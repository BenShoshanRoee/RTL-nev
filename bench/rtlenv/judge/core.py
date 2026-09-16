"""State-diff judge. Deterministic, pure Python over dicts, no I/O, sub-millisecond.

The judge sees the state before, the state after, the action trace, and whether the agent
declared completion. It never sees agent text: a model cannot talk its way to reward.

  success        every goal matcher holds on the after-state AND no protected subtree moved
  side_effects   every change under the task's unchanged_subtrees (the side-effect mechanism)
  false_complete declared_done and not success (penalised in 2.2.2)
  progress       1.0 / 0.0 here; sub-chunk 2.2.2 replaces it with ordered milestones
  reward         1.0 only for success; sub-chunk 2.2.2 replaces it with shaped reward
  evidence       goal results, goal_held_before (a trivial task), hashes, trace length
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rtlenv.domain_protocol import diff, hash_state
from rtlenv.judge.matchers import Unchanged, parse
from rtlenv.judge.verdict import Verdict
from rtlenv.task.schema import TaskContract, validate_task


@dataclass(frozen=True)
class Rollout:
    before: dict[str, Any]
    after: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    declared_done: bool = False


def judge(
    task: TaskContract | dict[str, Any], rollout: Rollout, *, explain: bool = False
) -> Verdict:
    contract = task if isinstance(task, TaskContract) else validate_task(task)
    matchers = [parse(spec) for spec in contract.goal_matchers]
    goal_results = [m.evaluate(rollout.before, rollout.after) for m in matchers]
    goal_ok = all(r.ok for r in goal_results)
    protected = Unchanged(contract.unchanged_subtrees).evaluate(rollout.before, rollout.after)
    side_effects: list[dict[str, Any]] = [] if protected.ok else list(protected.evidence["changes"])
    success = goal_ok and not side_effects
    goal_held_before = all(m.evaluate(rollout.before, rollout.before).ok for m in matchers)
    evidence: dict[str, Any] = {
        "goal": [r.to_dict() for r in goal_results],
        "goal_held_before": goal_held_before,
        "trace_length": len(rollout.trace),
        "protected_subtrees": contract.unchanged_subtrees,
    }
    if explain:
        evidence["before_hash"] = hash_state(rollout.before)
        evidence["after_hash"] = hash_state(rollout.after)
        evidence["all_changes"] = diff(rollout.before, rollout.after)["changes"]
    return Verdict(
        task_id=contract.id,
        success=success,
        progress=1.0 if goal_ok else 0.0,
        side_effects=side_effects,
        false_complete=bool(rollout.declared_done and not success),
        reward=1.0 if success else 0.0,
        evidence=evidence,
    )
