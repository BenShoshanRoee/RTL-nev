from __future__ import annotations

import pytest
from rtlenv.judge.matchers import MatcherSpecError, parse

BEFORE = {
    "a": {
        "n": 1,
        "m": {"minor": 100, "currency": "ILS"},
        "items": {"x": 1, "y": 2},
        "arr": [1, 2, 3],
    },
    "b": 5,
}
AFTER = {
    "a": {
        "n": 3,
        "m": {"minor": 250, "currency": "ILS"},
        "items": {"x": 1, "y": 2, "z": 3},
        "arr": [1, 2, 3, 4],
    },
    "b": 5,
}


def ev(spec: dict, before=BEFORE, after=AFTER) -> bool:
    return parse(spec).evaluate(before, after).ok


def test_field_equals_is_deep_and_exact() -> None:
    assert ev({"kind": "field_equals", "path": ["a", "n"], "expected": 3})
    assert not ev({"kind": "field_equals", "path": ["a", "n"], "expected": "3"})
    assert ev(
        {"kind": "field_equals", "path": ["a", "m"], "expected": {"minor": 250, "currency": "ILS"}}
    )
    assert not ev({"kind": "field_equals", "path": ["a", "m"], "expected": {"minor": 250}})
    assert not ev({"kind": "field_equals", "path": ["a", "missing"], "expected": None})


def test_collection_contains_exactly_is_an_exact_key_set() -> None:
    assert ev(
        {"kind": "collection_contains_exactly", "path": ["a", "items"], "keys": ["z", "y", "x"]}
    )
    assert not ev(
        {"kind": "collection_contains_exactly", "path": ["a", "items"], "keys": ["x", "y"]}
    )
    assert not ev(
        {
            "kind": "collection_contains_exactly",
            "path": ["a", "items"],
            "keys": ["x", "y", "z", "w"],
        }
    )


def test_count_is_records_and_arrays() -> None:
    assert ev({"kind": "count_is", "path": ["a", "items"], "expected": 3})
    assert ev({"kind": "count_is", "path": ["a", "arr"], "expected": 4})
    assert not ev({"kind": "count_is", "path": ["a", "arr"], "expected": 3})
    assert not ev({"kind": "count_is", "path": ["a", "n"], "expected": 1})  # not a collection


def test_money_equals_integer_exact_and_currency_aware() -> None:
    assert ev({"kind": "money_equals", "path": ["a", "m"], "minor": 250, "currency": "ILS"})
    assert not ev({"kind": "money_equals", "path": ["a", "m"], "minor": 250, "currency": "KWD"})
    assert not ev({"kind": "money_equals", "path": ["a", "m"], "minor": 251, "currency": "ILS"})
    with pytest.raises(MatcherSpecError):
        parse({"kind": "money_equals", "path": ["a", "m"], "minor": 2.5, "currency": "ILS"})
    with pytest.raises(MatcherSpecError):
        parse({"kind": "money_equals", "path": ["a", "m"], "minor": 1, "currency": "XXX"})


def test_within_tolerance_is_integers_only_and_refuses_money() -> None:
    assert ev({"kind": "within_tolerance", "path": ["a", "n"], "expected": 4, "tolerance": 1})
    assert not ev({"kind": "within_tolerance", "path": ["a", "n"], "expected": 5, "tolerance": 1})
    with pytest.raises(MatcherSpecError):
        parse({"kind": "within_tolerance", "path": ["a", "n"], "expected": 4.5, "tolerance": 1})
    assert not ev(
        {"kind": "within_tolerance", "path": ["a", "m"], "expected": 250, "tolerance": 5}
    )  # money is never tolerant


def test_unchanged_delta_exists_absent() -> None:
    assert ev({"kind": "unchanged", "subtrees": [["b"]]})
    assert not ev({"kind": "unchanged", "subtrees": [["a", "n"]]})
    assert ev({"kind": "delta_equals", "path": ["a", "n"], "delta": 2})
    assert not ev({"kind": "delta_equals", "path": ["a", "n"], "delta": 1})
    assert ev({"kind": "exists", "path": ["a", "items", "z"]})
    assert ev({"kind": "absent", "path": ["a", "items", "w"]})
    assert not ev({"kind": "absent", "path": ["a", "items", "z"]})


def test_combinators() -> None:
    a = {"kind": "field_equals", "path": ["b"], "expected": 5}
    b = {"kind": "field_equals", "path": ["b"], "expected": 6}
    assert ev({"kind": "all_of", "matchers": [a, {"kind": "exists", "path": ["a"]}]})
    assert not ev({"kind": "all_of", "matchers": [a, b]})
    assert ev({"kind": "any_of", "matchers": [b, a]})
    assert ev({"kind": "not", "matcher": b})
    assert not ev({"kind": "not", "matcher": a})


def test_parse_rejects_unknown_kind_missing_fields_and_bad_paths() -> None:
    with pytest.raises(MatcherSpecError, match="kind"):
        parse({"kind": "contains", "path": ["a"]})
    with pytest.raises(MatcherSpecError, match="path"):
        parse({"kind": "field_equals", "expected": 1})
    with pytest.raises(MatcherSpecError, match="path"):
        parse({"kind": "field_equals", "path": "a.b", "expected": 1})
    with pytest.raises(MatcherSpecError, match="expected"):
        parse({"kind": "count_is", "path": ["a"]})
    with pytest.raises(MatcherSpecError, match="matchers"):
        parse({"kind": "all_of", "matchers": []})


def test_specs_round_trip_and_results_carry_evidence() -> None:
    spec = {"kind": "money_equals", "path": ["a", "m"], "minor": 250, "currency": "ILS"}
    m = parse(spec)
    assert m.to_spec() == spec
    r = m.evaluate(BEFORE, AFTER)
    assert r.ok and r.kind == "money_equals" and r.path == ["a", "m"]
    bad = parse({"kind": "field_equals", "path": ["a", "n"], "expected": 9}).evaluate(BEFORE, AFTER)
    assert not bad.ok and bad.evidence["actual"] == 3 and bad.evidence["expected"] == 9
