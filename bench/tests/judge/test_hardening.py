"""Judge hardening: every relaxation a model could exploit, and proof that every matcher and
protected subtree in a task is load-bearing (weakening it lets an incorrect transcript through)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from rtlenv.judge import JUDGE_CONTRACT_VERSION, Rollout, Verdict, judge, parse
from rtlenv.logging import get_logger
from rtlenv.task.schema import TaskContractError, validate_task

FIX = json.loads(
    (Path(__file__).parent / "fixtures" / "commerce-states.json").read_text(encoding="utf-8")
)
IDS, SEED, AFTER_ADD, AFTER_COUPON = (
    FIX["ids"],
    FIX["states"]["seed"],
    FIX["states"]["afterAdd"],
    FIX["states"]["afterCoupon"],
)
LINE = IDS["lineId"]
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
        ["coupons", "WELCOME10", "uses"],
    ],
}


def mutate(base: dict, fn) -> dict:
    s = copy.deepcopy(base)
    fn(s)
    return s


# one incorrect transcript per goal matcher (index) and per protected subtree (index)
INCORRECT_PER_GOAL = [
    mutate(
        AFTER_COUPON,
        lambda s: s["cart"]["lines"].__setitem__(
            "l00099", {**s["cart"]["lines"][LINE], "id": "l00099", "variantId": IDS["sibling"]}
        ),
    ),
    mutate(
        AFTER_COUPON, lambda s: s["cart"]["lines"][LINE].__setitem__("variantId", IDS["sibling"])
    ),
    mutate(AFTER_COUPON, lambda s: s["cart"]["lines"][LINE].__setitem__("quantity", 3)),
    mutate(AFTER_COUPON, lambda s: s["cart"].__setitem__("couponCode", "SAVE20")),
    mutate(AFTER_COUPON, lambda s: s["cart"]["totals"]["discount"].__setitem__("minor", 1)),
]
INCORRECT_PER_SUBTREE = [
    mutate(
        AFTER_COUPON, lambda s: next(iter(s["orders"].values())).__setitem__("status", "cancelled")
    ),
    mutate(AFTER_COUPON, lambda s: s["addresses"]["a001"].__setitem__("houseNumber", "999")),
    mutate(AFTER_COUPON, lambda s: s["customer"].__setitem__("loyaltyPoints", 0)),
    mutate(AFTER_COUPON, lambda s: s["inventory"][IDS["variantId"]].__setitem__("available", 999)),
    mutate(
        AFTER_COUPON,
        lambda s: s["saved"].__setitem__(
            "sv0001", {"id": "sv0001", "variantId": IDS["sibling"], "quantity": 1}
        ),
    ),
    mutate(AFTER_COUPON, lambda s: s["coupons"]["WELCOME10"].__setitem__("uses", 1)),
]
ALWAYS_TRUE = {"kind": "exists", "path": ["cart"]}


def roll(after: dict, done: bool = True) -> Rollout:
    return Rollout(before=SEED, after=after, trace=[], declared_done=done)


@pytest.mark.parametrize("i", range(len(TASK["goal_matchers"])))
def test_every_goal_matcher_is_load_bearing(i: int) -> None:
    """Weaken matcher i to always-true: the transcript that only matcher i refuses must now pass."""
    assert judge(TASK, roll(INCORRECT_PER_GOAL[i])).success is False
    weakened = {
        **TASK,
        "goal_matchers": [
            ALWAYS_TRUE if j == i else m for j, m in enumerate(TASK["goal_matchers"])
        ],
    }
    assert judge(weakened, roll(INCORRECT_PER_GOAL[i])).success is True, (
        f"matcher {i} is not load-bearing"
    )


@pytest.mark.parametrize("i", range(len(TASK["unchanged_subtrees"])))
def test_every_protected_subtree_is_load_bearing(i: int) -> None:
    """Drop subtree i from the protected list: the side-effect transcript for it must now pass."""
    assert judge(TASK, roll(INCORRECT_PER_SUBTREE[i])).success is False
    weakened = {
        **TASK,
        "unchanged_subtrees": [p for j, p in enumerate(TASK["unchanged_subtrees"]) if j != i],
    }
    assert judge(weakened, roll(INCORRECT_PER_SUBTREE[i])).success is True, (
        f"subtree {i} is not load-bearing"
    )


def test_protected_subtree_that_does_not_exist_in_setup_is_refused() -> None:
    """A typo in unchanged_subtrees would silently protect nothing. The judge refuses it by name."""
    typo = {**TASK, "unchanged_subtrees": [*TASK["unchanged_subtrees"], ["ordrs"]]}
    with pytest.raises(TaskContractError, match=r"ordrs"):
        judge(typo, roll(AFTER_COUPON))


def test_equality_is_strict_about_json_types() -> None:
    """Python's == says 1 == True and 1 == 1.0; JSON does not. The judge must not either."""
    assert (
        parse({"kind": "field_equals", "path": ["a"], "expected": 1}).evaluate({}, {"a": True}).ok
        is False
    )
    assert (
        parse({"kind": "field_equals", "path": ["a"], "expected": {"x": 1}})
        .evaluate({}, {"a": {"x": True}})
        .ok
        is False
    )
    assert (
        parse({"kind": "field_equals", "path": ["a"], "expected": [0]})
        .evaluate({}, {"a": [False]})
        .ok
        is False
    )
    moved = parse({"kind": "unchanged", "subtrees": [["a"]]}).evaluate(
        {"a": {"flag": 1}}, {"a": {"flag": True}}
    )
    assert moved.ok is False
    assert (
        parse({"kind": "count_is", "path": ["a"], "expected": 1}).evaluate({}, {"a": {"k": 1}}).ok
        is True
    )


def test_verdict_round_trips_fractional_rewards_exactly() -> None:
    v = Verdict(
        task_id="t",
        success=False,
        progress=0.6,
        side_effects=[],
        false_complete=True,
        reward=-0.25,
        evidence={"z": 1, "a": [1.5]},
    )
    text = v.to_json()
    again = Verdict.from_dict(json.loads(text))
    assert again == v
    assert again.to_json() == text
    assert json.loads(text)["progress"] == 0.6 and json.loads(text)["reward"] == -0.25
    assert list(json.loads(text)) == [
        "task_id",
        "success",
        "progress",
        "side_effects",
        "false_complete",
        "reward",
        "evidence",
    ]


def test_verdict_carries_the_judge_contract_version() -> None:
    v = judge(TASK, roll(AFTER_COUPON))
    assert v.evidence["judge_version"] == JUDGE_CONTRACT_VERSION
    assert JUDGE_CONTRACT_VERSION == "1"


def test_judge_logs_each_verdict_with_run_id_seed_task_id_and_hashes() -> None:
    records: list[dict] = []
    log = get_logger(
        "judge",
        run_id="run-7",
        seed=42,
        sink=records.append,
        clock=lambda: __import__("datetime").datetime(
            2026, 9, 16, tzinfo=__import__("datetime").UTC
        ),
    )
    judge(TASK, roll(INCORRECT_PER_SUBTREE[0]), log=log)
    assert len(records) == 1
    r = records[0]
    assert (
        r["run_id"] == "run-7"
        and r["seed"] == 42
        and r["task_id"] == TASK["id"]
        and r["component"] == "judge"
    )
    assert r["success"] is False and r["side_effects"] == 1 and r["false_complete"] is True
    assert (
        len(r["before_hash"]) == 64
        and len(r["after_hash"]) == 64
        and r["before_hash"] != r["after_hash"]
    )
    assert r["level"] == "info"


def test_public_api_is_explicit() -> None:
    import rtlenv.judge as api

    assert set(api.__all__) >= {
        "judge",
        "Rollout",
        "Verdict",
        "parse",
        "KINDS",
        "MatcherSpecError",
        "JUDGE_CONTRACT_VERSION",
    }
    assert validate_task(TASK).id == TASK["id"]
