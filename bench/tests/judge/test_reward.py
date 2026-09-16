"""Partial credit and reward shaping. Every case is a way partial credit could be gamed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rtlenv.domain_protocol import diff, hash_state
from rtlenv.judge import Rollout, judge
from rtlenv.judge.progress import compute_progress
from rtlenv.judge.reward import DEFAULT_WEIGHTS, RewardConfigError, compute_reward, validate_weights
from rtlenv.rng import Rng
from rtlenv.task.schema import TaskContractError

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "commerce-states.json").read_text(encoding="utf-8")
)
SEED, AFTER_COUPON, TRACE = (
    FIX["states"]["seed"],
    FIX["states"]["afterCoupon"],
    FIX["trace_add_and_coupon"],
)
LINE = FIX["ids"]["lineId"]


def make_trace(states: list[dict]) -> list[dict]:
    """A consistent trace through the given states (hashes and changesets computed honestly)."""
    return [
        {
            "op": f"step{i}",
            "params": {},
            "beforeHash": hash_state(a),
            "afterHash": hash_state(b),
            "changes": diff(a, b),
        }
        for i, (a, b) in enumerate(zip(states, states[1:], strict=False))
    ]


# Toy world: five milestones a, b, c, d, e become true one after another.
def toy(*flags: str) -> dict:
    return {"flags": {f: (f in flags) for f in "abcde"}, "other": {"x": 1}}


MILESTONES = [{"kind": "field_equals", "path": ["flags", f], "expected": True} for f in "abcde"]
TOY_TASK = {
    "id": "toy.milestones",
    "setup": {"domain": "toy", "seed": 1},
    "goal_matchers": [{"kind": "field_equals", "path": ["flags", "e"], "expected": True}],
    "unchanged_subtrees": [["other"]],
    "milestones": MILESTONES,
}


def path_through(*sets: tuple[str, ...]) -> list[dict]:
    return [toy()] + [toy(*s) for s in sets]


def test_three_of_five_milestones_scores_strictly_between_failure_and_success() -> None:
    fail_states = [toy()]
    three_states = path_through(("a",), ("a", "b"), ("a", "b", "c"))
    full_states = path_through(
        ("a",), ("a", "b"), ("a", "b", "c"), ("a", "b", "c", "d"), ("a", "b", "c", "d", "e")
    )
    fail = judge(
        TOY_TASK,
        Rollout(before=fail_states[0], after=fail_states[-1], trace=[], declared_done=False),
    )
    three = judge(
        TOY_TASK,
        Rollout(
            before=three_states[0],
            after=three_states[-1],
            trace=make_trace(three_states),
            declared_done=False,
        ),
    )
    full = judge(
        TOY_TASK,
        Rollout(
            before=full_states[0],
            after=full_states[-1],
            trace=make_trace(full_states),
            declared_done=True,
        ),
    )
    assert three.progress == pytest.approx(0.6)
    assert fail.reward < three.reward < full.reward
    assert full.success and full.reward == 1.0
    assert not three.success and fail.progress == 0.0


def test_out_of_order_milestones_do_not_inflate_progress() -> None:
    # c first, then a, then b: a and b in order (steps 2, 3); c came earlier -> not counted
    states = path_through(("c",), ("a", "c"), ("a", "b", "c"))
    r = compute_progress(MILESTONES, states[0], states[-1], make_trace(states))
    assert r.trace_valid
    assert r.reached_at == [2, 3, 1, None, None]
    assert r.counted == 2 and r.rate == pytest.approx(0.4)
    # e first (the goal), then the rest: the in-order prefix a..d counts, e is out of order
    states = path_through(
        ("e",), ("a", "e"), ("a", "b", "e"), ("a", "b", "c", "e"), ("a", "b", "c", "d", "e")
    )
    r = compute_progress(MILESTONES, states[0], states[-1], make_trace(states))
    assert r.reached_at == [2, 3, 4, 5, 1] and r.counted == 4
    # fully reversed: only the first milestone can count
    states = path_through(
        ("e",), ("d", "e"), ("c", "d", "e"), ("b", "c", "d", "e"), ("a", "b", "c", "d", "e")
    )
    r = compute_progress(MILESTONES, states[0], states[-1], make_trace(states))
    assert r.counted == 1 and r.rate == pytest.approx(0.2)


def test_milestone_that_stops_holding_still_counts_if_reached_in_order() -> None:
    # transient milestones (item in cart, then checkout empties the cart) must count via the trace
    states = [toy(), toy("a"), toy("a", "b"), toy("b")]  # a reached at 1, then lost
    r = compute_progress(MILESTONES[:2], states[0], states[-1], make_trace(states))
    assert r.reached_at == [1, 2] and r.counted == 2 and r.rate == 1.0


def test_without_a_trace_only_final_state_counts_and_order_is_unverifiable() -> None:
    r = compute_progress(MILESTONES, toy(), toy("a", "b", "d"), [])
    assert r.trace_valid and r.reached_at == [0, 0, None, 0, None]
    assert r.counted == 2, "prefix a, b; d after a gap does not count"


def test_tampered_trace_yields_no_partial_credit() -> None:
    states = path_through(("a",), ("a", "b"), ("a", "b", "c"))
    trace = make_trace(states)
    forged = json.loads(json.dumps(trace))
    forged[1]["changes"]["changes"].append(
        {"path": ["flags", "e"], "kind": "changed", "before": False, "after": True}
    )
    r = compute_progress(MILESTONES, states[0], states[-1], forged)
    assert r.trace_valid is False and r.rate == 0.0 and "hash" in (r.reason or "")
    v = judge(
        TOY_TASK, Rollout(before=states[0], after=states[-1], trace=forged, declared_done=False)
    )
    assert v.progress == 0.0 and v.evidence["trace_valid"] is False
    broken_chain = json.loads(json.dumps(trace))
    broken_chain[2]["beforeHash"] = "0" * 64
    assert compute_progress(MILESTONES, states[0], states[-1], broken_chain).trace_valid is False


def test_false_complete_always_scores_below_any_honest_failure() -> None:
    worst_honest = min(
        compute_reward(success=False, progress=p, side_effects=s, false_complete=False)
        for p in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        for s in range(0, 6)
    )
    best_false = max(
        compute_reward(success=False, progress=p, side_effects=s, false_complete=True)
        for p in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        for s in range(0, 6)
    )
    assert best_false < worst_honest or best_false < compute_reward(
        success=False, progress=0.0, side_effects=0, false_complete=False
    )
    # the plan's literal statement: same progress, declared done vs honest -> strictly lower
    for p in (0.0, 0.4, 1.0):
        assert compute_reward(
            success=False, progress=p, side_effects=0, false_complete=True
        ) < compute_reward(success=False, progress=p, side_effects=0, false_complete=False)
    # and a false-complete with full milestones scores below an honest failure with none
    assert compute_reward(
        success=False, progress=1.0, side_effects=0, false_complete=True
    ) < compute_reward(success=False, progress=0.0, side_effects=0, false_complete=False)


def test_reward_never_exits_the_documented_range_over_10000_random_verdicts() -> None:
    rng = Rng(2022, "reward")
    lo, hi = DEFAULT_WEIGHTS["min"], DEFAULT_WEIGHTS["max"]
    for _ in range(10_000):
        success = rng.bool(0.3)
        r = compute_reward(
            success=success,
            progress=1.0 if success else rng.int(0, 11) / 10,
            side_effects=0 if success else rng.int(0, 50),
            false_complete=(not success) and rng.bool(0.5),
        )
        assert lo <= r <= hi


def test_success_outranks_every_failure_even_via_shortcut() -> None:
    shortcut = compute_reward(success=True, progress=0.0, side_effects=0, false_complete=False)
    best_failure = compute_reward(success=False, progress=1.0, side_effects=0, false_complete=False)
    assert shortcut > best_failure
    assert (
        compute_reward(success=True, progress=1.0, side_effects=0, false_complete=False)
        == DEFAULT_WEIGHTS["max"]
    )


def test_side_effects_cost_per_effect_up_to_a_cap() -> None:
    base = compute_reward(success=False, progress=1.0, side_effects=0, false_complete=False)
    one = compute_reward(success=False, progress=1.0, side_effects=1, false_complete=False)
    many = compute_reward(success=False, progress=1.0, side_effects=100, false_complete=False)
    assert one < base and many <= one and many >= DEFAULT_WEIGHTS["min"]


def test_weights_are_validated() -> None:
    validate_weights(DEFAULT_WEIGHTS)
    with pytest.raises(RewardConfigError, match="w_false"):
        validate_weights({**DEFAULT_WEIGHTS, "w_false": DEFAULT_WEIGHTS["w_progress"] - 0.01})
    with pytest.raises(RewardConfigError, match="negative"):
        validate_weights({**DEFAULT_WEIGHTS, "w_side": -1})
    with pytest.raises(RewardConfigError, match="max"):
        validate_weights({**DEFAULT_WEIGHTS, "max": 0.5})
    with pytest.raises(RewardConfigError, match="unknown"):
        validate_weights({**DEFAULT_WEIGHTS, "w_bonus": 1})


def test_task_level_weights_override_defaults_and_are_validated_by_the_judge() -> None:
    task = {**TOY_TASK, "reward": {"w_success": 0.55, "w_progress": 0.45, "w_false": 0.45}}
    states = path_through(
        ("a",), ("a", "b"), ("a", "b", "c"), ("a", "b", "c", "d"), ("a", "b", "c", "d", "e")
    )
    v = judge(
        task,
        Rollout(before=states[0], after=states[-1], trace=make_trace(states), declared_done=True),
    )
    assert v.reward == 1.0 and v.evidence["reward_weights"]["w_success"] == 0.55
    with pytest.raises(TaskContractError, match="reward"):
        judge(
            {**TOY_TASK, "reward": {"w_false": 0.0}},
            Rollout(before=states[0], after=states[-1], trace=[], declared_done=False),
        )


def test_milestones_on_the_real_commerce_trace() -> None:
    task = {
        "id": "he.commerce.cart.add_two_apply_welcome10",
        "setup": {"domain": "commerce", "seed": 42},
        "goal_matchers": [
            {"kind": "field_equals", "path": ["cart", "couponCode"], "expected": "WELCOME10"}
        ],
        "unchanged_subtrees": [["orders"], ["inventory"]],
        "milestones": [
            {"kind": "field_equals", "path": ["cart", "lines", LINE, "quantity"], "expected": 2},
            {"kind": "field_equals", "path": ["cart", "couponCode"], "expected": "WELCOME10"},
        ],
    }
    v = judge(task, Rollout(before=SEED, after=AFTER_COUPON, trace=TRACE, declared_done=True))
    assert v.success and v.progress == 1.0 and v.evidence["trace_valid"] is True
    assert [m["reached_at"] for m in v.evidence["milestones"]] == [1, 2]
    only_add = judge(
        task,
        Rollout(before=SEED, after=FIX["states"]["afterAdd"], trace=TRACE[:1], declared_done=False),
    )
    assert not only_add.success and only_add.progress == 0.5 and 0 < only_add.reward < v.reward


def test_milestone_specs_are_validated_like_goal_matchers() -> None:
    from rtlenv.task.schema import TaskContractError

    with pytest.raises(TaskContractError, match="milestones"):
        judge(
            {**TOY_TASK, "milestones": [{"kind": "nope"}]},
            Rollout(before=toy(), after=toy(), trace=[], declared_done=False),
        )
    with pytest.raises(TaskContractError, match="milestones"):
        judge(
            {
                **TOY_TASK,
                "milestones": [{"kind": "field_equals", "path": ["other", "x"], "expected": 1}],
            },
            Rollout(before=toy(), after=toy(), trace=[], declared_done=False),
        )


# ---- hardening: free credit must not exist ------------------------------------------------


def test_milestone_that_already_holds_at_setup_earns_nothing() -> None:
    """'Address selected' already true in the seed is not progress; it is an authoring smell."""
    before = toy("a")  # a already holds
    states = [before, toy("a", "b"), toy("a", "b", "c")]
    r = compute_progress(MILESTONES, before, states[-1], make_trace(states))
    assert r.trace_valid
    assert r.held_before == [0]
    # a is excluded from both numerator and denominator: b, c reached in order out of b..e
    assert r.counted == 2 and r.total == 4 and r.rate == pytest.approx(0.5)
    only_free = compute_progress(MILESTONES[:1], before, before, [])
    assert only_free.counted == 0 and only_free.total == 0 and only_free.rate == 0.0
    assert only_free.reason and "held" in only_free.reason


def test_trivial_instance_pays_zero_even_though_the_goal_holds() -> None:
    before = toy("e")  # goal already satisfied by the seed
    v = judge(TOY_TASK, Rollout(before=before, after=before, trace=[], declared_done=True))
    assert v.success is True  # state truth is untouched
    assert v.reward == 0.0 and v.progress == 0.0
    assert v.evidence["goal_held_before"] is True and v.evidence["trivial_instance"] is True
    assert v.false_complete is False


def test_side_effect_penalty_counts_violated_subtrees_not_leaf_changes() -> None:
    task = {**TOY_TASK, "unchanged_subtrees": [["other"], ["extra"]], "milestones": []}
    before = {**toy(), "extra": {"p": 1, "q": 2, "r": 3, "s": 4, "t": 5}}
    one_subtree_many_leaves = {**toy("e"), "extra": {"p": 9, "q": 9, "r": 9, "s": 9, "t": 9}}
    two_subtrees = {
        **toy("e"),
        "extra": {"p": 9, "q": 2, "r": 3, "s": 4, "t": 5},
        "other": {"x": 2},
    }
    a = judge(
        task, Rollout(before=before, after=one_subtree_many_leaves, trace=[], declared_done=False)
    )
    b = judge(task, Rollout(before=before, after=two_subtrees, trace=[], declared_done=False))
    assert len(a.side_effects) == 5 and a.evidence["violated_subtrees"] == [["extra"]]
    assert len(b.side_effects) == 2 and b.evidence["violated_subtrees"] == [["extra"], ["other"]]
    assert a.reward > b.reward, (
        "one damaged subtree must cost less than two, whatever the leaf count"
    )
    assert a.reward == pytest.approx(
        compute_reward(success=False, progress=1.0, side_effects=1, false_complete=False)
    )
