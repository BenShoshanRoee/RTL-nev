"""Per-file task validation: schema plus layout.

A task lives at ``<root>/<lang>/<suite>/<task>/task.yaml`` with its transcripts in a sibling
``fixtures/`` directory. The directory is part of the contract: the language and suite
directories equal the id's first two segments and the task directory equals the remaining
segments joined by ``_`` (``he.commerce.cart.add_two`` lives in ``he/commerce/cart_add_two``),
so a task is located from its id alone and a moved task cannot silently change identity.

    uv run python -m rtlenv.task.validate --all [--root bench/tasks]
    uv run python -m rtlenv.task.validate <task.yaml>... [--root bench/tasks]

Exit 0 when every task validates, 1 when any error is reported, 2 on a bad invocation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from rtlenv.task.schema import TaskContractError, TaskDefinition, validate_definition


class TaskFileError(ValueError):
    """The task file cannot be read as a task object. The message names the file."""


def load_task_file(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise TaskFileError(f"YAML parse error: {e}") from e
    except OSError as e:
        raise TaskFileError(f"cannot read: {e}") from e
    if not isinstance(data, dict):
        raise TaskFileError(f"task.yaml must be a mapping, got {type(data).__name__}")
    return data


def task_dir_name(task_id: str) -> str:
    """The directory a task id lives in: its segments after the suite, joined by ``_``."""
    return "_".join(task_id.split(".")[2:])


def _relative(task_file: Path, root: Path) -> Path:
    try:
        return task_file.resolve().relative_to(root.resolve())
    except ValueError as e:
        raise TaskFileError(f"{task_file} is not under the task root {root}") from e


def check_layout(
    task_file: Path, root: Path, definition: TaskDefinition | None = None
) -> list[str]:
    """Errors in how ``task_file`` sits under ``root``. Loads and validates the file when no
    definition is given, so the returned list is complete for that file."""
    rel = _relative(task_file, root)
    parts = rel.parts
    if len(parts) != 4 or parts[-1] != "task.yaml":
        return [f"{rel.as_posix()}: task.yaml must sit at <lang>/<suite>/<task>/task.yaml"]
    if definition is None:
        try:
            definition = validate_definition(load_task_file(task_file))
        except (TaskFileError, TaskContractError) as e:
            return [str(e)]
    lang_dir, suite_dir, task_dir = parts[:3]
    errors: list[str] = []
    if lang_dir != definition.language:
        errors.append(
            f"language directory {lang_dir!r} must equal the id's language {definition.language!r}"
        )
    if suite_dir != definition.suite:
        errors.append(f"suite directory {suite_dir!r} must equal suite {definition.suite!r}")
    name = task_dir_name(definition.id)
    if task_dir != name:
        errors.append(
            f"task directory {task_dir!r} must be {name!r} (the id's segments after the suite,"
            " joined by '_')"
        )
    fixtures = task_file.parent / "fixtures"
    if not fixtures.is_dir() or not any(fixtures.glob("*.json")):
        errors.append("fixtures/: missing or empty; every task ships its transcripts beside it")
    return errors


def validate_file(task_file: Path, root: Path) -> list[str]:
    """Every error for one task file: read, schema, layout. Empty means valid."""
    try:
        task = load_task_file(task_file)
    except TaskFileError as e:
        return [str(e)]
    try:
        definition = validate_definition(task)
    except TaskContractError as e:
        return [str(e)]
    try:
        return check_layout(task_file, root, definition)
    except TaskFileError as e:
        return [str(e)]


def validate_all(root: Path) -> dict[Path, list[str]]:
    """Errors per task file (relative to ``root``), for files with errors only.

    Two files cannot declare one id: the layout rule maps an id to exactly one directory, so
    duplicate detection lives in the registry, whose explicit file list can repeat a file.
    """
    from rtlenv.task.registry import iter_task_files

    report: dict[Path, list[str]] = {}
    for f in iter_task_files(root):
        errors = validate_file(f, root)
        if errors:
            report[_relative(f, root)] = errors
    return dict(sorted(report.items()))


def main(argv: list[str] | None = None) -> int:
    from rtlenv.task.registry import TASKS_ROOT, RegistryError, iter_task_files

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*", type=Path, help="task.yaml files to validate")
    ap.add_argument("--all", action="store_true", help="validate every task under --root")
    ap.add_argument("--root", type=Path, default=TASKS_ROOT)
    args = ap.parse_args(argv)
    if bool(args.files) == args.all:
        ap.print_usage()
        print("validate: pass either --all or one or more task.yaml paths")
        return 2
    try:
        files = iter_task_files(args.root) if args.all else list(args.files)
        report = validate_all(args.root) if args.all else {}
        if not args.all:
            for f in files:
                errors = validate_file(f, args.root)
                if errors:
                    report[_relative(f, args.root)] = errors
    except (RegistryError, TaskFileError) as e:
        print(f"validate: {e}")
        return 2
    n_errors = 0
    for f in files:
        rel = _relative(f, args.root)
        if rel in report:
            for e in report[rel]:
                n_errors += 1
                print(f"ERROR {rel.as_posix()}: {e}")
        else:
            print(f"OK {load_task_file(f)['id']} ({rel.parent.as_posix()})")
    print(f"validate: {len(files)} task(s), {n_errors} error(s)")
    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
