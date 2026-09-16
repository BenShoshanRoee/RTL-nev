"""The judge meta-test harness, run against every task under bench/tasks.

CI fails here if any task lacks its fixture minimums, any fixture's verdict disagrees with its
declared kind, fewer than 90% of injected matcher weakenings are caught, or the corpus takes
longer than 30 seconds.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml
from rtlenv.metatest.harness import (
    MINIMUMS,
    TASKS_ROOT,
    check_minimums,
    check_verdicts,
    discover_tasks,
    mutation_run,
    run,
)

TASKS = discover_tasks(TASKS_ROOT)


def test_corpus_is_not_empty() -> None:
    assert TASKS, "no tasks under bench/tasks: the harness would pass vacuously"


@pytest.mark.parametrize("entry", TASKS, ids=lambda e: e.id)
def test_fixture_minimums(entry) -> None:
    assert check_minimums(entry) == []


@pytest.mark.parametrize("entry", TASKS, ids=lambda e: e.id)
def test_every_fixture_verdict_matches_its_kind(entry) -> None:
    assert check_verdicts(entry) == []


@pytest.mark.parametrize("entry", TASKS, ids=lambda e: e.id)
def test_mutation_score_at_least_90_percent(entry) -> None:
    report = mutation_run(entry)
    assert report.total >= 5, "too few mutants to mean anything"
    assert report.score >= 0.9, f"escaped: {report.escaped}"


def test_full_corpus_under_30_seconds() -> None:
    t0 = time.perf_counter()
    report = run(TASKS_ROOT)
    elapsed = time.perf_counter() - t0
    assert report.ok, report.problems
    assert elapsed < 30, f"{elapsed:.1f}s"


def test_registering_a_task_without_fixtures_fails_with_a_clear_message(tmp_path: Path) -> None:
    task_dir = tmp_path / "he" / "commerce" / "empty_task"
    task_dir.mkdir(parents=True)
    src = next(TASKS_ROOT.rglob("task.yaml"))
    task = yaml.safe_load(src.read_text(encoding="utf-8"))
    task["id"] = "he.commerce.empty_task"
    (task_dir / "task.yaml").write_text(yaml.safe_dump(task, allow_unicode=True), encoding="utf-8")
    entries = discover_tasks(tmp_path)
    assert [e.id for e in entries] == ["he.commerce.empty_task"]
    problems = check_minimums(entries[0])
    assert problems, "a task with no fixtures must be refused"
    msg = " ".join(problems)
    assert (
        "he.commerce.empty_task" in msg
        and "plausibly_wrong" in msg
        and str(MINIMUMS["plausibly_wrong"]) in msg
    )
    proc = subprocess.run(
        [sys.executable, "-m", "rtlenv.metatest.harness", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "he.commerce.empty_task" in proc.stdout + proc.stderr


def test_a_plausibly_wrong_fixture_without_a_cheat_line_is_refused(tmp_path: Path) -> None:
    src_dir = next(TASKS_ROOT.rglob("task.yaml")).parent
    dst = tmp_path / "he" / "commerce" / src_dir.name
    dst.mkdir(parents=True)
    (dst / "task.yaml").write_text(
        (src_dir / "task.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (dst / "fixtures").mkdir()
    import json

    for f in sorted((src_dir / "fixtures").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data["kind"] == "plausibly_wrong":
            data["cheat"] = ""
        (dst / "fixtures" / f.name).write_text(json.dumps(data), encoding="utf-8")
    entry = discover_tasks(tmp_path)[0]
    problems = check_minimums(entry)
    assert any("cheat" in p for p in problems)


def test_a_fixture_from_the_wrong_base_state_is_refused(tmp_path: Path) -> None:
    import json

    src_dir = next(TASKS_ROOT.rglob("task.yaml")).parent
    dst = tmp_path / "he" / "commerce" / src_dir.name
    dst.mkdir(parents=True)
    (dst / "task.yaml").write_text(
        (src_dir / "task.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (dst / "fixtures").mkdir()
    for f in sorted((src_dir / "fixtures").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        data["before"] = {"ref": "commerce/seed-42-after-checkout"}
        (dst / "fixtures" / f.name).write_text(json.dumps(data), encoding="utf-8")
    entry = discover_tasks(tmp_path)[0]
    problems = check_minimums(entry) + check_verdicts(entry)
    assert any("state_ref" in p or "base state" in p for p in problems)


# ---- coverage matrix ------------------------------------------------------------------------


@pytest.mark.parametrize("entry", TASKS, ids=lambda e: e.id)
def test_every_check_has_a_fixture_it_alone_refuses(entry) -> None:
    """Sharper than mutation: each goal matcher and each protected subtree must be the sole reason
    at least one fixture is refused. A check that only ever fails alongside others is untested
    in isolation and its weakening could hide behind its neighbours."""
    from rtlenv.metatest.harness import coverage

    cov = coverage(entry)
    assert cov.checks, "no checks"
    gaps = [c.label for c in cov.checks if c.sole == 0]
    assert gaps == [], f"checks never the sole refuser: {gaps}"
    for c in cov.checks:
        assert c.refused >= c.sole >= 0


def test_coverage_reports_redundant_clusters_and_is_deterministic(tmp_path: Path) -> None:
    """Three fixtures refused by the identical set of checks are a cluster worth knowing about."""
    import json

    from rtlenv.metatest.harness import coverage

    src_dir = next(TASKS_ROOT.rglob("task.yaml")).parent
    dst = tmp_path / "he" / "commerce" / src_dir.name
    (dst / "fixtures").mkdir(parents=True)
    (dst / "task.yaml").write_text(
        (src_dir / "task.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    base = json.loads((src_dir / "fixtures" / "wrong_quantity.json").read_text(encoding="utf-8"))
    for i in range(3):
        clone = {**base, "name": f"clone_{i}", "cheat": f"clone {i} of wrong_quantity"}
        (dst / "fixtures" / f"clone_{i}.json").write_text(json.dumps(clone), encoding="utf-8")
    for name in ("correct", "nothing_done_declared_done"):
        (dst / "fixtures" / f"{name}.json").write_text(
            (src_dir / "fixtures" / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
    entry = discover_tasks(tmp_path)[0]
    cov = coverage(entry)
    assert any(set(c.fixtures) == {"clone_0", "clone_1", "clone_2"} for c in cov.clusters), (
        cov.clusters
    )
    assert coverage(entry).to_dict() == cov.to_dict()


def test_harness_cli_prints_the_coverage_matrix() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "rtlenv.metatest.harness"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "coverage" in proc.stdout and "sole" in proc.stdout
