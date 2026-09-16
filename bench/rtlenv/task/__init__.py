"""Task contract, validator and registry.

The schema exports import eagerly. Registry and validator names resolve lazily on first access
so that ``python -m rtlenv.task.registry`` / ``python -m rtlenv.task.validate`` do not import
the module they are about to run (Python warns when a package __init__ does that).
"""

from __future__ import annotations

from typing import Any

from rtlenv.task.schema import (
    DIFFICULTIES,
    FIXTURE_FLOOR,
    SPLITS,
    TaskContract,
    TaskContractError,
    TaskDefinition,
    TaskSetup,
    validate_definition,
    validate_task,
)

_LAZY = {
    "TASKS_ROOT": "rtlenv.task.registry",
    "Registry": "rtlenv.task.registry",
    "RegistryError": "rtlenv.task.registry",
    "TaskRecord": "rtlenv.task.registry",
    "iter_task_files": "rtlenv.task.registry",
    "TaskFileError": "rtlenv.task.validate",
    "check_layout": "rtlenv.task.validate",
    "task_dir_name": "rtlenv.task.validate",
    "validate_all": "rtlenv.task.validate",
    "validate_file": "rtlenv.task.validate",
}

__all__ = [
    "DIFFICULTIES",
    "FIXTURE_FLOOR",
    "SPLITS",
    "TaskContract",
    "TaskContractError",
    "TaskDefinition",
    "TaskSetup",
    "validate_definition",
    "validate_task",
    *sorted(_LAZY),
]


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
