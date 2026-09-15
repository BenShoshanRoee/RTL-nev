/**
 * Operations are pure: (state, params, ctx) -> new state. The input state is frozen, so a
 * mutating implementation throws. `sample` proposes legal params for a state, which is what
 * lets the conformance suite and property tests drive any domain blind.
 */

import type { Invariant, InvariantViolation } from "./invariant.js";
import { checkInvariants } from "./invariant.js";
import { isCurrency } from "./money.js";
import type { Rng } from "./rng.js";
import { deepFreeze, diff, hashState, snapshot, type Changeset, type JsonObject, type JsonValue } from "./state.js";

export type FieldSpec =
  | "string"
  | "integer"
  | "boolean"
  | "money"
  | { kind: "enum"; values: readonly string[] }
  | { kind: "list"; of: FieldSpec }
  | { kind: "ref"; entity: string }
  | { kind: "record"; entity: string };

export interface EntitySchema {
  /** Field holding the identity of a record; collections are keyed by it. */
  readonly key: string;
  readonly fields: Record<string, FieldSpec>;
}

export interface OperationContext {
  readonly rng: Rng;
  /** Injected clock, milliseconds since the epoch. Never the wall clock inside a domain. */
  readonly now: () => number;
}

export type Precondition = { ok: true } | { ok: false; reason: string };

export interface OperationDefinition<S extends JsonObject, P extends JsonObject = JsonObject> {
  readonly name: string;
  readonly description: string;
  readonly params: Record<string, FieldSpec>;
  precondition(state: Readonly<S>, params: P): Precondition;
  apply(state: Readonly<S>, params: P, ctx: OperationContext): S;
  /** Legal params for this state, or null if none exist. Draws only from `rng`. */
  sample(state: Readonly<S>, rng: Rng): P | null;
}

export interface TraceEntry {
  op: string;
  params: JsonObject;
  beforeHash: string;
  afterHash: string;
  changes: Changeset;
}

export type OperationResult<S extends JsonObject> =
  | { ok: true; state: S; trace: TraceEntry }
  | { ok: false; reason: string; violations?: InvariantViolation[]; state: Readonly<S> };

export class MutationError extends Error {}

function typeOk(spec: FieldSpec, value: JsonValue | undefined): boolean {
  if (value === undefined) return false;
  if (spec === "string") return typeof value === "string";
  if (spec === "integer") return typeof value === "number" && Number.isSafeInteger(value);
  if (spec === "boolean") return typeof value === "boolean";
  if (spec === "money") {
    return (
      typeof value === "object" && value !== null && !Array.isArray(value) &&
      Number.isSafeInteger((value as JsonObject)["minor"] as number) &&
      typeof (value as JsonObject)["currency"] === "string" && isCurrency((value as JsonObject)["currency"] as string)
    );
  }
  if (spec.kind === "enum") return typeof value === "string" && spec.values.includes(value);
  if (spec.kind === "list") return Array.isArray(value) && value.every((v) => typeOk(spec.of, v));
  if (spec.kind === "ref") return typeof value === "string";
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Every declared param present with the declared type; no undeclared params. */
export function validateParams(spec: Record<string, FieldSpec>, params: JsonObject): string | null {
  for (const [name, fs] of Object.entries(spec)) {
    if (!typeOk(fs, params[name])) return `param ${name}: expected ${typeof fs === "string" ? fs : fs.kind}`;
  }
  for (const name of Object.keys(params)) if (!(name in spec)) return `param ${name}: not declared`;
  return null;
}

export interface Executable<S extends JsonObject> {
  readonly operations: Record<string, OperationDefinition<S, JsonObject>>;
  readonly invariants: readonly Invariant<S>[];
}

/**
 * Validate params, check the precondition, apply on a frozen copy, check invariants.
 * Any failure returns ok:false with the untouched input state. A mutating `apply` throws.
 */
export function execute<S extends JsonObject>(
  domain: Executable<S>,
  state: Readonly<S>,
  name: string,
  params: JsonObject,
  ctx: OperationContext,
): OperationResult<S> {
  const op = domain.operations[name];
  if (!op) return { ok: false, reason: `unknown operation ${name}`, state };
  const bad = validateParams(op.params, params);
  if (bad) return { ok: false, reason: bad, state };
  const pre = op.precondition(state, params);
  if (!pre.ok) return { ok: false, reason: pre.reason, state };
  const frozen = deepFreeze(snapshot(state as JsonValue) as S);
  const beforeHash = hashState(frozen);
  let next: S;
  try {
    next = op.apply(frozen, params, ctx);
  } catch (e) {
    if (e instanceof TypeError) throw new MutationError(`operation ${name} mutated its input state: ${e.message}`);
    throw e;
  }
  if (hashState(frozen) !== beforeHash) throw new MutationError(`operation ${name} mutated its input state`);
  const violations = checkInvariants(domain, next);
  if (violations.length) return { ok: false, reason: `invariant violated: ${violations.map((v) => v.id).join(", ")}`, violations, state };
  const result = snapshot(next as JsonValue) as S;
  return {
    ok: true,
    state: result,
    trace: { op: name, params: snapshot(params), beforeHash, afterHash: hashState(result), changes: diff(frozen, result) },
  };
}
