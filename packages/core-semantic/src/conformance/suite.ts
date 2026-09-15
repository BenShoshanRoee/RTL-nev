/**
 * Test-runner-agnostic conformance checks any domain must pass. Each domain's test file turns
 * the results into test cases:
 *
 *   for (const c of conformanceChecks(domain, { seed: 1 })) it(c.id, () => expect(c.ok, c.detail).toBe(true));
 *
 * The insurance stub and the commerce domain run the identical checks; if the core ever
 * absorbs one domain's assumptions, the other fails here.
 */

import type { DomainDefinition } from "../domain.js";
import { checkInvariants } from "../invariant.js";
import { execute, type OperationContext } from "../operation.js";
import { Rng } from "../rng.js";
import { canonicalJson, diff, hashState, isEmpty, patch, type JsonObject, type JsonValue } from "../state.js";

export interface ConformanceCheck {
  id: string;
  ok: boolean;
  detail: string;
}

export interface ConformanceOptions {
  seed?: number;
  /** Number of random operation sequences to drive. */
  sequences?: number;
  /** Operations per sequence. */
  length?: number;
}

function check(id: string, fn: () => string | null): ConformanceCheck {
  try {
    const detail = fn();
    return { id, ok: detail === null, detail: detail ?? "ok" };
  } catch (e) {
    return { id, ok: false, detail: `threw: ${(e as Error).message}` };
  }
}

export function conformanceChecks<S extends JsonObject>(
  domain: DomainDefinition<S>,
  opts: ConformanceOptions = {},
): ConformanceCheck[] {
  const seed = opts.seed ?? 1;
  const sequences = opts.sequences ?? 20;
  const length = opts.length ?? 10;
  const root = new Rng(seed, `conformance:${domain.id}`);
  const out: ConformanceCheck[] = [];

  out.push(check("declaration: id, version, entities, operations, invariants present", () => {
    if (!domain.id) return "missing id";
    if (!/^\d+\.\d+\.\d+/.test(domain.version)) return `version ${domain.version} is not semver`;
    if (Object.keys(domain.entities).length === 0) return "no entities";
    if (Object.keys(domain.operations).length === 0) return "no operations";
    for (const [name, op] of Object.entries(domain.operations)) {
      if (op.name !== name) return `operation key ${name} != name ${op.name}`;
      if (typeof op.sample !== "function") return `operation ${name} has no sample()`;
    }
    for (const [name, e] of Object.entries(domain.entities)) if (!(e.key in e.fields)) return `entity ${name}: key ${e.key} is not a field`;
    return null;
  }));

  out.push(check("seedState: canonical JSON round-trip (integers only, sorted keys)", () => {
    const s = domain.seedState(root.child("seed"));
    const text = canonicalJson(s);
    const back = JSON.parse(text) as JsonValue;
    return canonicalJson(back) === text ? null : "round-trip changed the state";
  }));

  out.push(check("seedState: deterministic under the same seed", () => {
    const a = hashState(domain.seedState(new Rng(seed, "a")));
    const b = hashState(domain.seedState(new Rng(seed, "b")));
    return a === b ? null : "same seed gave different seed states";
  }));

  out.push(check("seedState: invariants hold", () => {
    const v = checkInvariants(domain, domain.seedState(root.child("seed")));
    return v.length ? v.map((x) => `${x.id}: ${x.detail}`).join("; ") : null;
  }));

  const ctxFor = (r: Rng): OperationContext => ({ rng: r, now: () => 1_700_000_000_000 });
  const opNames = Object.keys(domain.operations).sort();
  let applied = 0;
  let rejected = 0;
  const problems: Record<string, string[]> = {
    "operations: legal operations keep every invariant": [],
    "operations: deterministic under the same child seed": [],
    "operations: diff/patch round-trips every transition": [],
    "operations: a rejected operation leaves state byte-identical": [],
    "operations: apply never mutates its input": [],
    "operations: sample() returns params the precondition accepts": [],
  };
  for (let s = 0; s < sequences; s++) {
    const seqRng = root.child(`seq:${s}`);
    let state = domain.seedState(seqRng.child("seed"));
    for (let i = 0; i < length; i++) {
      const name = opNames[seqRng.int(0, opNames.length)] as string;
      const op = domain.operations[name];
      if (!op) continue;
      const params = op.sample(state, seqRng.child(`sample:${i}`));
      if (params === null) continue;
      const pre = op.precondition(state, params);
      if (!pre.ok) {
        problems["operations: sample() returns params the precondition accepts"]?.push(`${name}: ${pre.reason}`);
        continue;
      }
      const before = hashState(state);
      const r1 = execute(domain, state, name, params, ctxFor(seqRng.child(`apply:${i}`)));
      const r2 = execute(domain, state, name, params, ctxFor(seqRng.child(`apply:${i}`)));
      if (hashState(state) !== before) problems["operations: apply never mutates its input"]?.push(name);
      if (!r1.ok) {
        rejected++;
        if (r1.violations) problems["operations: legal operations keep every invariant"]?.push(`${name}: ${r1.reason}`);
        continue;
      }
      applied++;
      if (!r2.ok || r2.trace.afterHash !== r1.trace.afterHash) problems["operations: deterministic under the same child seed"]?.push(name);
      const patched = patch(state, r1.trace.changes);
      if (hashState(patched) !== r1.trace.afterHash) problems["operations: diff/patch round-trips every transition"]?.push(name);
      state = r1.state;
    }
    // one deliberately rejected call per sequence: unknown operation must not touch state
    const h = hashState(state);
    const rej = execute(domain, state, "__no_such_operation__", {}, ctxFor(seqRng));
    if (rej.ok || hashState(state) !== h || !isEmpty(diff(state, rej.state as JsonValue)))
      problems["operations: a rejected operation leaves state byte-identical"]?.push(`seq ${s}`);
  }
  for (const [id, list] of Object.entries(problems)) {
    out.push({ id, ok: list.length === 0, detail: list.length ? Array.from(new Set(list)).slice(0, 5).join("; ") : `ok (${applied} applied, ${rejected} rejected)` });
  }
  out.push(check("operations: the sequences exercised at least one operation", () => (applied > 0 ? null : "no operation was ever applied; sample() always returned null?")));
  return out;
}
