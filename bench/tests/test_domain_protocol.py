"""Python mirror of the core-semantic state and money contracts. The fixture is shared with
the TypeScript suite; this module generates it (``python -m rtlenv.domain_protocol --vectors``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rtlenv.domain_protocol import (
    CurrencyMismatchError,
    add,
    canonical_json,
    diff,
    get_path,
    hash_state,
    is_empty,
    money,
    patch,
    scale,
    subtree_changes,
)

FIXTURE = (
    Path(__file__).resolve().parents[2] / "packages/core-semantic/tests/fixtures/state-parity.json"
)
PARITY = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_canonical_json_sorts_keys_keeps_unicode_rejects_floats() -> None:
    assert (
        canonical_json({"b": 1, "a": {"d": "שלום", "c": [1, 2]}})
        == '{"a":{"c":[1,2],"d":"שלום"},"b":1}'
    )
    with pytest.raises(ValueError):
        canonical_json({"x": 1.5})
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    assert hash_state({"a": 1, "b": 2}) == hash_state({"b": 2, "a": 1})


def test_fixture_cases_round_trip() -> None:
    assert len(PARITY["cases"]) >= 8
    for c in PARITY["cases"]:
        assert canonical_json(c["before"]) == c["canonical_before"], c["name"]
        assert hash_state(c["before"]) == c["hash_before"], c["name"]
        assert diff(c["before"], c["after"]) == c["changeset"], c["name"]
        assert patch(c["before"], c["changeset"]) == c["after"], c["name"]


def test_diff_identical_is_empty_and_sorted_leaf_changes() -> None:
    s = {"a": {"b": [1, 2, {"c": "x"}]}, "n": None}
    assert is_empty(diff(s, s))
    cs = diff(
        {"a": 1, "b": {"x": 1, "y": 2}, "l": [1, 2]},
        {"a": 2, "b": {"x": 1, "z": 3}, "l": [1, 2, 3]},
    )
    assert cs["changes"] == [
        {"path": ["a"], "kind": "changed", "before": 1, "after": 2},
        {"path": ["b", "y"], "kind": "removed", "before": 2},
        {"path": ["b", "z"], "kind": "added", "after": 3},
        {"path": ["l", 2], "kind": "added", "after": 3},
    ]
    assert get_path(s, ["a", "b", 2, "c"]) == "x"
    assert get_path(s, ["zz"]) is None
    before = {"k": {"n": 1}, "other": {"n": 1}}
    after = {"k": {"n": 2}, "other": {"n": 1}}
    assert subtree_changes(before, after, [["other"]]) == []
    assert [c["path"] for c in subtree_changes(before, after, [["k"]])] == [["k", "n"]]


def test_money_mirror() -> None:
    assert money(1500, "KWD") == {"minor": 1500, "currency": "KWD"}
    assert add(money(100, "ILS"), money(250, "ILS")) == money(350, "ILS")
    assert scale(money(1005, "ILS"), 17, 100) == money(171, "ILS")
    assert scale(money(1005, "ILS"), 17, 100, "down") == money(170, "ILS")
    assert scale(money(25, "ILS"), 1, 2, "half-even") == money(12, "ILS")
    with pytest.raises(CurrencyMismatchError):
        add(money(1, "ILS"), money(1, "KWD"))
    with pytest.raises(ValueError):
        money(1.5, "ILS")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        money(1, "XXX")
