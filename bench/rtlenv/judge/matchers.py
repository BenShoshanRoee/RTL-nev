"""Matchers: composable, exact predicates over state trees, declared as JSON specs.

Every matcher is data (``parse(spec)`` / ``to_spec()``) so tasks declare them in YAML and the
meta-test harness can weaken them programmatically. Every matcher is exact by design: there
is no "contains", tolerances are integers only and never apply to money, collections are
exact key sets. A permissive matcher is a hole a model will find.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from rtlenv.domain_protocol import CURRENCY_EXPONENT, get_path, subtree_changes

Path = list[str | int]
_MISSING = object()


class MatcherSpecError(ValueError):
    """A matcher spec is malformed. The message names the offending field."""


@dataclass(frozen=True)
class MatchResult:
    ok: bool
    kind: str
    path: Path | None
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "path": self.path,
            "detail": self.detail,
            "evidence": self.evidence,
        }


class Matcher(Protocol):
    kind: str

    def evaluate(self, before: Any, after: Any) -> MatchResult: ...
    def to_spec(self) -> dict[str, Any]: ...
    def paths(self) -> list[Path]: ...


def _lookup(state: Any, path: Path) -> Any:
    """get_path that distinguishes an explicit null from a missing path."""
    cur = state
    for seg in path:
        if isinstance(cur, dict) and isinstance(seg, str) and seg in cur:
            cur = cur[seg]
        elif (
            isinstance(cur, list)
            and isinstance(seg, int)
            and not isinstance(seg, bool)
            and 0 <= seg < len(cur)
        ):
            cur = cur[seg]
        else:
            return _MISSING
    return cur


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_money(v: Any) -> bool:
    return (
        isinstance(v, dict)
        and set(v) == {"minor", "currency"}
        and _is_int(v["minor"])
        and isinstance(v["currency"], str)
    )


def _require(spec: dict, name: str, kind: str) -> Any:
    if name not in spec:
        raise MatcherSpecError(f"{kind}: missing field {name!r}")
    return spec[name]


def _path(spec: dict, kind: str, name: str = "path") -> Path:
    p = _require(spec, name, kind)
    if not isinstance(p, list) or not p or not all(isinstance(s, str) or _is_int(s) for s in p):
        raise MatcherSpecError(
            f"{kind}: {name} must be a non-empty list of string/int segments, got {p!r}"
        )
    return list(p)


def _paths(spec: dict, kind: str, name: str) -> list[Path]:
    ps = _require(spec, name, kind)
    if not isinstance(ps, list) or not ps:
        raise MatcherSpecError(f"{kind}: {name} must be a non-empty list of paths")
    return [_path({"p": p}, kind, "p") for p in ps]


@dataclass(frozen=True)
class FieldEquals:
    path: Path
    expected: Any
    kind: str = "field_equals"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        actual = _lookup(after, self.path)
        if actual is _MISSING:
            return MatchResult(
                False, self.kind, self.path, "path missing", {"expected": self.expected}
            )
        ok = (
            actual == self.expected and type(actual) is type(self.expected)
            if not isinstance(self.expected, (dict, list))
            else actual == self.expected
        )
        return MatchResult(
            bool(ok),
            self.kind,
            self.path,
            "equal" if ok else "differs",
            {"expected": self.expected, "actual": actual},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "expected": self.expected}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class CollectionContainsExactly:
    path: Path
    keys: list[str]
    kind: str = "collection_contains_exactly"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        actual = _lookup(after, self.path)
        if not isinstance(actual, dict):
            return MatchResult(
                False,
                self.kind,
                self.path,
                "not a keyed collection",
                {"expected": sorted(self.keys)},
            )
        have, want = sorted(actual), sorted(self.keys)
        ok = have == want
        return MatchResult(
            ok,
            self.kind,
            self.path,
            "exact key set" if ok else "key set differs",
            {"expected": want, "actual": have},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "keys": self.keys}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class CountIs:
    path: Path
    expected: int
    kind: str = "count_is"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        actual = _lookup(after, self.path)
        if not isinstance(actual, (dict, list)):
            return MatchResult(
                False, self.kind, self.path, "not a collection", {"expected": self.expected}
            )
        n = len(actual)
        return MatchResult(
            n == self.expected,
            self.kind,
            self.path,
            "count matches" if n == self.expected else "count differs",
            {"expected": self.expected, "actual": n},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "expected": self.expected}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class MoneyEquals:
    path: Path
    minor: int
    currency: str
    kind: str = "money_equals"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        actual = _lookup(after, self.path)
        if not _is_money(actual):
            return MatchResult(
                False,
                self.kind,
                self.path,
                "not a money value",
                {"expected": {"minor": self.minor, "currency": self.currency}},
            )
        ok = actual["minor"] == self.minor and actual["currency"] == self.currency
        return MatchResult(
            ok,
            self.kind,
            self.path,
            "equal" if ok else "differs",
            {"expected": {"minor": self.minor, "currency": self.currency}, "actual": actual},
        )

    def to_spec(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "minor": self.minor,
            "currency": self.currency,
        }

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class WithinTolerance:
    path: Path
    expected: int
    tolerance: int
    kind: str = "within_tolerance"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        actual = _lookup(after, self.path)
        if not _is_int(actual):
            return MatchResult(
                False,
                self.kind,
                self.path,
                "not an integer (money is never tolerant)",
                {"expected": self.expected},
            )
        ok = abs(actual - self.expected) <= self.tolerance
        return MatchResult(
            ok,
            self.kind,
            self.path,
            "within tolerance" if ok else "outside tolerance",
            {"expected": self.expected, "tolerance": self.tolerance, "actual": actual},
        )

    def to_spec(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "expected": self.expected,
            "tolerance": self.tolerance,
        }

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class Unchanged:
    subtrees: list[Path]
    kind: str = "unchanged"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        # fast path: direct equality of each subtree; diff only what differs, for evidence
        moved = [p for p in self.subtrees if get_path(before, p) != get_path(after, p)]
        if not moved:
            return MatchResult(
                True, self.kind, None, "subtrees unchanged", {"subtrees": self.subtrees}
            )
        changes = subtree_changes(before, after, moved)
        return MatchResult(
            False,
            self.kind,
            None,
            f"{len(changes)} change(s) under protected subtrees",
            {"subtrees": self.subtrees, "changes": changes},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "subtrees": self.subtrees}

    def paths(self) -> list[Path]:
        return list(self.subtrees)


@dataclass(frozen=True)
class DeltaEquals:
    path: Path
    delta: int
    kind: str = "delta_equals"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        b, a = _lookup(before, self.path), _lookup(after, self.path)
        if not (_is_int(b) and _is_int(a)):
            return MatchResult(
                False, self.kind, self.path, "not integers on both sides", {"delta": self.delta}
            )
        ok = a - b == self.delta
        return MatchResult(
            ok,
            self.kind,
            self.path,
            "delta matches" if ok else "delta differs",
            {"delta": self.delta, "before": b, "after": a},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path, "delta": self.delta}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class Exists:
    path: Path
    kind: str = "exists"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        ok = _lookup(after, self.path) is not _MISSING
        return MatchResult(ok, self.kind, self.path, "present" if ok else "missing", {})

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class Absent:
    path: Path
    kind: str = "absent"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        ok = _lookup(after, self.path) is _MISSING
        return MatchResult(ok, self.kind, self.path, "absent" if ok else "present", {})

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "path": self.path}

    def paths(self) -> list[Path]:
        return [self.path]


@dataclass(frozen=True)
class AllOf:
    matchers: tuple[Any, ...]
    kind: str = "all_of"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        results = [m.evaluate(before, after) for m in self.matchers]
        ok = all(r.ok for r in results)
        return MatchResult(
            ok,
            self.kind,
            None,
            "all hold" if ok else "some fail",
            {"results": [r.to_dict() for r in results]},
        )

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "matchers": [m.to_spec() for m in self.matchers]}

    def paths(self) -> list[Path]:
        return [p for m in self.matchers for p in m.paths()]


@dataclass(frozen=True)
class AnyOf(AllOf):
    kind: str = "any_of"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        results = [m.evaluate(before, after) for m in self.matchers]
        ok = any(r.ok for r in results)
        return MatchResult(
            ok,
            self.kind,
            None,
            "one holds" if ok else "none hold",
            {"results": [r.to_dict() for r in results]},
        )


@dataclass(frozen=True)
class Not:
    matcher: Any
    kind: str = "not"

    def evaluate(self, before: Any, after: Any) -> MatchResult:
        inner = self.matcher.evaluate(before, after)
        return MatchResult(not inner.ok, self.kind, None, "negated", {"inner": inner.to_dict()})

    def to_spec(self) -> dict[str, Any]:
        return {"kind": self.kind, "matcher": self.matcher.to_spec()}

    def paths(self) -> list[Path]:
        return self.matcher.paths()


KINDS = (
    "field_equals",
    "collection_contains_exactly",
    "count_is",
    "money_equals",
    "within_tolerance",
    "unchanged",
    "delta_equals",
    "exists",
    "absent",
    "all_of",
    "any_of",
    "not",
)


def parse(spec: dict[str, Any]) -> Matcher:  # noqa: C901 - one branch per matcher kind
    if not isinstance(spec, dict):
        raise MatcherSpecError(f"matcher spec must be an object, got {type(spec).__name__}")
    kind = spec.get("kind")
    if kind not in KINDS:
        raise MatcherSpecError(f"unknown matcher kind {kind!r}; known kinds: {', '.join(KINDS)}")
    if kind == "field_equals":
        return FieldEquals(_path(spec, kind), _require(spec, "expected", kind))
    if kind == "collection_contains_exactly":
        keys = _require(spec, "keys", kind)
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise MatcherSpecError(f"{kind}: keys must be a list of strings")
        return CollectionContainsExactly(_path(spec, kind), list(keys))
    if kind == "count_is":
        n = _require(spec, "expected", kind)
        if not _is_int(n) or n < 0:
            raise MatcherSpecError(f"{kind}: expected must be a non-negative integer")
        return CountIs(_path(spec, kind), n)
    if kind == "money_equals":
        minor, currency = _require(spec, "minor", kind), _require(spec, "currency", kind)
        if not _is_int(minor):
            raise MatcherSpecError(f"{kind}: minor must be an integer (no floats in money paths)")
        if currency not in CURRENCY_EXPONENT:
            raise MatcherSpecError(f"{kind}: unknown currency {currency!r}")
        return MoneyEquals(_path(spec, kind), minor, currency)
    if kind == "within_tolerance":
        expected, tol = _require(spec, "expected", kind), _require(spec, "tolerance", kind)
        if not (_is_int(expected) and _is_int(tol)) or tol < 0:
            raise MatcherSpecError(
                f"{kind}: expected and tolerance must be integers (tolerance >= 0)"
            )
        return WithinTolerance(_path(spec, kind), expected, tol)
    if kind == "unchanged":
        return Unchanged(_paths(spec, kind, "subtrees"))
    if kind == "delta_equals":
        delta = _require(spec, "delta", kind)
        if not _is_int(delta):
            raise MatcherSpecError(f"{kind}: delta must be an integer")
        return DeltaEquals(_path(spec, kind), delta)
    if kind == "exists":
        return Exists(_path(spec, kind))
    if kind == "absent":
        return Absent(_path(spec, kind))
    if kind in ("all_of", "any_of"):
        inner = _require(spec, "matchers", kind)
        if not isinstance(inner, list) or not inner:
            raise MatcherSpecError(f"{kind}: matchers must be a non-empty list")
        parsed = tuple(parse(m) for m in inner)
        return AllOf(parsed) if kind == "all_of" else AnyOf(parsed)
    return Not(parse(_require(spec, "matcher", kind)))
