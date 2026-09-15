"""Python mirror of the core-semantic state and money contracts.

The judge (2.2.1) diffs, in Python, states the simulator produced in TypeScript, so the two
implementations must agree byte for byte: canonical JSON, hashes, changesets. The shared
fixture packages/core-semantic/tests/fixtures/state-parity.json is generated here
(``uv run python -m rtlenv.domain_protocol --vectors``) and asserted by both suites.

State rules: JSON only, numbers are integers, entity collections are records keyed by id.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Literal

Json = Any
Path = list[str | int]
Rounding = Literal["half-up", "half-even", "down", "up"]

CURRENCY_EXPONENT: dict[str, int] = {
    "ILS": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "AED": 2,
    "SAR": 2,
    "EGP": 2,
    "QAR": 2,
    "MAD": 2,
    "TRY": 2,
    "JOD": 3,
    "KWD": 3,
    "BHD": 3,
    "OMR": 3,
    "IQD": 3,
    "TND": 3,
    "LYD": 3,
    "JPY": 0,
}
_SAFE = 2**53 - 1


class CurrencyMismatchError(ValueError):
    pass


# ----------------------------------------------------------------------------- money
def _check_int(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) > _SAFE:
        raise ValueError(f"{what} must be a safe integer, got {value!r}")
    return value


def exponent(currency: str) -> int:
    if currency not in CURRENCY_EXPONENT:
        raise ValueError(f"unknown currency {currency!r}")
    return CURRENCY_EXPONENT[currency]


def money(minor: int, currency: str) -> dict[str, Any]:
    exponent(currency)
    return {"minor": _check_int(minor, "minor units"), "currency": currency}


def assert_same_currency(a: dict, b: dict) -> None:
    if a["currency"] != b["currency"]:
        raise CurrencyMismatchError(f"currency mismatch: {a['currency']} vs {b['currency']}")


def add(a: dict, b: dict) -> dict:
    assert_same_currency(a, b)
    return money(a["minor"] + b["minor"], a["currency"])


def subtract(a: dict, b: dict) -> dict:
    assert_same_currency(a, b)
    return money(a["minor"] - b["minor"], a["currency"])


def multiply(a: dict, factor: int) -> dict:
    return money(a["minor"] * _check_int(factor, "factor"), a["currency"])


def scale(a: dict, numerator: int, denominator: int, rounding: Rounding = "half-up") -> dict:
    _check_int(numerator, "numerator")
    _check_int(denominator, "denominator")
    if denominator == 0:
        raise ValueError("scale() denominator must not be zero")
    num = a["minor"] * numerator
    den = denominator
    if den < 0:
        num, den = -num, -den
    negative = num < 0
    q, r = divmod(abs(num), den)
    twice = r * 2
    if rounding == "up":
        round_away = r > 0
    elif rounding == "down":
        round_away = False
    elif rounding == "half-up":
        round_away = twice >= den
    else:
        round_away = twice > den or (twice == den and q % 2 == 1)
    if round_away:
        q += 1
    return money(-q if negative else q, a["currency"])


def compare(a: dict, b: dict) -> int:
    assert_same_currency(a, b)
    return (a["minor"] > b["minor"]) - (a["minor"] < b["minor"])


def equals(a: dict, b: dict) -> bool:
    return a["currency"] == b["currency"] and a["minor"] == b["minor"]


# ----------------------------------------------------------------------------- state
def canonical_json(value: Json) -> str:
    """Sorted keys, compact, unicode kept. Rejects floats and non-JSON values."""
    _reject_floats(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _reject_floats(value: Json) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if abs(value) > _SAFE:
            raise ValueError(f"state numbers must be safe integers, got {value}")
        return
    if isinstance(value, float):
        raise ValueError(f"state numbers must be integers, got {value}")
    if isinstance(value, list):
        for v in value:
            _reject_floats(v)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"object keys must be strings, got {k!r}")
            _reject_floats(v)
        return
    raise ValueError(f"not a JSON value: {type(value).__name__}")


def hash_state(value: Json) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def snapshot(value: Json) -> Json:
    if isinstance(value, list):
        return [snapshot(v) for v in value]
    if isinstance(value, dict):
        return {k: snapshot(v) for k, v in value.items()}
    return value


fork = snapshot


def _path_key(path: Path) -> tuple:
    return tuple(
        (0, p) if isinstance(p, int) and not isinstance(p, bool) else (1, str(p)) for p in path
    )


def _collect(
    before: Json, after: Json, path: Path, out: list[dict], *, b_missing: bool, a_missing: bool
) -> None:
    if b_missing:
        out.append({"path": path, "kind": "added", "after": snapshot(after)})
        return
    if a_missing:
        out.append({"path": path, "kind": "removed", "before": snapshot(before)})
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for k in sorted(set(before) | set(after)):
            _collect(
                before.get(k),
                after.get(k),
                [*path, k],
                out,
                b_missing=k not in before,
                a_missing=k not in after,
            )
        return
    if isinstance(before, list) and isinstance(after, list):
        for i in range(max(len(before), len(after))):
            bi, ai = i < len(before), i < len(after)
            _collect(
                before[i] if bi else None,
                after[i] if ai else None,
                [*path, i],
                out,
                b_missing=not bi,
                a_missing=not ai,
            )
        return
    if canonical_json(before) != canonical_json(after):
        out.append(
            {"path": path, "kind": "changed", "before": snapshot(before), "after": snapshot(after)}
        )


def diff(before: Json, after: Json) -> dict:
    """Leaf-level structured diff, sorted by path. Objects recurse by key, arrays by index."""
    out: list[dict] = []
    _collect(before, after, [], out, b_missing=False, a_missing=False)
    out.sort(key=lambda c: _path_key(c["path"]))
    return {"changes": out}


def is_empty(changeset: dict) -> bool:
    return not changeset["changes"]


def get_path(value: Json, path: Path) -> Json:
    cur = value
    for seg in path:
        if isinstance(cur, dict):
            if not isinstance(seg, str) or seg not in cur:
                return None
            cur = cur[seg]
        elif isinstance(cur, list):
            if not isinstance(seg, int) or seg >= len(cur):
                return None
            cur = cur[seg]
        else:
            return None
    return cur


def _set_path(root: Json, path: Path, value: Json, remove: bool) -> Json:
    if not path:
        return None if remove else value
    cur = root
    for i, seg in enumerate(path[:-1]):
        nxt = (
            cur[seg]
            if (isinstance(cur, dict) and seg in cur)
            or (isinstance(cur, list) and isinstance(seg, int) and seg < len(cur))
            else None
        )
        if not isinstance(nxt, (dict, list)):
            nxt = [] if isinstance(path[i + 1], int) else {}
            cur[seg] = nxt
        cur = nxt
    last = path[-1]
    if isinstance(cur, list):
        if remove:
            del cur[last]
        elif last < len(cur):
            cur[last] = value
        else:
            cur.extend([None] * (last - len(cur)))
            cur.append(value)
    elif remove:
        cur.pop(last, None)
    else:
        cur[last] = value
    return root


def patch(before: Json, changeset: dict) -> Json:
    """Apply a changeset to a copy of `before`. Deepest/last paths first so array removals hold."""
    root = snapshot(before)
    for c in sorted(changeset["changes"], key=lambda c: _path_key(c["path"]), reverse=True):
        root = _set_path(root, c["path"], snapshot(c.get("after")), remove=c["kind"] == "removed")
    return root


def subtree_changes(before: Json, after: Json, subtrees: list[Path]) -> list[dict]:
    """Changes under any of the given subtrees. Empty means those subtrees are untouched."""
    return [
        c
        for c in diff(before, after)["changes"]
        if any(
            len(p) <= len(c["path"]) and all(seg == c["path"][i] for i, seg in enumerate(p))
            for p in subtrees
        )
    ]


# ----------------------------------------------------------------------------- fixture
def parity_vectors() -> dict:
    cases = [
        (
            "identical",
            {"a": {"b": [1, 2, {"c": "x"}]}, "n": None},
            {"a": {"b": [1, 2, {"c": "x"}]}, "n": None},
        ),
        (
            "leaf-changes",
            {"a": 1, "b": {"x": 1, "y": 2}, "l": [1, 2]},
            {"a": 2, "b": {"x": 1, "z": 3}, "l": [1, 2, 3]},
        ),
        ("type-change", {"a": {"x": 1}}, {"a": [1]}),
        (
            "keyed-collection",
            {"k": {"1": {"v": 1}, "2": {"v": 2}}},
            {"k": {"2": {"v": 5}, "3": {"v": 3}}},
        ),
        ("array-shrink", {"arr": [1, [2, 3], 4]}, {"arr": [1, [2]]}),
        (
            "unicode",
            {"שם": "דני", "ar": "مرحبا", "q": 'a"b\\c\n'},
            {"שם": "רות", "ar": "مرحبا", "q": 'a"b\\c\n'},
        ),
        (
            "nested-add-remove",
            {"a": {"b": {"c": 1}}},
            {"a": {"b": {}}, "d": {"e": {"f": [True, False, None]}}},
        ),
        (
            "money-fields",
            {"total": {"minor": 1990, "currency": "ILS"}},
            {"total": {"minor": 2490, "currency": "ILS"}},
        ),
        ("empty-to-full", {}, {"x": {"y": [1, {"z": "q"}]}}),
        (
            "key-order-irrelevant",
            {"z": 1, "a": 2, "m": {"q": 1, "b": 2}},
            {"a": 2, "m": {"b": 2, "q": 1}, "z": 1},
        ),
    ]
    return {
        "generated_by": "uv run python -m rtlenv.domain_protocol --vectors",
        "cases": [
            {
                "name": name,
                "before": before,
                "after": after,
                "changeset": diff(before, after),
                "canonical_before": canonical_json(before),
                "hash_before": hash_state(before),
                "hash_after": hash_state(after),
            }
            for name, before, after in cases
        ],
    }


if __name__ == "__main__":
    if sys.argv[1:] == ["--vectors"]:
        json.dump(parity_vectors(), sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        sys.exit("usage: python -m rtlenv.domain_protocol --vectors")
