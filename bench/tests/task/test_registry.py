"""Task registry and validator CLI (2.2.4).

The registry is what packaging (8.1.1), licensing (10.1.1) and the hold-out check (7.2.1)
read, so it must refuse anything inconsistent and must order everything by id alone.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from rtlenv.metatest.harness import MINIMUMS, check_minimums, discover_tasks
from rtlenv.task.registry import (
    TASKS_ROOT,
    Registry,
    RegistryError,
    TaskRecord,
    iter_task_files,
)
from rtlenv.task.validate import check_layout, task_dir_name, validate_all, validate_file

REAL_ID = "he.commerce.cart.add_two_apply_welcome10"
REAL_TASK_DIR = TASKS_ROOT / "he" / "commerce" / "cart_add_two_apply_welcome10"


def load_real_task() -> dict[str, Any]:
    return yaml.safe_load((REAL_TASK_DIR / "task.yaml").read_text(encoding="utf-8"))


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args], capture_output=True, text=True, check=False
    )


# ---------- discovery


def test_real_corpus_registers_and_the_record_carries_every_routing_field() -> None:
    reg = Registry.discover(TASKS_ROOT)
    assert REAL_ID in reg.ids()
    rec = reg.get(REAL_ID)
    assert isinstance(rec, TaskRecord)
    assert (rec.language, rec.suite, rec.domain, rec.split) == (
        "he",
        "commerce",
        "commerce",
        "train",
    )
    assert rec.difficulty == "L1" and rec.version == 1 and rec.deprecated is False
    assert rec.path == REAL_TASK_DIR
    assert rec.definition.id == REAL_ID


def test_the_walker_is_shared_with_the_metatest_harness(corpus) -> None:
    corpus()
    root = corpus().parents[3]
    assert [p.parent for p in iter_task_files(root)] == [e.path for e in discover_tasks(root)]


def test_every_split_is_exposed_even_when_empty() -> None:
    reg = Registry.discover(TASKS_ROOT)
    assert set(reg.splits()) == {"train", "test", "pathology", "calibration"}
    assert REAL_ID in reg.splits()["train"]


def test_registry_refuses_a_missing_root(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="no such"):
        Registry.discover(tmp_path / "nope")


def test_registry_refuses_an_empty_root(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="no tasks"):
        Registry.discover(tmp_path)


# ---------- consistency with the layout


def test_a_repeated_file_is_refused_as_a_duplicate_id(corpus) -> None:
    a = corpus()
    with pytest.raises(RegistryError) as info:
        Registry.discover(a.parents[3], files=[a, a])
    msg = str(info.value)
    assert "duplicate" in msg and REAL_ID in msg and a.parent.name in msg


def test_task_directory_is_derived_from_the_id() -> None:
    assert task_dir_name(REAL_ID) == "cart_add_two_apply_welcome10"
    assert (
        task_dir_name("he.commerce.checkout.coupon.then_variant") == "checkout_coupon_then_variant"
    )


@pytest.mark.parametrize(
    ("rel", "fragment"),
    [
        ("he/cart_add_two_apply_welcome10", "<lang>/<suite>/<task>"),
        ("he/commerce/x/cart_add_two_apply_welcome10", "<lang>/<suite>/<task>"),
        ("ar/commerce/cart_add_two_apply_welcome10", "language"),
        ("he/pathology/cart_add_two_apply_welcome10", "suite"),
        ("he/commerce/other_name", "directory"),
    ],
)
def test_directory_must_agree_with_the_id(corpus, rel: str, fragment: str) -> None:
    path = corpus(rel=rel)
    root = path.parents[len(Path(rel).parts)]
    errors = check_layout(path, root)
    assert errors and any(fragment in e for e in errors), errors
    with pytest.raises(RegistryError):
        Registry.discover(root)


def test_pathology_suite_and_split_imply_each_other(corpus) -> None:
    def to_pathology(t: dict[str, Any]) -> None:
        t["id"] = "he.pathology.truncation.name_field"
        t["suite"] = "pathology"
        t["split"] = "train"

    p = corpus(mutate=to_pathology, rel="he/pathology/name_field")
    errors = check_layout(p, p.parents[3])
    assert any("pathology" in e and "split" in e for e in errors), errors

    def to_split_only(t: dict[str, Any]) -> None:
        t["split"] = "pathology"

    p = corpus(mutate=to_split_only)
    errors = check_layout(p, p.parents[3])
    assert any("pathology" in e and "suite" in e for e in errors), errors


def test_reference_tasks_can_never_be_in_the_train_split(corpus) -> None:
    def to_reference(t: dict[str, Any]) -> None:
        t["id"] = "he.reference.a.checkout_full"
        t["suite"] = "reference"
        t["split"] = "train"

    p = corpus(mutate=to_reference, rel="he/reference/checkout_full")
    errors = check_layout(p, p.parents[3])
    assert any("reference" in e and "train" in e for e in errors), errors


def test_a_task_without_a_fixtures_directory_is_refused(corpus) -> None:
    p = corpus(with_fixtures=False)
    errors = check_layout(p, p.parents[3])
    assert any("fixtures" in e for e in errors), errors


def test_an_invalid_task_names_its_path_and_field(corpus) -> None:
    def drop(t: dict[str, Any]) -> None:
        del t["cheat_surface"]

    p = corpus(mutate=drop)
    with pytest.raises(RegistryError) as info:
        Registry.discover(p.parents[3])
    assert "cheat_surface" in str(info.value) and "task.yaml" in str(info.value)


# ---------- selection


def _three_task_root(corpus) -> Path:
    def as_test(t: dict[str, Any]) -> None:
        t["id"] = "he.commerce.cart.held_out"
        t["split"] = "test"
        t["difficulty_target"] = "L3"

    def as_deprecated(t: dict[str, Any]) -> None:
        t["id"] = "he.commerce.cart.old"
        t["deprecated"] = True
        t["version"] = 2

    corpus()
    corpus(mutate=as_test, rel="he/commerce/cart_held_out")
    p = corpus(mutate=as_deprecated, rel="he/commerce/cart_old")
    return p.parents[3]


def test_select_filters_and_hides_deprecated_by_default(corpus) -> None:
    reg = Registry.discover(_three_task_root(corpus))
    assert reg.ids() == [
        "he.commerce.cart.add_two_apply_welcome10",
        "he.commerce.cart.held_out",
        "he.commerce.cart.old",
    ]
    assert [r.id for r in reg.select()] == [REAL_ID, "he.commerce.cart.held_out"]
    assert [r.id for r in reg.select(include_deprecated=True)][-1] == "he.commerce.cart.old"
    assert [r.id for r in reg.select(split="test")] == ["he.commerce.cart.held_out"]
    assert [r.id for r in reg.select(difficulty="L3")] == ["he.commerce.cart.held_out"]
    assert [r.id for r in reg.select(language="ar")] == []
    assert [r.id for r in reg.select(suite="commerce", domain="commerce", split="train")] == [
        REAL_ID
    ]
    assert reg.get("he.commerce.cart.old").version == 2


def test_select_rejects_unknown_filter_values(corpus) -> None:
    reg = Registry.discover(_three_task_root(corpus))
    with pytest.raises(RegistryError, match="split"):
        reg.select(split="validation")
    with pytest.raises(RegistryError, match="difficulty"):
        reg.select(difficulty="L9")


def test_get_unknown_id_raises_a_named_error() -> None:
    reg = Registry.discover(TASKS_ROOT)
    with pytest.raises(RegistryError, match="he.commerce.cart.nope"):
        reg.get("he.commerce.cart.nope")


# ---------- stability


def test_ids_and_json_are_identical_regardless_of_file_order(corpus) -> None:
    root = _three_task_root(corpus)
    files = iter_task_files(root)
    orders = [files, list(reversed(files)), files[1:] + files[:1]]
    outputs = [Registry.discover(root, files=o).to_json() for o in orders]
    assert outputs[0] == outputs[1] == outputs[2]
    assert [r["id"] for r in outputs[0]] == sorted(r["id"] for r in outputs[0])


def test_list_output_is_byte_identical_across_runs() -> None:
    a = _run("rtlenv.task.registry", "--list")
    b = _run("rtlenv.task.registry", "--list")
    assert a.returncode == 0, a.stderr
    assert a.stdout == b.stdout


# ---------- CLI: registry


def test_list_groups_by_suite_then_split_with_counts() -> None:
    proc = _run("rtlenv.task.registry", "--list")
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    header = next(i for i, ln in enumerate(lines) if ln.startswith("commerce / train"))
    assert "(1)" in lines[header] or "(" in lines[header]
    assert any(REAL_ID in ln for ln in lines[header + 1 :])
    assert any(ln.startswith("registry:") and "task(s)" in ln for ln in lines)


def test_list_json_is_machine_readable_and_carries_versions() -> None:
    proc = _run("rtlenv.task.registry", "--list", "--json")
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    row = next(r for r in rows if r["id"] == REAL_ID)
    assert row["version"] == 1 and row["split"] == "train" and row["suite"] == "commerce"
    assert row["path"].startswith("he/commerce/") and row["difficulty"] == "L1"


def test_list_on_a_bad_root_exits_non_zero(tmp_path: Path) -> None:
    proc = _run("rtlenv.task.registry", "--list", "--root", str(tmp_path / "nope"))
    assert proc.returncode != 0
    assert "no such" in proc.stdout + proc.stderr


# ---------- CLI: validate


def test_validate_all_passes_on_the_real_corpus() -> None:
    proc = _run("rtlenv.task.validate", "--all")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"OK {REAL_ID}" in proc.stdout
    assert "0 error(s)" in proc.stdout


def test_validate_all_names_a_task_missing_unchanged_subtrees(corpus) -> None:
    def drop(t: dict[str, Any]) -> None:
        del t["unchanged_subtrees"]

    p = corpus(mutate=drop)
    root = p.parents[3]
    report = validate_all(root)
    assert list(report) == [p.relative_to(root)]
    assert any("unchanged_subtrees" in e for e in report[p.relative_to(root)])
    proc = _run("rtlenv.task.validate", "--all", "--root", str(root))
    assert proc.returncode == 1
    assert (
        "unchanged_subtrees" in proc.stdout
        and "he/commerce/cart_add_two_apply_welcome10" in proc.stdout
    )


def test_validate_single_file_and_unreadable_yaml(corpus, write_task_fn, tmp_path: Path) -> None:
    p = corpus()
    assert validate_file(p, p.parents[3]) == []
    proc = _run("rtlenv.task.validate", str(p), "--root", str(p.parents[3]))
    assert proc.returncode == 0, proc.stdout
    bad = write_task_fn(tmp_path / "other", "he/commerce/broken", load_real_task())
    bad.write_text("id: [unclosed\n", encoding="utf-8")
    errors = validate_file(bad, tmp_path / "other")
    assert errors and "yaml" in errors[0].lower()


def test_validate_all_reports_a_misplaced_task(corpus) -> None:
    p = corpus(rel="he/commerce/cart_add_two_apply_welcome10_copy")
    root = p.parents[3]
    proc = _run("rtlenv.task.validate", "--all", "--root", str(root))
    assert proc.returncode == 1 and "task directory" in proc.stdout


# ---------- harness integration


def test_harness_honours_a_raised_per_task_fixture_minimum(corpus) -> None:
    def raise_min(t: dict[str, Any]) -> None:
        t["fixtures"] = {"plausibly_wrong": 40}

    p = corpus(mutate=raise_min)
    entry = discover_tasks(p.parents[3])[0]
    problems = check_minimums(entry)
    assert any("plausibly_wrong" in m and "40" in m for m in problems), problems


def test_harness_rejects_a_task_that_lacks_authoring_fields(corpus) -> None:
    def drop(t: dict[str, Any]) -> None:
        del t["cheat_surface"]

    p = corpus(mutate=drop)
    entry = discover_tasks(p.parents[3])[0]
    assert any("cheat_surface" in m for m in check_minimums(entry))


def test_harness_floor_is_the_documented_minimum() -> None:
    assert MINIMUMS == {"correct": 1, "clearly_wrong": 1, "plausibly_wrong": 3}
