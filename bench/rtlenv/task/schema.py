"""The task contract, in two layers.

Layer 1 (sub-chunk 2.2.1, ``validate_task``): what the judge consumes at runtime.
    ``id``, ``setup`` (domain, seed, optional state_ref), ``goal_matchers``,
    ``unchanged_subtrees``, optional ``milestones`` and ``reward``.

Layer 2 (sub-chunk 2.2.4, ``validate_definition``): what an authored, registered task must
also declare. It ADDS fields; it never renames, removes or redefines a layer-1 field, so a
task the judge accepts is accepted here as soon as the added fields are present.
    ``suite``            the collection the task ships in; equals the id's second segment and
                         the directory under bench/tasks/<lang>/ (commerce, pathology, reference)
    ``domain``           the semantic domain; must equal setup.domain
    ``split``            train | test | pathology | calibration (what packaging exposes)
    ``difficulty_target`` L1..L4 (the platform taxonomy used by calibration)
    ``description_template`` {language: slotted string}; the task's own language is mandatory
                         and every language must use the same identifier slots
    ``cheat_surface``    >= 3 distinct prose lines naming known exploits
    ``fixtures``         optional per-kind minimums; may raise the floor, never lower it
    ``version``          optional positive integer, default 1 (licensing keys on id + version)
    ``deprecated``       optional boolean, default false (deprecated tasks still run)
Unknown fields pass through in ``TaskDefinition.extra`` so pathology tasks (3.2.2) can extend
the contract without forking it.

Authoring rule from red-team finding #1: protect subtrees, never leaves. A protected path
deeper than ``MAX_PROTECTED_DEPTH`` is rejected.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any

from rtlenv.judge.matchers import MatcherSpecError, parse
from rtlenv.judge.reward import RewardConfigError, validate_weights

Path = list[str | int]

SPLITS = ("train", "test", "pathology", "calibration")
DIFFICULTIES = ("L1", "L2", "L3", "L4")
FIXTURE_KINDS = ("correct", "clearly_wrong", "plausibly_wrong")
FIXTURE_FLOOR = {"correct": 1, "clearly_wrong": 1, "plausibly_wrong": 3}
MIN_CHEAT_SURFACE = 3
MAX_PROTECTED_DEPTH = 2

_SEGMENT = r"[a-z][a-z0-9_]*"
ID_PATTERN = re.compile(rf"^[a-z]{{2}}(\.{_SEGMENT}){{3,}}$")
SEGMENT_PATTERN = re.compile(rf"^{_SEGMENT}$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}$")
STATE_REF_PATTERN = re.compile(r"^[a-z0-9_-]+(/[a-z0-9_-]+)*$")

CONTRACT_FIELDS = frozenset(
    {"id", "setup", "goal_matchers", "unchanged_subtrees", "milestones", "reward"}
)
AUTHORING_FIELDS = frozenset(
    {
        "suite",
        "domain",
        "split",
        "difficulty_target",
        "description_template",
        "cheat_surface",
        "fixtures",
        "version",
        "deprecated",
    }
)


class TaskContractError(ValueError):
    """The task object violates the contract. The message names the field."""


@dataclass(frozen=True)
class TaskSetup:
    domain: str
    seed: int
    state_ref: str | None = None


@dataclass(frozen=True)
class TaskContract:
    id: str
    setup: TaskSetup
    goal_matchers: list[dict[str, Any]]
    unchanged_subtrees: list[Path]
    # optional (2.2.2): ordered milestone matcher specs and reward weight overrides
    milestones: list[dict[str, Any]] = field(default_factory=list)
    reward: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskDefinition:
    """An authored task: the judge contract plus the routing and quality fields."""

    contract: TaskContract
    suite: str
    domain: str
    language: str
    split: str
    difficulty_target: str
    description_template: dict[str, str]
    slots: tuple[str, ...]
    cheat_surface: tuple[str, ...]
    fixtures: dict[str, int]
    version: int
    deprecated: bool
    extra: dict[str, Any]

    @property
    def id(self) -> str:
        return self.contract.id


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_path(p: Any) -> bool:
    return isinstance(p, list) and bool(p) and all(isinstance(s, str) or _is_int(s) for s in p)


def _prefix(short: list, long: list) -> bool:
    return len(short) <= len(long) and all(a == b for a, b in zip(short, long, strict=False))


# ----------------------------------------------------------------------------- layer 1: judge


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
    if not _is_int(seed) or not 0 <= seed < 2**32:
        raise TaskContractError("setup.seed: must be an integer in [0, 2^32)")
    state_ref = setup.get("state_ref")
    if state_ref is not None and (
        not isinstance(state_ref, str) or not STATE_REF_PATTERN.match(state_ref)
    ):
        raise TaskContractError(
            "setup.state_ref: must be a relative name like 'commerce/seed-42'"
            f" (lowercase, digits, '-', '_', '/'), got {state_ref!r}"
        )
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
    milestones = obj.get("milestones", [])
    if not isinstance(milestones, list):
        raise TaskContractError("milestones: must be a list of matcher specs")
    parsed_milestones = []
    for i, spec in enumerate(milestones):
        try:
            parsed_milestones.append(parse(spec))
        except MatcherSpecError as e:
            raise TaskContractError(f"milestones[{i}]: {e}") from e
    for i, m in enumerate(parsed_milestones):
        for mp in m.paths():
            for up in subtrees:
                if _prefix(up, mp):
                    raise TaskContractError(
                        f"milestones[{i}]: path {mp} lies inside unchanged subtree {up}"
                    )
    reward = obj.get("reward", {})
    if not isinstance(reward, dict):
        raise TaskContractError("reward: must be an object of weight overrides")
    try:
        validate_weights(reward)
    except RewardConfigError as e:
        raise TaskContractError(f"reward: {e}") from e
    for m in parsed:
        for gp in m.paths():
            for up in subtrees:
                if _prefix(up, gp) and m.kind != "unchanged":
                    raise TaskContractError(
                        f"goal path {gp} lies inside unchanged subtree {up}; unreachable"
                    )
    return TaskContract(
        id=task_id,
        setup=TaskSetup(domain=setup["domain"], seed=seed, state_ref=state_ref),
        goal_matchers=list(goals),
        unchanged_subtrees=[list(p) for p in subtrees],
        milestones=list(milestones),
        reward=dict(reward),
    )


# ----------------------------------------------------------------------------- layer 2: authoring


def _require_enum(obj: dict, key: str, allowed: tuple[str, ...]) -> str:
    v = obj.get(key)
    if v is None:
        raise TaskContractError(f"{key}: missing; must be one of {list(allowed)}")
    if not isinstance(v, str) or v not in allowed:
        raise TaskContractError(f"{key}: must be one of {list(allowed)}, got {v!r}")
    return v


def _slots(template: str, where: str) -> tuple[str, ...]:
    """Slot names of a str.format template, validated as plain identifiers."""
    names: set[str] = set()
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as e:
        raise TaskContractError(f"{where}: malformed slot syntax ({e})") from e
    for _literal, name, spec, conversion in parsed:
        if name is None:
            continue
        if not name.isidentifier():
            raise TaskContractError(
                f"{where}: slot {{{name}}} must be a plain identifier such as {{product}}"
            )
        if spec or conversion:
            raise TaskContractError(f"{where}: slot {{{name}}} must not carry a format spec")
        names.add(name)
    return tuple(sorted(names))


def _description(obj: dict, language: str) -> tuple[dict[str, str], tuple[str, ...]]:
    tpl = obj.get("description_template")
    if tpl is None:
        raise TaskContractError(
            "description_template: missing; must map language codes to slotted strings"
        )
    if not isinstance(tpl, dict) or not tpl:
        raise TaskContractError(
            "description_template: must be a non-empty mapping of language code to string"
        )
    for lang in tpl:
        if not isinstance(lang, str) or not LANGUAGE_PATTERN.match(lang):
            raise TaskContractError(
                f"description_template: language key {lang!r} must be a two-letter lowercase code"
            )
    if language not in tpl:
        raise TaskContractError(
            f"description_template: missing the task's own language {language!r}"
        )
    slots_by_lang: dict[str, tuple[str, ...]] = {}
    for lang in sorted(tpl):
        text = tpl[lang]
        where = f"description_template.{lang}"
        if not isinstance(text, str) or not text.strip():
            raise TaskContractError(f"{where}: must be a non-empty string")
        slots_by_lang[lang] = _slots(text, where)
    reference = slots_by_lang[language]
    for lang, s in slots_by_lang.items():
        if s != reference:
            raise TaskContractError(
                f"description_template: slots differ between {language!r} {list(reference)}"
                f" and {lang!r} {list(s)}; every language must use the same slots"
            )
    return {k: tpl[k] for k in sorted(tpl)}, reference


def _cheat_surface(obj: dict) -> tuple[str, ...]:
    cs = obj.get("cheat_surface")
    if cs is None:
        raise TaskContractError(
            "cheat_surface: missing; every task must document how a model could collect the"
            " reward without doing the work"
        )
    if not isinstance(cs, list):
        raise TaskContractError("cheat_surface: must be a list of prose lines")
    for i, line in enumerate(cs):
        if not isinstance(line, str) or not line.strip():
            raise TaskContractError(f"cheat_surface[{i}]: must be a non-empty string")
    stripped = [line.strip() for line in cs]
    if len(set(stripped)) != len(stripped):
        raise TaskContractError("cheat_surface: duplicate lines")
    if len(stripped) < MIN_CHEAT_SURFACE:
        raise TaskContractError(
            f"cheat_surface: {len(stripped)} line(s); at least {MIN_CHEAT_SURFACE} are required"
            " (one per plausibly-wrong fixture)"
        )
    return tuple(stripped)


def _fixture_minimums(obj: dict) -> dict[str, int]:
    fx = obj.get("fixtures", {})
    if not isinstance(fx, dict):
        raise TaskContractError(
            f"fixtures: must be a mapping of fixture kind to minimum count, got {fx!r}"
        )
    out: dict[str, int] = {}
    for kind in sorted(fx):
        if kind not in FIXTURE_KINDS:
            raise TaskContractError(f"fixtures: unknown kind {kind!r}; kinds are {FIXTURE_KINDS}")
        n = fx[kind]
        if not _is_int(n):
            raise TaskContractError(f"fixtures.{kind}: must be an integer, got {n!r}")
        if n < FIXTURE_FLOOR[kind]:
            raise TaskContractError(
                f"fixtures.{kind}: {n} is below the floor of {FIXTURE_FLOOR[kind]};"
                " a task may raise the minimum, never lower it"
            )
        out[kind] = n
    return out


def validate_definition(obj: Any) -> TaskDefinition:
    """Validate an authored task: the judge contract plus every authoring field."""
    contract = validate_task(obj)
    task_id = contract.id
    if not ID_PATTERN.match(task_id):
        raise TaskContractError(
            f"id: {task_id!r} must be <lang>.<suite>.<area>.<name> in lowercase snake case,"
            " e.g. he.commerce.checkout.coupon_then_variant_change"
        )
    segments = task_id.split(".")
    language, id_suite = segments[0], segments[1]

    suite = obj.get("suite")
    if suite is None:
        raise TaskContractError("suite: missing; must equal the id's second segment")
    if not isinstance(suite, str) or not SEGMENT_PATTERN.match(suite):
        raise TaskContractError(f"suite: must be lowercase snake case, got {suite!r}")
    if suite != id_suite:
        raise TaskContractError(f"suite: {suite!r} must equal the id's second segment {id_suite!r}")

    domain = obj.get("domain")
    if domain is None:
        raise TaskContractError("domain: missing; must equal setup.domain")
    if not isinstance(domain, str) or domain != contract.setup.domain:
        raise TaskContractError(
            f"domain: {domain!r} must equal setup.domain {contract.setup.domain!r}"
        )

    split = _require_enum(obj, "split", SPLITS)
    if (suite == "pathology") != (split == "pathology"):
        if suite == "pathology":
            raise TaskContractError(
                f"split: suite 'pathology' requires split 'pathology', got {split!r}"
            )
        raise TaskContractError(
            f"suite: split 'pathology' requires suite 'pathology', got {suite!r}"
        )
    if suite == "reference" and split == "train":
        raise TaskContractError(
            "split: suite 'reference' is held out for transfer measurement and can never be"
            " in split 'train'"
        )

    difficulty = _require_enum(obj, "difficulty_target", DIFFICULTIES)
    description, slots = _description(obj, language)
    cheat_surface = _cheat_surface(obj)
    fixtures = _fixture_minimums(obj)

    if contract.setup.state_ref is None:
        raise TaskContractError(
            "setup.state_ref: missing; an authored task names the base state its fixtures start"
            " from"
        )
    for i, p in enumerate(contract.unchanged_subtrees):
        if len(p) > MAX_PROTECTED_DEPTH:
            raise TaskContractError(
                f"unchanged_subtrees[{i}]: {p} protects a leaf; protect the whole subtree"
                f" {p[:MAX_PROTECTED_DEPTH]} instead (red-team finding #1: protect subtrees,"
                " not leaves)"
            )

    version = obj.get("version", 1)
    if not _is_int(version) or version < 1:
        raise TaskContractError(f"version: must be a positive integer, got {version!r}")
    deprecated = obj.get("deprecated", False)
    if not isinstance(deprecated, bool):
        raise TaskContractError(f"deprecated: must be true or false, got {deprecated!r}")

    extra = {k: obj[k] for k in sorted(obj) if k not in CONTRACT_FIELDS | AUTHORING_FIELDS}
    return TaskDefinition(
        contract=contract,
        suite=suite,
        domain=domain,
        language=language,
        split=split,
        difficulty_target=difficulty,
        description_template=description,
        slots=slots,
        cheat_surface=cheat_surface,
        fixtures=fixtures,
        version=version,
        deprecated=deprecated,
        extra=extra,
    )
