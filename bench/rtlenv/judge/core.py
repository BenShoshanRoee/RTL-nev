"""State-diff judge. Deterministic, pure Python over dicts, no I/O, sub-millisecond.

The judge sees the state before, the state after, the action trace, and whether the agent
declared completion. It never sees agent text: a model cannot talk its way to reward.

  success        every goal matcher holds on the after-state AND no protected subtree moved
  side_effects   every change under the task's unchanged_subtrees (the side-effect mechanism)
  false_complete declared_done and not success (penalised in 2.2.2)
  progress       fraction of the task's ordered milestones reached in order (trace replayed
                 and hash-verified); a task without milestones scores 1.0 iff the goal holds
  reward         shaped: see reward.py (defaults documented there; task may override)
  evidence       goal results, goal_held_before (a trivial task), hashes, trace length
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rtlenv.domain_protocol import diff, hash_state
from rtlenv.judge.matchers import Unchanged, parse
from rtlenv.judge.progress import compute_progress
from rtlenv.judge.reward import RewardConfigError, compute_reward, validate_weights
from rtlenv.judge.verdict import Verdict
from rtlenv.logging import Logger
from rtlenv.task.schema import TaskContract, TaskContractError, validate_task

# Bump when the verdict shape or the semantics of success / side effects change.
JUDGE_CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class Rollout:
    before: dict[str, Any]
    after: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    declared_done: bool = False


def judge(
    task: TaskContract | dict[str, Any],
    rollout: Rollout,
    *,
    explain: bool = False,
    log: Logger | None = None,
) -> Verdict:
    contract = task if isinstance(task, TaskContract) else validate_task(task)
    # A protected path absent from the setup state would protect nothing: a typo in
    # unchanged_subtrees is the quietest way to make a judge permissive. Refuse it by name.
    for p in contract.unchanged_subtrees:
        if not _path_exists(rollout.before, p):
            raise TaskContractError(
                f"unchanged_subtrees: path {p} does not exist in the setup state"
            )
    matchers = [parse(spec) for spec in contract.goal_matchers]
    goal_results = [m.evaluate(rollout.before, rollout.after) for m in matchers]
    goal_ok = all(r.ok for r in goal_results)
    protected = Unchanged(contract.unchanged_subtrees).evaluate(rollout.before, rollout.after)
    side_effects: list[dict[str, Any]] = [] if protected.ok else list(protected.evidence["changes"])
    success = goal_ok and not side_effects
    goal_held_before = all(m.evaluate(rollout.before, rollout.before).ok for m in matchers)
    try:
        weights = validate_weights(contract.reward)
    except RewardConfigError as e:
        raise RewardConfigError(f"task {contract.id}: {e}") from e
    if contract.milestones:
        prog = compute_progress(contract.milestones, rollout.before, rollout.after, rollout.trace)
        progress = prog.rate
    else:
        prog = None
        progress = 1.0 if goal_ok else 0.0
    false_complete = bool(rollout.declared_done and not success)
    reward = compute_reward(
        success=success,
        progress=progress,
        side_effects=len(side_effects),
        false_complete=false_complete,
        weights=weights,
    )
    evidence: dict[str, Any] = {
        "goal": [r.to_dict() for r in goal_results],
        "goal_held_before": goal_held_before,
        "trace_length": len(rollout.trace),
        "protected_subtrees": contract.unchanged_subtrees,
        "judge_version": JUDGE_CONTRACT_VERSION,
        "reward_weights": weights,
        "trace_valid": prog.trace_valid if prog else True,
        "milestones": [
            {
                "index": i,
                "spec": spec,
                "reached_at": prog.reached_at[i],
                "counted": i < prog.counted,
            }
            for i, spec in enumerate(contract.milestones)
        ]
        if prog
        else [],
    }
    if prog and prog.reason:
        evidence["trace_invalid_reason"] = prog.reason
    if explain:
        evidence["before_hash"] = hash_state(rollout.before)
        evidence["after_hash"] = hash_state(rollout.after)
        evidence["all_changes"] = diff(rollout.before, rollout.after)["changes"]
    if log is not None:
        log.info(
            "verdict",
            task_id=contract.id,
            success=success,
            side_effects=len(side_effects),
            false_complete=false_complete,
            progress=progress,
            reward=reward,
            goal_held_before=goal_held_before,
            before_hash=hash_state(rollout.before),
            after_hash=hash_state(rollout.after),
            judge_version=JUDGE_CONTRACT_VERSION,
        )
    return Verdict(
        task_id=contract.id,
        success=success,
        progress=progress,
        side_effects=side_effects,
        false_complete=false_complete,
        reward=reward,
        evidence=evidence,
    )


def _path_exists(state: Any, path: list) -> bool:
    cur = state
    for seg in path:
        if isinstance(cur, dict) and isinstance(seg, str) and seg in cur:
            cur = cur[seg]
        elif isinstance(cur, list) and isinstance(seg, int) and not isinstance(seg, bool):
            if not 0 <= seg < len(cur):
                return False
            cur = cur[seg]
        else:
            return False
    return True
