"""Judge meta-test harness: tests the judges themselves against curated transcripts.

Corpus layout (shared with the task registry, 2.2.4, and authoring, 6.1.x):

    bench/tasks/<lang>/<suite>/<task_dir>/task.yaml
    bench/tasks/<lang>/<suite>/<task_dir>/fixtures/<name>.json
    bench/rtlenv/metatest/fixtures/states/<ref>.json      shared base states (exported)

A fixture: {name, kind, author, cheat, before, after, trace, declared_done}.
  kind     correct | clearly_wrong | plausibly_wrong
  before   {"ref": "<state>"}; must equal the task's setup.state_ref
  after    {"ref": "<state>"} optionally with "set": [{path, value}], "remove": [path],
           or "changes": [...] (a core changeset); or a full inline state object
  trace    [] | {"ref": "<trace>"} | inline list of trace entries
  cheat    prose naming the cheat a plausibly-wrong fixture exercises (mandatory for that kind)

Checks (each a CI failure, each naming the task and fixture):
  minimums   >= 1 correct, >= 1 clearly_wrong, >= 3 plausibly_wrong, unique names, cheat lines
  verdicts   correct -> success, full reward, not trivial; clearly_wrong -> reward <= 0;
             plausibly_wrong -> not success and reward below the correct fixture's
  mutation   every goal matcher, milestone and protected subtree is weakened in turn; a mutant
             is caught if some fixture's success flips to True or its reward rises. Score must
             reach 90%. An escaped mutant names the fixture that is missing.

    uv run python -m rtlenv.metatest.harness [--root bench/tasks]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rtlenv.domain_protocol import patch
from rtlenv.judge import Rollout, judge
from rtlenv.judge.reward import DEFAULT_WEIGHTS
from rtlenv.task.schema import TaskContractError, validate_task

BENCH = Path(__file__).resolve().parents[2]
TASKS_ROOT = BENCH / "tasks"
STATES_ROOT = Path(__file__).resolve().parent / "fixtures" / "states"
FIXTURE_KINDS = ("correct", "clearly_wrong", "plausibly_wrong")
MINIMUMS = {"correct": 1, "clearly_wrong": 1, "plausibly_wrong": 3}
MUTATION_THRESHOLD = 0.9


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class Fixture:
    name: str
    kind: str
    author: str
    cheat: str
    rollout: Rollout
    before_ref: str | None
    path: Path


@dataclass(frozen=True)
class TaskEntry:
    id: str
    path: Path
    task: dict[str, Any]
    fixtures: list[Fixture]
    load_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MutationReport:
    total: int
    caught: int
    escaped: list[str]

    @property
    def score(self) -> float:
        return 1.0 if self.total == 0 else self.caught / self.total


@dataclass
class HarnessReport:
    tasks: list[dict[str, Any]]
    problems: list[str]
    elapsed_s: float

    @property
    def ok(self) -> bool:
        return not self.problems


# ----------------------------------------------------------------------------- loading
_state_cache: dict[str, Any] = {}


def load_state_ref(ref: str) -> Any:
    if ref not in _state_cache:
        p = STATES_ROOT / f"{ref}.json"
        if not p.is_file() or ".." in ref:
            raise CorpusError(f"unknown state ref {ref!r} (expected {p})")
        _state_cache[ref] = json.loads(p.read_text(encoding="utf-8"))
    return copy.deepcopy(_state_cache[ref])


def _resolve_state(spec: Any, what: str) -> tuple[Any, str | None]:
    """A state from a fixture 'before'/'after' spec. Returns (state, ref-or-None)."""
    if isinstance(spec, dict) and "ref" in spec:
        state = load_state_ref(spec["ref"])
        if "changes" in spec:
            state = patch(state, {"changes": spec["changes"]})
        for edit in spec.get("set", []):
            state = _set(state, edit["path"], edit["value"])
        for path in spec.get("remove", []):
            state = _remove(state, path)
        return state, spec["ref"]
    if isinstance(spec, dict):
        return spec, None
    raise CorpusError(f"{what}: must be a state object or {{'ref': ...}}")


def _walk(state: Any, path: list, what: str) -> Any:
    cur = state
    for i, seg in enumerate(path[:-1]):
        if not isinstance(cur, dict) or seg not in cur:
            raise CorpusError(f"{what} path {path}: segment {seg!r} does not exist (at {path[:i]})")
        cur = cur[seg]
    if not isinstance(cur, dict):
        raise CorpusError(f"{what} path {path}: parent is not an object")
    return cur


def _set(state: Any, path: list, value: Any) -> Any:
    if not path:
        raise CorpusError("set: empty path")
    _walk(state, path, "set")[path[-1]] = value
    return state


def _remove(state: Any, path: list) -> Any:
    if not path:
        raise CorpusError("remove: empty path")
    parent = _walk(state, path, "remove")
    if path[-1] not in parent:
        raise CorpusError(f"remove path {path}: key {path[-1]!r} does not exist")
    del parent[path[-1]]
    return state


def _resolve_trace(spec: Any) -> list[dict]:
    if isinstance(spec, dict) and "ref" in spec:
        return load_state_ref(spec["ref"])
    if isinstance(spec, list):
        return spec
    raise CorpusError("trace: must be a list or {'ref': ...}")


def load_fixture(path: Path) -> Fixture:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("name", "kind", "author", "before", "after"):
        if key not in data:
            raise CorpusError(f"{path.name}: missing {key!r}")
    if data["kind"] not in FIXTURE_KINDS:
        raise CorpusError(f"{path.name}: kind must be one of {FIXTURE_KINDS}")
    if data["name"] != path.stem:
        raise CorpusError(f"{path.name}: name {data['name']!r} must equal the file stem")
    before, before_ref = _resolve_state(data["before"], f"{path.name}: before")
    after, _ = _resolve_state(data["after"], f"{path.name}: after")
    trace = _resolve_trace(data.get("trace", []))
    return Fixture(
        name=data["name"],
        kind=data["kind"],
        author=str(data.get("author", "")),
        cheat=str(data.get("cheat", "") or ""),
        rollout=Rollout(
            before=before,
            after=after,
            trace=trace,
            declared_done=bool(data.get("declared_done", False)),
        ),
        before_ref=before_ref,
        path=path,
    )


def discover_tasks(root: Path = TASKS_ROOT) -> list[TaskEntry]:
    entries: list[TaskEntry] = []
    for task_file in sorted(Path(root).rglob("task.yaml")):
        task = yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
        fixtures: list[Fixture] = []
        errors: list[str] = []
        for f in sorted((task_file.parent / "fixtures").glob("*.json")):
            try:
                fixtures.append(load_fixture(f))
            except (CorpusError, KeyError, json.JSONDecodeError, TypeError) as e:
                errors.append(f"{task.get('id', task_file.parent.name)}: fixture {f.name}: {e}")
        entries.append(
            TaskEntry(
                id=str(task.get("id", task_file.parent.name)),
                path=task_file.parent,
                task=task,
                fixtures=fixtures,
                load_errors=errors,
            )
        )
    return sorted(entries, key=lambda e: e.id)


# ----------------------------------------------------------------------------- checks
def check_minimums(entry: TaskEntry) -> list[str]:
    problems = list(entry.load_errors)
    try:
        validate_task(entry.task)
    except TaskContractError as e:
        problems.append(f"{entry.id}: task contract: {e}")
    counts = {k: sum(1 for f in entry.fixtures if f.kind == k) for k in FIXTURE_KINDS}
    short = [f"{k}: {counts[k]} of {n} required" for k, n in MINIMUMS.items() if counts[k] < n]
    if short:
        need = ", ".join(f">= {n} {k}" for k, n in MINIMUMS.items())
        problems.append(
            f"{entry.id}: fixture minimums not met ({'; '.join(short)}); every task needs {need}"
        )
    names = [f.name for f in entry.fixtures]
    if len(names) != len(set(names)):
        problems.append(f"{entry.id}: duplicate fixture names")
    for f in entry.fixtures:
        if f.kind == "plausibly_wrong" and not f.cheat.strip():
            problems.append(
                f"{entry.id}: fixture {f.name}: plausibly_wrong fixtures must name their cheat"
            )
        if not f.author.strip():
            problems.append(f"{entry.id}: fixture {f.name}: missing author")
    state_ref = (entry.task.get("setup") or {}).get("state_ref")
    if not state_ref:
        problems.append(
            f"{entry.id}: setup.state_ref missing (the base state every fixture starts from)"
        )
    else:
        for f in entry.fixtures:
            if f.before_ref != state_ref:
                problems.append(
                    f"{entry.id}: fixture {f.name}: before must be the base state {state_ref!r},"
                    f" got {f.before_ref!r}"
                )
    return problems


def _verdicts(entry: TaskEntry) -> dict[str, Any]:
    return {f.name: judge(entry.task, f.rollout) for f in entry.fixtures}


def check_verdicts(entry: TaskEntry) -> list[str]:
    problems: list[str] = []
    if entry.load_errors:
        return list(entry.load_errors)
    try:
        verdicts = _verdicts(entry)
    except (TaskContractError, ValueError) as e:
        return [f"{entry.id}: judging failed: {e}"]
    weights = {**DEFAULT_WEIGHTS, **(entry.task.get("reward") or {})}
    correct_rewards = [
        v.reward for f, v in ((f, verdicts[f.name]) for f in entry.fixtures) if f.kind == "correct"
    ]
    best_correct = min(correct_rewards) if correct_rewards else weights["max"]
    for f in entry.fixtures:
        v = verdicts[f.name]
        tag = f"{entry.id}: fixture {f.name} ({f.kind})"
        if f.kind == "correct":
            if not v.success:
                failed = [r["detail"] for r in v.evidence["goal"] if not r["ok"]]
                problems.append(
                    f"{tag}: expected success; goal={failed} side_effects={len(v.side_effects)}"
                )
            if v.reward != weights["max"]:
                problems.append(
                    f"{tag}: expected full reward {weights['max']}, got {v.reward}"
                    f" (progress {v.progress}, trace_valid {v.evidence.get('trace_valid')})"
                )
            if v.evidence.get("goal_held_before"):
                problems.append(
                    f"{tag}: the goal already holds in the base state; the task is trivial"
                )
        elif f.kind == "clearly_wrong":
            if v.success or v.reward > 0:
                problems.append(
                    f"{tag}: expected reward <= 0, got {v.reward} (success={v.success})"
                )
        else:
            if v.success:
                problems.append(
                    f"{tag}: JUDGE TOO PERMISSIVE: accepted a plausibly-wrong transcript"
                    f" ({f.cheat})"
                )
            elif v.reward >= best_correct:
                problems.append(
                    f"{tag}: reward {v.reward} not below the correct fixture's {best_correct}"
                )
    return problems


# ----------------------------------------------------------------------------- mutation
def _weakenings(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any] | None]]:
    """(label, weakened spec or None to drop) for one matcher spec."""
    kind = spec.get("kind")
    out: list[tuple[str, dict[str, Any] | None]] = []
    if "path" in spec and kind not in ("exists",):
        out.append(("accept any value", {"kind": "exists", "path": spec["path"]}))
    if kind == "exists":
        out.append(("drop", None))
    if kind == "within_tolerance":
        out.append(("tolerance x10", {**spec, "tolerance": spec["tolerance"] * 10 + 1}))
    if kind == "collection_contains_exactly":
        out.append(
            (
                "count only",
                {"kind": "count_is", "path": spec["path"], "expected": len(spec["keys"])},
            )
        )
    if kind == "count_is" and spec["expected"] > 0:
        out.append(("count off by one", {**spec, "expected": spec["expected"] + 1}))
    if kind == "all_of":
        out.append(("all_of -> any_of", {**spec, "kind": "any_of"}))
    if kind == "not":
        out.append(("drop negation", spec["matcher"]))
    if kind == "unchanged":
        out.append(("drop", None))
    return out


def mutants(task: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for i, spec in enumerate(task.get("goal_matchers", [])):
        for label, weak in _weakenings(spec):
            t = copy.deepcopy(task)
            if weak is None:
                del t["goal_matchers"][i]
                if not t["goal_matchers"]:
                    continue
            else:
                t["goal_matchers"][i] = weak
            out.append((f"goal[{i}] {spec.get('kind')} -> {label}", t))
    for i, spec in enumerate(task.get("milestones", []) or []):
        t = copy.deepcopy(task)
        t["milestones"][i] = (
            {"kind": "exists", "path": spec["path"]} if "path" in spec else t["milestones"][i]
        )
        if t["milestones"][i] != spec:
            out.append((f"milestone[{i}] {spec.get('kind')} -> accept any value", t))
    for i, p in enumerate(task.get("unchanged_subtrees", [])):
        t = copy.deepcopy(task)
        del t["unchanged_subtrees"][i]
        if t["unchanged_subtrees"]:
            out.append((f"unchanged[{i}] {p} -> dropped", t))
    return out


def mutation_run(entry: TaskEntry) -> MutationReport:
    base = _verdicts(entry)
    caught = 0
    escaped: list[str] = []
    ms = mutants(entry.task)
    for label, mutant in ms:
        detected = False
        for f in entry.fixtures:
            if f.kind == "correct":
                continue
            try:
                v = judge(mutant, f.rollout)
            except (TaskContractError, ValueError):
                detected = True  # a mutant the contract itself refuses is not a hole
                break
            b = base[f.name]
            if (v.success and not b.success) or v.reward > b.reward + 1e-12:
                detected = True
                break
        if detected:
            caught += 1
        else:
            escaped.append(label)
    return MutationReport(total=len(ms), caught=caught, escaped=escaped)


# ----------------------------------------------------------------------------- coverage
@dataclass(frozen=True)
class CheckCoverage:
    label: str
    refused: int
    sole: int
    fixtures: list[str]


@dataclass(frozen=True)
class Cluster:
    refusers: list[str]
    fixtures: list[str]


@dataclass(frozen=True)
class CoverageReport:
    checks: list[CheckCoverage]
    clusters: list[Cluster]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [c.__dict__ for c in self.checks],
            "clusters": [c.__dict__ for c in self.clusters],
        }


def coverage(entry: TaskEntry, cluster_min: int = 3) -> CoverageReport:
    """Which checks refuse which fixtures. `sole` counts fixtures a check refuses on its own:
    a check with sole == 0 is never tested in isolation. Clusters are groups of fixtures
    refused by the identical set of checks (redundant near-misses)."""
    goals = entry.task.get("goal_matchers", [])
    subtrees = entry.task.get("unchanged_subtrees", [])
    labels = [
        f"goal[{i}] {g.get('kind')} {'/'.join(map(str, g.get('path', [])))}"
        for i, g in enumerate(goals)
    ]
    labels += [f"unchanged[{i}] {'/'.join(map(str, p))}" for i, p in enumerate(subtrees)]
    refused_by: dict[str, list[str]] = {label: [] for label in labels}
    sole_by: dict[str, list[str]] = {label: [] for label in labels}
    by_set: dict[tuple[str, ...], list[str]] = {}
    for f in sorted(entry.fixtures, key=lambda x: x.name):
        if f.kind == "correct":
            continue
        v = judge(entry.task, f.rollout)
        refusers = [labels[i] for i, r in enumerate(v.evidence["goal"]) if not r["ok"]]
        violated = v.evidence["violated_subtrees"]
        refusers += [
            labels[len(goals) + i] for i, sp in enumerate(subtrees) if list(sp) in violated
        ]
        for r in refusers:
            refused_by[r].append(f.name)
        if len(refusers) == 1:
            sole_by[refusers[0]].append(f.name)
        by_set.setdefault(tuple(refusers), []).append(f.name)
    checks = [
        CheckCoverage(
            label=lb, refused=len(refused_by[lb]), sole=len(sole_by[lb]), fixtures=refused_by[lb]
        )
        for lb in labels
    ]
    clusters = [
        Cluster(refusers=list(k), fixtures=v)
        for k, v in sorted(by_set.items())
        if len(v) >= cluster_min
    ]
    return CoverageReport(checks=checks, clusters=clusters)


# ----------------------------------------------------------------------------- run
def run(root: Path = TASKS_ROOT) -> HarnessReport:
    t0 = time.perf_counter()
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    entries = discover_tasks(root)
    if not entries:
        problems.append(f"no tasks found under {root}")
    for e in entries:
        p_min = check_minimums(e)
        p_ver = check_verdicts(e) if not p_min else []
        rep = mutation_run(e) if not (p_min or p_ver) else MutationReport(0, 0, [])
        if not (p_min or p_ver) and rep.score < MUTATION_THRESHOLD:
            problems.append(
                f"{e.id}: mutation score {rep.score:.0%} below {MUTATION_THRESHOLD:.0%};"
                f" escaped: {rep.escaped}"
            )
        problems.extend(p_min + p_ver)
        by_kind = {k: sum(1 for f in e.fixtures if f.kind == k) for k in FIXTURE_KINDS}
        by_author = {}
        for f in e.fixtures:
            by_author[f.author] = by_author.get(f.author, 0) + 1
        cov = coverage(e) if not (p_min or p_ver) else CoverageReport([], [])
        rows.append(
            {
                "id": e.id,
                "fixtures": by_kind,
                "authors": by_author,
                "mutants": rep.total,
                "caught": rep.caught,
                "escaped": rep.escaped,
                "problems": len(p_min + p_ver),
                "coverage": cov.to_dict(),
            }
        )
    elapsed = time.perf_counter() - t0
    if elapsed > 30:
        problems.append(f"corpus took {elapsed:.1f}s; budget is 30s")
    return HarnessReport(tasks=rows, problems=problems, elapsed_s=elapsed)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=TASKS_ROOT)
    args = ap.parse_args()
    report = run(args.root)
    for r in report.tasks:
        kinds = " ".join(f"{k}={v}" for k, v in r["fixtures"].items())
        authors = " ".join(f"{k}={v}" for k, v in sorted(r["authors"].items()))
        score = f"{r['caught']}/{r['mutants']}" if r["mutants"] else "n/a"
        print(
            f"{r['id']}: fixtures [{kinds}] authors [{authors}]"
            f" mutants caught {score} problems {r['problems']}"
        )
        for m in r["escaped"]:
            print(f"  escaped mutant: {m}  (add a fixture that only this check refuses)")
        cov = r["coverage"]
        if cov["checks"]:
            print("  coverage (sole/refused):")
            for c in cov["checks"]:
                flag = "  <- never the sole refuser" if c["sole"] == 0 else ""
                print(f"    {c['sole']:2d}/{c['refused']:2d}  {c['label']}{flag}")
            for cl in cov["clusters"]:
                print(
                    f"  cluster: {len(cl['fixtures'])} fixtures refused by exactly"
                    f" {cl['refusers']}: {cl['fixtures']}"
                )
    for p in report.problems:
        print(f"PROBLEM: {p}")
    n_pw = sum(r["fixtures"].get("plausibly_wrong", 0) for r in report.tasks)
    status = "OK" if report.ok else "FAIL"
    print(
        f"metatest: {len(report.tasks)} task(s), {n_pw} plausibly-wrong fixtures,"
        f" {report.elapsed_s:.2f}s, {status}"
    )
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
