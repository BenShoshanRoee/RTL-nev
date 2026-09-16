"""State-diff judge core. The judge is security-critical: every test here is a way a model could
collect reward without doing the work, and the judge must refuse it."""

from __future__ import annotations

import copy
import json
import statistics
import time
from pathlib import Path

import pytest
from rtlenv.domain_protocol import money
from rtlenv.judge.core import Rollout, judge
from rtlenv.judge.reward import DEFAULT_WEIGHTS
from rtlenv.judge.verdict import Verdict
from rtlenv.task.schema import TaskContractError, validate_task

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "commerce-states.json").read_text(encoding="utf-8")
)
IDS = FIX["ids"]
SEED = FIX["states"]["seed"]
AFTER_ADD = FIX["states"]["afterAdd"]
AFTER_COUPON = FIX["states"]["afterCoupon"]
TRACE = FIX["trace_add_and_coupon"]
LINE = IDS["lineId"]

# Task: "add two units of variant v0001 to the cart and apply WELCOME10". Everything else stays.
TASK = {
    "id": "he.commerce.cart.add_two_apply_welcome10",
    "setup": {"domain": "commerce", "seed": 42},
    "goal_matchers": [
        {"kind": "count_is", "path": ["cart", "lines"], "expected": 1},
        {
            "kind": "field_equals",
            "path": ["cart", "lines", LINE, "variantId"],
            "expected": IDS["variantId"],
        },
        {"kind": "field_equals", "path": ["cart", "lines", LINE, "quantity"], "expected": 2},
        {"kind": "field_equals", "path": ["cart", "couponCode"], "expected": "WELCOME10"},
        {
            "kind": "money_equals",
            "path": ["cart", "totals", "discount"],
            "minor": AFTER_COUPON["cart"]["totals"]["discount"]["minor"],
            "currency": "ILS",
        },
    ],
    "unchanged_subtrees": [
        ["orders"],
        ["addresses"],
        ["customer"],
        ["inventory"],
        ["saved"],
        ["returns"],
        ["paymentMethods"],
        ["coupons", "WELCOME10", "uses"],
    ],
}


def rollout(after: dict, *, declared_done: bool = True, trace: list | None = None) -> Rollout:
    return Rollout(
        before=SEED,
        after=after,
        trace=trace if trace is not None else TRACE,
        declared_done=declared_done,
    )


def mutate(base: dict, fn) -> dict:
    s = copy.deepcopy(base)
    fn(s)
    return s


def test_correct_transcript_succeeds() -> None:
    v = judge(TASK, rollout(AFTER_COUPON))
    assert v.success is True
    assert v.side_effects == []
    assert v.false_complete is False
    assert v.reward == 1.0 and v.progress == 1.0
    assert v.evidence["goal_held_before"] is False
    assert all(r["ok"] for r in v.evidence["goal"])


INCORRECT = {
    "no_coupon_applied": lambda: AFTER_ADD,
    "wrong_coupon": lambda: mutate(
        AFTER_COUPON, lambda s: s["cart"].__setitem__("couponCode", "SAVE20")
    ),
    "wrong_quantity": lambda: mutate(
        AFTER_COUPON, lambda s: s["cart"]["lines"][LINE].__setitem__("quantity", 3)
    ),
    "wrong_variant_sibling": lambda: mutate(
        AFTER_COUPON, lambda s: s["cart"]["lines"][LINE].__setitem__("variantId", IDS["sibling"])
    ),
    "second_line_added": lambda: mutate(
        AFTER_COUPON,
        lambda s: s["cart"]["lines"].__setitem__(
            "l00099", {**s["cart"]["lines"][LINE], "id": "l00099", "variantId": IDS["sibling"]}
        ),
    ),
    "discount_tampered": lambda: mutate(
        AFTER_COUPON,
        lambda s: s["cart"]["totals"]["discount"].__setitem__(
            "minor", s["cart"]["totals"]["discount"]["minor"] + 1
        ),
    ),
    "goal_plus_order_cancelled": lambda: mutate(
        AFTER_COUPON, lambda s: next(iter(s["orders"].values())).__setitem__("status", "cancelled")
    ),
    "goal_plus_address_edited": lambda: mutate(
        AFTER_COUPON, lambda s: s["addresses"]["a001"].__setitem__("houseNumber", "999")
    ),
    "goal_plus_inventory_restocked": lambda: mutate(
        AFTER_COUPON, lambda s: s["inventory"][IDS["variantId"]].__setitem__("available", 999)
    ),
    "goal_plus_loyalty_changed": lambda: mutate(
        AFTER_COUPON, lambda s: s["customer"].__setitem__("loyaltyPoints", 0)
    ),
    "goal_plus_item_saved": lambda: mutate(
        AFTER_COUPON,
        lambda s: s["saved"].__setitem__(
            "sv0001", {"id": "sv0001", "variantId": IDS["sibling"], "quantity": 1}
        ),
    ),
    "goal_plus_coupon_uses_bumped": lambda: mutate(
        AFTER_COUPON, lambda s: s["coupons"]["WELCOME10"].__setitem__("uses", 1)
    ),
    "nothing_done_declared_done": lambda: SEED,
    "empty_cart_with_coupon": lambda: mutate(
        AFTER_COUPON, lambda s: s["cart"].__setitem__("lines", {})
    ),
}


@pytest.mark.parametrize("name", sorted(INCORRECT))
def test_incorrect_transcripts_fail(name: str) -> None:
    v = judge(TASK, rollout(INCORRECT[name]()))
    assert v.success is False, name
    # a failure can earn at most w_progress; success earns 1.0
    assert v.reward <= DEFAULT_WEIGHTS["w_progress"], name
    assert v.reward < judge(TASK, rollout(AFTER_COUPON)).reward, name


@pytest.mark.parametrize(
    "name",
    [
        "goal_plus_order_cancelled",
        "goal_plus_address_edited",
        "goal_plus_inventory_restocked",
        "goal_plus_loyalty_changed",
        "goal_plus_item_saved",
        "goal_plus_coupon_uses_bumped",
    ],
)
def test_side_effects_are_named_by_path(name: str) -> None:
    v = judge(TASK, rollout(INCORRECT[name]()))
    assert v.side_effects, name
    assert all(r["ok"] for r in v.evidence["goal"]), (
        f"{name}: goal itself should hold; the side effect is the failure"
    )
    paths = [tuple(e["path"]) for e in v.side_effects]
    assert any(
        p[0] in {"orders", "addresses", "inventory", "customer", "saved", "coupons"} for p in paths
    ), paths


def test_false_complete_is_flagged_only_when_declared_done_without_success() -> None:
    assert judge(TASK, rollout(SEED, declared_done=True)).false_complete is True
    assert judge(TASK, rollout(SEED, declared_done=False)).false_complete is False
    assert judge(TASK, rollout(AFTER_COUPON, declared_done=True)).false_complete is False


def test_goal_held_before_is_reported_for_trivial_tasks() -> None:
    trivial = {
        **TASK,
        "goal_matchers": [{"kind": "count_is", "path": ["cart", "lines"], "expected": 0}],
    }
    v = judge(trivial, rollout(SEED))
    assert v.evidence["goal_held_before"] is True


def test_task_without_unchanged_subtrees_is_refused_by_name() -> None:
    bad = {k: v for k, v in TASK.items() if k != "unchanged_subtrees"}
    with pytest.raises(TaskContractError, match="unchanged_subtrees"):
        validate_task(bad)
    with pytest.raises(TaskContractError, match="unchanged_subtrees"):
        judge(bad, rollout(AFTER_COUPON))
    with pytest.raises(TaskContractError, match="unchanged_subtrees"):
        validate_task({**TASK, "unchanged_subtrees": []})
    with pytest.raises(TaskContractError, match="goal_matchers"):
        validate_task({**TASK, "goal_matchers": []})
    with pytest.raises(TaskContractError, match="inside"):
        validate_task({**TASK, "unchanged_subtrees": [["cart"]]})  # goal paths live under cart
    with pytest.raises(TaskContractError, match="setup"):
        validate_task({k: v for k, v in TASK.items() if k != "setup"})


def test_extra_fields_are_allowed_for_2_2_4() -> None:
    t = validate_task({**TASK, "suite": "core", "cheat_surface": ["x"], "difficulty_target": "L2"})
    assert t.id == TASK["id"]


def test_verdict_is_byte_identical_across_runs_and_key_orders() -> None:
    a = judge(TASK, rollout(AFTER_COUPON)).to_json()
    b = judge(TASK, rollout(AFTER_COUPON)).to_json()
    assert a == b
    shuffled_after = json.loads(json.dumps(AFTER_COUPON, sort_keys=True))
    reversed_after = {k: shuffled_after[k] for k in reversed(list(shuffled_after))}
    c = judge(
        TASK, Rollout(before=SEED, after=reversed_after, trace=TRACE, declared_done=True)
    ).to_json()
    assert a == c
    parsed = json.loads(a)
    assert list(parsed) == [
        "task_id",
        "success",
        "progress",
        "side_effects",
        "false_complete",
        "reward",
        "evidence",
    ]
    assert Verdict.from_dict(parsed).to_json() == a


def test_judge_never_reads_agent_text() -> None:
    import inspect

    import rtlenv.judge.core as core

    src = inspect.getsource(core)
    assert "agent_text" not in src and "message" not in src.lower().replace("error message", "")


def test_money_matcher_is_integer_exact() -> None:
    off_by_one = {
        **TASK,
        "goal_matchers": [
            {
                "kind": "money_equals",
                "path": ["cart", "totals", "discount"],
                "minor": AFTER_COUPON["cart"]["totals"]["discount"]["minor"] - 1,
                "currency": "ILS",
            }
        ],
    }
    assert judge(off_by_one, rollout(AFTER_COUPON)).success is False
    assert money(1, "ILS") == {"minor": 1, "currency": "ILS"}


def test_median_latency_under_one_millisecond() -> None:
    r = rollout(AFTER_COUPON)
    judge(TASK, r)  # warm
    samples = []
    for _ in range(300):
        t0 = time.perf_counter_ns()
        judge(TASK, r)
        samples.append(time.perf_counter_ns() - t0)
    median_ms = statistics.median(samples) / 1e6
    assert median_ms < 1.0, f"median {median_ms:.3f} ms"


def test_benchmark_judge(benchmark) -> None:
    r = rollout(AFTER_COUPON)
    v = benchmark(lambda: judge(TASK, r))
    assert v.success is True
