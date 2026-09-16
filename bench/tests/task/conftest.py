"""Shared helpers for the task schema, registry and validator tests.

``corpus`` copies the real first task (task.yaml plus every fixture) into a temporary root at
the canonical layout ``<lang>/<suite>/<task>/`` and lets a test mutate the task object before it
is written. Every test therefore starts from a task that is known to validate.
"""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

BENCH = Path(__file__).resolve().parents[2]
TASKS_ROOT = BENCH / "tasks"
REAL_TASK_DIR = TASKS_ROOT / "he" / "commerce" / "cart_add_two_apply_welcome10"


def load_real_task() -> dict[str, Any]:
    return yaml.safe_load((REAL_TASK_DIR / "task.yaml").read_text(encoding="utf-8"))


def write_task(
    root: Path,
    rel: str,
    task: dict[str, Any],
    *,
    with_fixtures: bool = True,
) -> Path:
    """Write ``task`` at ``root/rel/task.yaml`` and copy the real fixtures beside it."""
    task_dir = root / rel
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.yaml").write_text(
        yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    if with_fixtures:
        shutil.copytree(REAL_TASK_DIR / "fixtures", task_dir / "fixtures", dirs_exist_ok=True)
    return task_dir / "task.yaml"


@pytest.fixture
def write_task_fn() -> Callable[..., Path]:
    return write_task


@pytest.fixture
def corpus(tmp_path: Path) -> Callable[..., Path]:
    """Factory: ``corpus(mutate=None, rel=None, with_fixtures=True) -> task.yaml path``.

    ``mutate`` receives a deep copy of the real task object and may edit it in place or
    return a replacement. The temporary root is ``tmp_path``.
    """

    def make(
        mutate: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        rel: str | None = None,
        with_fixtures: bool = True,
    ) -> Path:
        task = copy.deepcopy(load_real_task())
        if mutate is not None:
            replaced = mutate(task)
            if replaced is not None:
                task = replaced
        rel = rel or "he/commerce/cart_add_two_apply_welcome10"
        return write_task(tmp_path, rel, task, with_fixtures=with_fixtures)

    return make


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
