"""Structured logging. One JSON object per line: ts, level, run_id, seed, task_id, component,
msg, then extra fields in sorted key order. Sink and clock are injectable. No SaaS.

Mirrors packages/core-semantic/src/logging.ts. Named ``rtlenv.logging`` by the plan; import
the standard library module as ``_stdlib_logging`` if ever needed, never bare ``logging``.

Default sink: ``RTLENV_LOG_FILE`` set -> append JSON lines to that file; otherwise JSON to
stderr, or a readable line when stderr is a terminal and ``RTLENV_LOG_FORMAT`` is not ``json``.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from collections.abc import Callable
from typing import Any

Level = str
_RANK = {"debug": 10, "info": 20, "warning": 30, "error": 40}
_CONTEXT_KEYS = ("ts", "level", "run_id", "seed", "task_id", "component", "msg")
Sink = Callable[[dict[str, Any]], None]
Clock = Callable[[], dt.datetime]


def _iso_ms(when: dt.datetime) -> str:
    when = when.astimezone(dt.UTC) if when.tzinfo else when.replace(tzinfo=dt.UTC)
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def json_line(record: dict[str, Any]) -> str:
    """Serialise a record as one line with a fixed leading key order and sorted extras."""
    ordered: dict[str, Any] = {k: record[k] for k in _CONTEXT_KEYS if record.get(k) is not None}
    for k in sorted(k for k in record if k not in _CONTEXT_KEYS):
        ordered[k] = record[k]
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def pretty_line(record: dict[str, Any]) -> str:
    extras = {k: v for k, v in record.items() if k not in _CONTEXT_KEYS}
    task = f" task={record['task_id']}" if record.get("task_id") else ""
    rest = " " + json.dumps(extras, ensure_ascii=False) if extras else ""
    return (
        f"{record['ts']} {record['level'].upper():<7} [{record['component']}] "
        f"run={record['run_id']} seed={record['seed']}{task} {record['msg']}{rest}"
    )


def default_sink() -> Sink:
    path = os.environ.get("RTLENV_LOG_FILE")
    if path:

        def to_file(record: dict[str, Any]) -> None:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json_line(record) + "\n")

        return to_file
    interactive = sys.stderr.isatty() and os.environ.get("RTLENV_LOG_FORMAT") != "json"
    fmt = pretty_line if interactive else json_line
    return lambda record: print(fmt(record), file=sys.stderr)


class Logger:
    __slots__ = ("_clock", "_min", "_sink", "context")

    def __init__(self, context: dict[str, Any], sink: Sink, clock: Clock, level: Level) -> None:
        self.context = dict(context)
        self._sink = sink
        self._clock = clock
        self._min = _RANK[level]

    def _emit(self, level: Level, msg: str, fields: dict[str, Any]) -> None:
        if _RANK[level] < self._min:
            return
        record: dict[str, Any] = dict(fields)
        record.update({"ts": _iso_ms(self._clock()), "level": level})
        record.update(self.context)  # context always wins over extra fields
        record["msg"] = msg
        self._sink(record)

    def debug(self, msg: str, **fields: Any) -> None:
        self._emit("debug", msg, fields)

    def info(self, msg: str, **fields: Any) -> None:
        self._emit("info", msg, fields)

    def warning(self, msg: str, **fields: Any) -> None:
        self._emit("warning", msg, fields)

    def error(self, msg: str, **fields: Any) -> None:
        self._emit("error", msg, fields)

    def bind(self, **context: Any) -> Logger:
        """A child logger with inherited, overridable context."""
        merged = {**self.context, **context}
        return Logger(merged, self._sink, self._clock, _level_name(self._min))


def _level_name(rank: int) -> Level:
    return next(name for name, r in _RANK.items() if r == rank)


def get_logger(
    component: str,
    *,
    run_id: str,
    seed: int,
    task_id: str | None = None,
    sink: Sink | None = None,
    clock: Clock | None = None,
    level: Level = "debug",
) -> Logger:
    context: dict[str, Any] = {"run_id": run_id, "seed": seed, "component": component}
    if task_id is not None:
        context["task_id"] = task_id
    return Logger(
        context,
        sink or default_sink(),
        clock or (lambda: dt.datetime.now(dt.UTC)),
        level,
    )
