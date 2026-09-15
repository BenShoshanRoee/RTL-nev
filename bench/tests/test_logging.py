"""Structured logging contract for rtlenv.logging."""

from __future__ import annotations

import datetime as dt
import json

from rtlenv.logging import get_logger, json_line

FIXED = dt.datetime(2026, 9, 15, 12, 0, 0, tzinfo=dt.UTC)


def test_record_carries_run_id_seed_task_id_component() -> None:
    records: list[dict] = []
    log = get_logger(
        "judge",
        run_id="run-1",
        seed=12345,
        task_id="he.commerce.t1",
        sink=records.append,
        clock=lambda: FIXED,
    )
    log.info("verdict computed", reward=1)
    assert records == [
        {
            "ts": "2026-09-15T12:00:00.000Z",
            "level": "info",
            "run_id": "run-1",
            "seed": 12345,
            "task_id": "he.commerce.t1",
            "component": "judge",
            "msg": "verdict computed",
            "reward": 1,
        }
    ]


def test_json_line_has_fixed_key_order_and_no_newline() -> None:
    records: list[dict] = []
    log = get_logger("c", run_id="r", seed=1, sink=records.append, clock=lambda: FIXED)
    log.warning("w", z=1, a=2)
    line = json_line(records[0])
    assert "\n" not in line
    parsed = json.loads(line)
    assert list(parsed) == ["ts", "level", "run_id", "seed", "component", "msg", "a", "z"]


def test_bind_inherits_and_overrides_context() -> None:
    records: list[dict] = []
    log = get_logger("runner", run_id="r", seed=1, sink=records.append, clock=lambda: FIXED)
    log.bind(task_id="t9", component="judge").error("boom")
    assert records[0]["task_id"] == "t9"
    assert records[0]["component"] == "judge"
    assert records[0]["run_id"] == "r"
    assert records[0]["level"] == "error"


def test_extra_fields_cannot_overwrite_context() -> None:
    records: list[dict] = []
    log = get_logger("c", run_id="r", seed=1, sink=records.append, clock=lambda: FIXED)
    log.info("m", **{"run_id": "spoofed", "seed": 999})
    assert records[0]["run_id"] == "r"
    assert records[0]["seed"] == 1
