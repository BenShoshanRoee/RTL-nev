/**
 * Structured logging. One JSON object per line: ts, level, run_id, seed, task_id, component,
 * msg, then extra fields in sorted key order. Sink and clock are injectable so tests assert
 * exact bytes and generated data never touches the wall clock. No SaaS: logs are lines.
 *
 * Mirrors bench/rtlenv/logging.py.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogContext {
  run_id: string;
  seed: number;
  task_id?: string;
  component: string;
}

export interface LogRecord extends LogContext {
  ts: string;
  level: LogLevel;
  msg: string;
  [extra: string]: unknown;
}

export type LogSink = (record: LogRecord) => void;

export interface LoggerOptions {
  sink?: LogSink;
  /** Injected clock; defaults to the wall clock. */
  clock?: () => Date;
  /** Minimum level emitted; defaults to debug. */
  level?: LogLevel;
}

export interface Logger {
  debug(msg: string, fields?: Record<string, unknown>): void;
  info(msg: string, fields?: Record<string, unknown>): void;
  warn(msg: string, fields?: Record<string, unknown>): void;
  error(msg: string, fields?: Record<string, unknown>): void;
  child(ctx: Partial<LogContext>): Logger;
  readonly context: Readonly<LogContext>;
}

const LEVEL_RANK: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };
const CONTEXT_KEYS = ["ts", "level", "run_id", "seed", "task_id", "component", "msg"] as const;

/** Serialise a record as one line with a fixed leading key order and sorted extras. */
export function toJsonLine(record: LogRecord): string {
  const arranged: Record<string, unknown> = {};
  for (const k of CONTEXT_KEYS) if (record[k] !== undefined) arranged[k] = record[k];
  const extras = Object.keys(record)
    .filter((k) => !(CONTEXT_KEYS as readonly string[]).includes(k))
    .sort();
  for (const k of extras) arranged[k] = record[k];
  return JSON.stringify(arranged);
}

/** A sink writing JSON lines through `write` (default: console.log). */
export function jsonSink(write: (line: string) => void = consoleWrite): LogSink {
  return (record) => write(toJsonLine(record));
}

/** A human-readable sink for interactive development. */
export function prettySink(write: (line: string) => void = consoleWrite): LogSink {
  return (record) => {
    const { ts, level, run_id, seed, task_id, component, msg, ...extras } = record;
    const head = `${ts} ${level.toUpperCase().padEnd(5)} [${component}] run=${run_id} seed=${seed}`;
    const task = task_id ? ` task=${task_id}` : "";
    const rest = Object.keys(extras).length ? " " + JSON.stringify(extras) : "";
    write(`${head}${task} ${msg}${rest}`);
  };
}

interface MaybeNode {
  process?: { env?: Record<string, string | undefined>; stdout?: { isTTY?: boolean } };
  console?: { log: (line: string) => void };
}

/** Write a line to the host console without depending on DOM or Node type libraries. */
function consoleWrite(line: string): void {
  (globalThis as unknown as MaybeNode).console?.log(line);
}

/** JSON unless running interactively outside production: then pretty. */
export function defaultSink(): LogSink {
  const node = globalThis as unknown as MaybeNode;
  const interactive =
    node.process?.stdout?.isTTY === true &&
    node.process.env?.["NODE_ENV"] !== "production" &&
    node.process.env?.["RTLENV_LOG_FORMAT"] !== "json";
  return interactive ? prettySink() : jsonSink();
}

export function createLogger(ctx: LogContext, opts: LoggerOptions = {}): Logger {
  const sink = opts.sink ?? defaultSink();
  const clock = opts.clock ?? (() => new Date());
  const minRank = LEVEL_RANK[opts.level ?? "debug"];
  const context: LogContext = { ...ctx };

  const emit = (level: LogLevel, msg: string, fields: Record<string, unknown> | undefined) => {
    if (LEVEL_RANK[level] < minRank) return;
    const record: LogRecord = { ...fields, ts: clock().toISOString(), level, ...context, msg };
    sink(record);
  };
  return {
    context,
    debug: (m, f) => emit("debug", m, f),
    info: (m, f) => emit("info", m, f),
    warn: (m, f) => emit("warn", m, f),
    error: (m, f) => emit("error", m, f),
    child: (c) => createLogger({ ...context, ...c }, { sink, clock, level: opts.level ?? "debug" }),
  };
}
