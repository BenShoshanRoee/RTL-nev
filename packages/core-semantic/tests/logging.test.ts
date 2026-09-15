import { describe, expect, it } from "vitest";
import { createLogger, jsonSink, type LogRecord } from "../src/logging";

const fixedClock = () => new Date("2026-09-15T12:00:00.000Z");

describe("createLogger", () => {
  it("emits one record carrying run_id, seed, task_id and component", () => {
    const records: LogRecord[] = [];
    const log = createLogger(
      { run_id: "run-1", seed: 12345, task_id: "he.commerce.t1", component: "judge" },
      { sink: (r) => records.push(r), clock: fixedClock },
    );
    log.info("verdict computed", { reward: 1 });
    expect(records).toEqual([
      {
        ts: "2026-09-15T12:00:00.000Z",
        level: "info",
        run_id: "run-1",
        seed: 12345,
        task_id: "he.commerce.t1",
        component: "judge",
        msg: "verdict computed",
        reward: 1,
      },
    ]);
  });
  it("serialises to a single JSON line with a fixed key order", () => {
    const lines: string[] = [];
    const log = createLogger(
      { run_id: "r", seed: 1, component: "c" },
      { sink: jsonSink((line) => lines.push(line)), clock: fixedClock },
    );
    log.warn("w", { z: 1, a: 2 });
    expect(lines.length).toBe(1);
    expect(lines[0]).not.toContain("\n");
    const parsed = JSON.parse(lines[0] ?? "");
    expect(Object.keys(parsed)).toEqual(["ts", "level", "run_id", "seed", "component", "msg", "a", "z"]);
    expect(parsed.run_id).toBe("r");
    expect(parsed.seed).toBe(1);
  });
  it("child loggers inherit and override context", () => {
    const records: LogRecord[] = [];
    const log = createLogger(
      { run_id: "r", seed: 1, component: "runner" },
      { sink: (r) => records.push(r), clock: fixedClock },
    );
    log.child({ task_id: "t9", component: "judge" }).error("boom");
    expect(records[0]?.task_id).toBe("t9");
    expect(records[0]?.component).toBe("judge");
    expect(records[0]?.run_id).toBe("r");
    expect(records[0]?.level).toBe("error");
  });
  it("extra fields cannot overwrite the context fields", () => {
    const records: LogRecord[] = [];
    const log = createLogger(
      { run_id: "r", seed: 1, component: "c" },
      { sink: (r) => records.push(r), clock: fixedClock },
    );
    log.info("m", { run_id: "spoofed", seed: 999 } as Record<string, unknown>);
    expect(records[0]?.run_id).toBe("r");
    expect(records[0]?.seed).toBe(1);
  });
});
