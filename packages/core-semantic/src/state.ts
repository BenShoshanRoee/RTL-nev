/**
 * State is one JSON-serialisable tree: objects, arrays, strings, integers, booleans, null.
 * Numbers must be integers (money is minor units; JS and Python format floats differently,
 * which would break cross-language hashing). Collections of entities are records keyed by
 * id, not arrays, so diffs stay stable under insertion.
 *
 * canonicalJson: sorted keys, no whitespace, unicode kept. hashState: SHA-256 of it.
 * diff/patch: leaf-level structured changeset; patch(before, diff(before, after)) === after.
 * Mirrored by bench/rtlenv/domain_protocol.py; the two agree byte for byte
 * (tests/fixtures/state-parity.json).
 */

import { sha256Hex } from "./rng";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export type PathSegment = string | number;
export type Path = readonly PathSegment[];

export interface Change {
  path: PathSegment[];
  kind: "added" | "removed" | "changed";
  before?: JsonValue;
  after?: JsonValue;
}

export interface Changeset {
  changes: Change[];
}

export class InvalidStateError extends TypeError {}

function isObject(v: JsonValue | undefined): v is JsonObject {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function quote(s: string): string {
  return JSON.stringify(s);
}

/** Canonical form: sorted keys, compact, unicode kept. Throws on non-integer numbers. */
export function canonicalJson(value: JsonValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new InvalidStateError(`state numbers must be safe integers, got ${value}`);
    return String(value);
  }
  if (typeof value === "string") return quote(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  if (isObject(value)) {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => quote(k) + ":" + canonicalJson(value[k] as JsonValue)).join(",") + "}";
  }
  throw new InvalidStateError(`not a JSON value: ${typeof value}`);
}

export function hashState(value: JsonValue): string {
  return sha256Hex(canonicalJson(value));
}

/** Independent deep copy. */
export function snapshot<T extends JsonValue>(value: T): T {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map((v) => snapshot(v)) as T;
  const out: JsonObject = {};
  for (const k of Object.keys(value)) out[k] = snapshot((value as JsonObject)[k] as JsonValue);
  return out as T;
}

/** A branch point for parallel rollouts: an independent copy. */
export const fork = snapshot;

export function deepFreeze<T extends JsonValue>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const v of Object.values(value)) deepFreeze(v as JsonValue);
  }
  return value;
}

export function deepEqual(a: JsonValue | undefined, b: JsonValue | undefined): boolean {
  if (a === b) return true;
  if (a === undefined || b === undefined) return false;
  return canonicalJson(a) === canonicalJson(b);
}

function comparePaths(a: Path, b: Path): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i] as PathSegment;
    const y = b[i] as PathSegment;
    if (x === y) continue;
    if (typeof x === "number" && typeof y === "number") return x - y;
    const xs = String(x);
    const ys = String(y);
    return xs < ys ? -1 : 1;
  }
  return a.length - b.length;
}

function collect(before: JsonValue | undefined, after: JsonValue | undefined, path: PathSegment[], out: Change[]): void {
  if (before === undefined) {
    out.push({ path, kind: "added", after: snapshot(after as JsonValue) });
    return;
  }
  if (after === undefined) {
    out.push({ path, kind: "removed", before: snapshot(before) });
    return;
  }
  if (isObject(before) && isObject(after)) {
    const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();
    for (const k of keys) collect(before[k], after[k], [...path, k], out);
    return;
  }
  if (Array.isArray(before) && Array.isArray(after)) {
    const n = Math.max(before.length, after.length);
    for (let i = 0; i < n; i++) collect(before[i], after[i], [...path, i], out);
    return;
  }
  if (!deepEqual(before, after)) {
    out.push({ path, kind: "changed", before: snapshot(before), after: snapshot(after) });
  }
}

/** Leaf-level structured diff, sorted by path. Objects recurse by key, arrays by index. */
export function diff(before: JsonValue, after: JsonValue): Changeset {
  const out: Change[] = [];
  collect(before, after, [], out);
  out.sort((a, b) => comparePaths(a.path, b.path));
  return { changes: out };
}

export function isEmpty(changeset: Changeset): boolean {
  return changeset.changes.length === 0;
}

export function getPath(value: JsonValue, path: Path): JsonValue | undefined {
  let cur: JsonValue | undefined = value;
  for (const seg of path) {
    if (cur === undefined || cur === null || typeof cur !== "object") return undefined;
    cur = Array.isArray(cur) ? cur[seg as number] : (cur as JsonObject)[seg as string];
  }
  return cur;
}

function setPath(root: JsonValue, path: Path, value: JsonValue | undefined): JsonValue {
  if (path.length === 0) return value === undefined ? null : value;
  let cur = root as JsonObject | JsonValue[];
  for (let i = 0; i < path.length - 1; i++) {
    const seg = path[i] as PathSegment;
    let next = Array.isArray(cur) ? cur[seg as number] : (cur as JsonObject)[seg as string];
    if (next === undefined || next === null || typeof next !== "object") {
      next = typeof path[i + 1] === "number" ? [] : {};
      if (Array.isArray(cur)) cur[seg as number] = next;
      else (cur as JsonObject)[seg as string] = next;
    }
    cur = next as JsonObject | JsonValue[];
  }
  const last = path[path.length - 1] as PathSegment;
  if (Array.isArray(cur)) {
    if (value === undefined) cur.splice(last as number, 1);
    else cur[last as number] = value;
  } else if (value === undefined) delete (cur as JsonObject)[last as string];
  else (cur as JsonObject)[last as string] = value;
  return root;
}

/** Apply a changeset to a copy of `before`. Removals inside arrays are applied last-first. */
export function patch(before: JsonValue, changeset: Changeset): JsonValue {
  let root = snapshot(before);
  const arranged = [...changeset.changes].sort((a, b) => comparePaths(b.path, a.path)); // deepest/last first
  for (const c of arranged) {
    root = setPath(root, c.path, c.kind === "removed" ? undefined : snapshot(c.after as JsonValue));
  }
  return root;
}

/** Changes that fall under any of the given subtrees. Empty means those subtrees are untouched. */
export function unchanged(before: JsonValue, after: JsonValue, subtrees: readonly Path[]): Change[] {
  const cs = diff(before, after);
  return cs.changes.filter((c) => subtrees.some((p) => p.length <= c.path.length && p.every((seg, i) => seg === c.path[i])));
}
