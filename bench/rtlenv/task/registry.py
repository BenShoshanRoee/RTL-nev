"""Task registry: discovery, validation and selection of every task under a root.

The registry is the one walker of ``bench/tasks`` (the meta-test harness reuses it), the
source packaging reads to expose ``language`` / ``split`` / pathology filters (8.1.1), and the
list a licence grant or compatibility check keys on by ``id`` and ``version`` (8.1.3, 10.1.1).
It is strict: a root containing any invalid or duplicate task yields no registry at all.
Ordering is by id alone, so output never depends on filesystem order.

    uv run python -m rtlenv.task.registry --list [--json] [--root bench/tasks]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rtlenv.task.schema import DIFFICULTIES, SPLITS, TaskDefinition, validate_definition
from rtlenv.task.validate import TaskFileError, load_task_file, validate_file

BENCH = Path(__file__).resolve().parents[2]
TASKS_ROOT = BENCH / "tasks"


class RegistryError(ValueError):
    """The root cannot become a registry, or a lookup or filter is invalid."""


@dataclass(frozen=True)
class TaskRecord:
    id: str
    version: int
    language: str
    suite: str
    domain: str
    split: str
    difficulty: str
    deprecated: bool
    path: Path  # the task directory
    task: dict[str, Any]  # the raw task object, what the judge consumes
    definition: TaskDefinition

    def to_json(self, root: Path) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "language": self.language,
            "suite": self.suite,
            "domain": self.domain,
            "split": self.split,
            "difficulty": self.difficulty,
            "deprecated": self.deprecated,
            "path": self.path.resolve().relative_to(root.resolve()).as_posix(),
        }


def iter_task_files(root: Path) -> list[Path]:
    """Every task.yaml under ``root``, sorted by relative POSIX path."""
    root = Path(root)
    if not root.is_dir():
        raise RegistryError(f"no such task root: {root}")
    return sorted(root.rglob("task.yaml"), key=lambda p: p.relative_to(root).as_posix())


def load_record(task_file: Path, root: Path) -> TaskRecord:
    errors = validate_file(task_file, root)
    if errors:
        rel = task_file.resolve().relative_to(Path(root).resolve()).as_posix()
        raise RegistryError("\n".join(f"{rel}: {e}" for e in errors))
    task = load_task_file(task_file)
    d = validate_definition(task)
    return TaskRecord(
        id=d.id,
        version=d.version,
        language=d.language,
        suite=d.suite,
        domain=d.domain,
        split=d.split,
        difficulty=d.difficulty_target,
        deprecated=d.deprecated,
        path=task_file.parent,
        task=task,
        definition=d,
    )


class Registry:
    def __init__(self, records: Iterable[TaskRecord], root: Path) -> None:
        self.root = Path(root)
        self._records: tuple[TaskRecord, ...] = tuple(sorted(records, key=lambda r: r.id))
        self._by_id = {r.id: r for r in self._records}

    @classmethod
    def discover(cls, root: Path = TASKS_ROOT, files: Iterable[Path] | None = None) -> Registry:
        """Build a registry from every task under ``root``. ``files`` overrides discovery
        (used to prove the result is independent of file order)."""
        root = Path(root)
        files = list(files) if files is not None else iter_task_files(root)
        if not files:
            raise RegistryError(f"no tasks under {root}")
        records: list[TaskRecord] = []
        errors: list[str] = []
        for f in files:
            try:
                records.append(load_record(f, root))
            except (RegistryError, TaskFileError) as e:
                errors.append(str(e))
        if errors:
            raise RegistryError("\n".join(sorted(errors)))
        by_id: dict[str, list[TaskRecord]] = {}
        for r in records:
            by_id.setdefault(r.id, []).append(r)
        dupes = {k: v for k, v in by_id.items() if len(v) > 1}
        if dupes:
            lines = [
                f"duplicate id {k!r} declared by "
                + ", ".join(sorted(r.path.relative_to(root).as_posix() for r in v))
                for k, v in sorted(dupes.items())
            ]
            raise RegistryError("\n".join(lines))
        return cls(records, root)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    def ids(self) -> list[str]:
        return [r.id for r in self._records]

    def get(self, task_id: str) -> TaskRecord:
        try:
            return self._by_id[task_id]
        except KeyError:
            raise RegistryError(f"unknown task id {task_id!r}") from None

    def select(
        self,
        *,
        language: str | None = None,
        suite: str | None = None,
        domain: str | None = None,
        split: str | None = None,
        difficulty: str | None = None,
        include_deprecated: bool = False,
    ) -> list[TaskRecord]:
        if split is not None and split not in SPLITS:
            raise RegistryError(f"split must be one of {list(SPLITS)}, got {split!r}")
        if difficulty is not None and difficulty not in DIFFICULTIES:
            raise RegistryError(
                f"difficulty must be one of {list(DIFFICULTIES)}, got {difficulty!r}"
            )
        out = []
        for r in self._records:
            if r.deprecated and not include_deprecated:
                continue
            if language is not None and r.language != language:
                continue
            if suite is not None and r.suite != suite:
                continue
            if domain is not None and r.domain != domain:
                continue
            if split is not None and r.split != split:
                continue
            if difficulty is not None and r.difficulty != difficulty:
                continue
            out.append(r)
        return out

    def splits(self) -> dict[str, list[str]]:
        """Every split, in the documented order, with its task ids (deprecated included)."""
        return {s: [r.id for r in self._records if r.split == s] for s in SPLITS}

    def grouped(self) -> dict[str, dict[str, list[TaskRecord]]]:
        """suite -> split -> records, suites and splits sorted, records by id."""
        out: dict[str, dict[str, list[TaskRecord]]] = {}
        for r in self._records:
            out.setdefault(r.suite, {}).setdefault(r.split, []).append(r)
        return {s: dict(sorted(v.items())) for s, v in sorted(out.items())}

    def to_json(self) -> list[dict[str, Any]]:
        return [r.to_json(self.root) for r in self._records]


def _format_list(reg: Registry) -> str:
    lines: list[str] = []
    for suite, by_split in reg.grouped().items():
        for split, records in by_split.items():
            lines.append(f"{suite} / {split} ({len(records)})")
            for r in records:
                flag = "  [deprecated]" if r.deprecated else ""
                lines.append(f"  {r.id}  v{r.version}  {r.difficulty}{flag}")
    n_dep = sum(1 for r in reg if r.deprecated)
    lines.append(
        f"registry: {len(reg)} task(s), {len(reg.grouped())} suite(s),"
        f" {len(SPLITS)} split(s), {n_dep} deprecated"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=TASKS_ROOT)
    ap.add_argument("--list", action="store_true", help="list tasks grouped by suite and split")
    ap.add_argument("--json", action="store_true", help="with --list: emit JSON rows")
    args = ap.parse_args(argv)
    if not args.list:
        ap.print_usage()
        return 2
    try:
        reg = Registry.discover(args.root)
    except RegistryError as e:
        print(f"registry: {e}")
        return 1
    if args.json:
        print(json.dumps(reg.to_json(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(_format_list(reg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
