"""Task schema (2.2.4): the authoring contract layered over the 2.2.1 judge contract.

Every test names a way an author could ship a task the judge would accept but that is
unfit to sell: no cheat surface, a leaf protected instead of a subtree, a description whose
Hebrew and English disagree on their slots, a split the packaging cannot route.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path
from typing import Any

import pytest
import yaml
from rtlenv.task.schema import (
    DIFFICULTIES,
    MIN_CHEAT_SURFACE,
    SPLITS,
    TaskContract,
    TaskContractError,
    TaskDefinition,
    validate_definition,
    validate_task,
)

MINIMAL_2_2_1 = {
    "id": "he.commerce.cart.add_two_apply_welcome10",
    "setup": {"domain": "commerce", "seed": 42},
    "goal_matchers": [{"kind": "field_equals", "path": ["cart", "couponCode"], "expected": "X"}],
    "unchanged_subtrees": [["orders"]],
}


REAL_TASK = (
    Path(__file__).resolve().parents[2]
    / "tasks"
    / "he"
    / "commerce"
    / "cart_add_two_apply_welcome10"
    / "task.yaml"
)


def _real() -> dict[str, Any]:
    return copy.deepcopy(yaml.safe_load(REAL_TASK.read_text(encoding="utf-8")))


def _rejects(task: dict[str, Any], *fragments: str) -> str:
    with pytest.raises(TaskContractError) as info:
        validate_definition(task)
    msg = str(info.value)
    for f in fragments:
        assert f in msg, f"expected {f!r} in error: {msg}"
    return msg


# ---------- extends, never redefines


def test_2_2_1_minimal_contract_still_validates_for_the_judge() -> None:
    c = validate_task(MINIMAL_2_2_1)
    assert isinstance(c, TaskContract)
    assert c.id == MINIMAL_2_2_1["id"] and c.setup.seed == 42 and c.setup.state_ref is None


def test_judge_contract_does_not_demand_authoring_fields() -> None:
    # The judge consumes the minimal contract; authoring fields are the registry's concern.
    validate_task(MINIMAL_2_2_1)


def test_authoring_contract_rejects_the_bare_judge_contract_by_naming_the_missing_field() -> None:
    _rejects(MINIMAL_2_2_1, "suite")


def test_real_task_validates_and_every_field_is_populated() -> None:
    d = validate_definition(_real())
    assert isinstance(d, TaskDefinition)
    assert d.id == "he.commerce.cart.add_two_apply_welcome10"
    assert d.language == "he"
    assert d.suite == "commerce"
    assert d.domain == "commerce"
    assert d.split == "train"
    assert d.difficulty_target == "L1"
    assert d.slots == ("product",)
    assert set(d.description_template) >= {"he", "en"}
    assert len(d.cheat_surface) >= MIN_CHEAT_SURFACE
    assert d.version == 1 and d.deprecated is False
    assert d.contract.setup.state_ref == "commerce/seed-42"
    assert d.fixtures == {}


def test_definition_is_immutable() -> None:
    d = validate_definition(_real())
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.split = "test"  # type: ignore[misc]


def test_unknown_fields_pass_through_for_later_extension() -> None:
    t = _real()
    t["pathology"] = {"injectors": ["hebrew-truncation"], "behaviours": ["avoid"]}
    d = validate_definition(t)
    assert d.extra["pathology"]["injectors"] == ["hebrew-truncation"]


# ---------- mandatory fields


def test_missing_unchanged_subtrees_is_rejected_by_name() -> None:
    t = _real()
    del t["unchanged_subtrees"]
    _rejects(t, "unchanged_subtrees")
    with pytest.raises(TaskContractError, match="unchanged_subtrees"):
        validate_task(t)


@pytest.mark.parametrize(
    "value",
    [None, [], "prose", ["", "b", "c"], ["a", "b"], ["a", 1, "c"], ["a", "a", "c"]],
    ids=["missing", "empty", "string", "blank-entry", "too-few", "non-string", "duplicate"],
)
def test_cheat_surface_must_be_a_list_of_at_least_three_distinct_lines(value: Any) -> None:
    t = _real()
    if value is None:
        del t["cheat_surface"]
    else:
        t["cheat_surface"] = value
    _rejects(t, "cheat_surface")


def test_cheat_surface_minimum_matches_the_fixture_minimum() -> None:
    # Three plausibly-wrong fixtures each target one cheat; fewer cheats means untested fixtures.
    assert MIN_CHEAT_SURFACE == 3


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("suite", None, "suite"),
        ("suite", "Commerce", "suite"),
        ("suite", "core", "suite"),  # must equal the id's second segment
        ("domain", None, "domain"),
        ("domain", "insurance", "setup.domain"),
        ("split", None, "split"),
        ("split", "validation", "split"),
        ("difficulty_target", None, "difficulty_target"),
        ("difficulty_target", "L5", "difficulty_target"),
        ("difficulty_target", "l1", "difficulty_target"),
        ("difficulty_target", 1, "difficulty_target"),
    ],
)
def test_mandatory_scalar_fields_are_checked_by_name(field: str, value: Any, fragment: str) -> None:
    t = _real()
    if value is None:
        del t[field]
    else:
        t[field] = value
    _rejects(t, fragment)


def test_split_and_difficulty_enums_are_the_documented_ones() -> None:
    assert SPLITS == ("train", "test", "pathology", "calibration")
    assert DIFFICULTIES == ("L1", "L2", "L3", "L4")


# ---------- ids


@pytest.mark.parametrize(
    "task_id",
    [
        "he.commerce.add_two",  # three segments
        "he.commerce.cart.Add_Two",  # uppercase
        "hebrew.commerce.cart.add_two",  # language must be two letters
        "he.commerce.cart.add-two",  # hyphen
        "he.commerce.cart.",  # empty segment
        "he.commerce.cart.2fast",  # segment must start with a letter
        "",
    ],
)
def test_id_must_be_lang_suite_area_name_in_snake_case(task_id: str) -> None:
    t = _real()
    t["id"] = task_id
    _rejects(t, "id")


def test_id_may_have_more_than_four_segments_for_deeper_areas() -> None:
    t = _real()
    t["id"] = "he.commerce.checkout.coupon.then_variant_change"
    assert validate_definition(t).id == t["id"]


# ---------- description template


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        (None, "description_template"),
        ("prose", "description_template"),
        ({}, "description_template"),
        ({"en": "Add {product}"}, "he"),  # the task's own language is mandatory
        ({"he": "", "en": "Add {product}"}, "description_template.he"),
        ({"he": "הוסיפו {product}", "en": "Add {item}"}, "slots"),
        ({"he": "הוסיפו {product", "en": "Add {product}"}, "description_template.he"),
        ({"he": "הוסיפו {0}", "en": "Add {0}"}, "slot"),
        ({"he": "הוסיפו {product.name}", "en": "Add {product.name}"}, "slot"),
        ({"he": "הוסיפו {product}", "EN": "Add {product}"}, "language"),
        ({"he": "הוסיפו {product}", "en": 5}, "description_template.en"),
    ],
)
def test_description_template_is_per_language_with_identical_identifier_slots(
    value: Any, fragment: str
) -> None:
    t = _real()
    if value is None:
        del t["description_template"]
    else:
        t["description_template"] = value
    _rejects(t, fragment)


def test_description_without_slots_is_legal_and_reports_no_slots() -> None:
    t = _real()
    t["description_template"] = {"he": "רוקנו את העגלה", "en": "Empty the cart"}
    assert validate_definition(t).slots == ()


# ---------- protect subtrees, not leaves


def test_protected_path_deeper_than_a_record_is_rejected_citing_finding_1() -> None:
    t = _real()
    t["unchanged_subtrees"].append(["coupons", "ONESHOT", "uses"])
    msg = _rejects(t, "unchanged_subtrees", "subtree")
    assert "finding #1" in msg


def test_protected_singleton_field_at_depth_two_is_allowed() -> None:
    t = _real()
    t["unchanged_subtrees"] = [p for p in t["unchanged_subtrees"] if p != ["customer"]]
    t["unchanged_subtrees"].append(["customer", "loyaltyPoints"])
    assert ["customer", "loyaltyPoints"] in validate_definition(t).contract.unchanged_subtrees


# ---------- fixtures minimums


def test_fixture_minimums_may_be_raised_but_never_lowered() -> None:
    t = _real()
    t["fixtures"] = {"plausibly_wrong": 10}
    assert validate_definition(t).fixtures == {"plausibly_wrong": 10}
    t["fixtures"] = {"plausibly_wrong": 2}
    _rejects(t, "fixtures.plausibly_wrong", "3")
    t["fixtures"] = {"correct": 0}
    _rejects(t, "fixtures.correct")


@pytest.mark.parametrize(
    "value", [{"wrong_kind": 3}, {"correct": "1"}, {"correct": True}, ["correct"], 5]
)
def test_fixture_minimums_shape_is_checked(value: Any) -> None:
    t = _real()
    t["fixtures"] = value
    _rejects(t, "fixtures")


# ---------- version and deprecation


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.0])
def test_version_is_a_positive_integer(value: Any) -> None:
    t = _real()
    t["version"] = value
    _rejects(t, "version")


def test_version_defaults_to_one_and_is_read_when_present() -> None:
    t = _real()
    t.pop("version", None)
    assert validate_definition(t).version == 1
    t["version"] = 3
    assert validate_definition(t).version == 3


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_deprecated_must_be_a_boolean(value: Any) -> None:
    t = _real()
    t["deprecated"] = value
    _rejects(t, "deprecated")


def test_deprecated_true_is_accepted_and_reported() -> None:
    t = _real()
    t["deprecated"] = True
    assert validate_definition(t).deprecated is True


# ---------- setup.state_ref


@pytest.mark.parametrize("value", ["", 42, ["commerce/seed-42"], "../secrets"])
def test_state_ref_when_present_is_a_plain_relative_name(value: Any) -> None:
    t = _real()
    t["setup"]["state_ref"] = value
    _rejects(t, "setup.state_ref")
    with pytest.raises(TaskContractError, match="setup.state_ref"):
        validate_task(t)


def test_state_ref_is_mandatory_for_an_authored_task() -> None:
    t = _real()
    del t["setup"]["state_ref"]
    validate_task(t)  # the judge does not need it
    _rejects(t, "setup.state_ref")


# ---------- determinism of validation


def test_validation_is_pure_and_does_not_mutate_its_input() -> None:
    t = _real()
    before = copy.deepcopy(t)
    validate_definition(t)
    assert t == before
