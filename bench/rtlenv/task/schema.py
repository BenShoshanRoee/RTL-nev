"""The minimal task contract the judge consumes (sub-chunk 2.2.1).

Fields: ``id``, ``setup`` (domain + seed), ``goal_matchers``, ``unchanged_subtrees``.
Sub-chunk 2.2.4 ADDS authoring fields (suite, description_template, milestones,
cheat_surface, fixtures, difficulty_target); it never renames, removes or redefines these.
Unknown fields are therefore accepted here and ignored by the judge.

``unchanged_subtrees`` is mandatory and non-empty: it is the only mechanism that catches side
effects, and a task without it is permissive by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rtlenv.judge.matchers import MatcherSpecError, parse

Path = list[str | int]


class TaskContractError(ValueError):
    """The task object violates the minimal contract. The message names the field."""


@dataclass(frozen=True)
class TaskSetup:
    domain: str
    seed: int


@dataclass(frozen=True)
class TaskContract:
    id: str
    setup: TaskSetup
    goal_matchers: list[dict[str, Any]]
    unchanged_subtrees: list[Path]


def _is_path(p: Any) -> bool:
    return (
        isinstance(p, list)
        and bool(p)
        and all(isinstance(s, str) or (isinstance(s, int) and not isinstance(s, bool)) for s in p)
    )


def _prefix(short: list, long: list) -> bool:
    return len(short) <= len(long) and all(a == b for a, b in zip(short, long, strict=False))


def validate_task(obj: Any) -> TaskContract:
    if not isinstance(obj, dict):
        raise TaskContractError(f"task must be an object, got {type(obj).__name__}")
    task_id = obj.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise TaskContractError("id: must be a non-empty string")
    setup = obj.get("setup")
    if (
        not isinstance(setup, dict)
        or not isinstance(setup.get("domain"), str)
        or not setup["domain"]
    ):
        raise TaskContractError("setup: must be an object with a non-empty 'domain' string")
    seed = setup.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**32:
        raise TaskContractError("setup.seed: must be an integer in [0, 2^32)")
    goals = obj.get("goal_matchers")
    if not isinstance(goals, list) or not goals:
        raise TaskContractError("goal_matchers: must be a non-empty list of matcher specs")
    parsed = []
    for i, spec in enumerate(goals):
        try:
            parsed.append(parse(spec))
        except MatcherSpecError as e:
            raise TaskContractError(f"goal_matchers[{i}]: {e}") from e
    subtrees = obj.get("unchanged_subtrees")
    if subtrees is None:
        raise TaskContractError(
            "unchanged_subtrees: missing; every task must declare the subtrees that must not move"
        )
    if not isinstance(subtrees, list) or not subtrees:
        raise TaskContractError(
            "unchanged_subtrees: must be a non-empty list of paths (an empty list protects nothing)"
        )
    for i, p in enumerate(subtrees):
        if not _is_path(p):
            raise TaskContractError(
                f"unchanged_subtrees[{i}]: must be a non-empty list of segments, got {p!r}"
            )
    seen = set()
    for p in subtrees:
        key = tuple(p)
        if key in seen:
            raise TaskContractError(f"unchanged_subtrees: duplicate path {p}")
        seen.add(key)
    for m in parsed:
        for gp in m.paths():
            for up in subtrees:
                if _prefix(up, gp) and m.kind != "unchanged":
                    raise TaskContractError(
                        f"goal path {gp} lies inside unchanged subtree {up}; unreachable"
                    )
    return TaskContract(
        id=task_id,
        setup=TaskSetup(domain=setup["domain"], seed=seed),
        goal_matchers=list(goals),
        unchanged_subtrees=[list(p) for p in subtrees],
    )
