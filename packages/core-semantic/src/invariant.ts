/** Predicates that must hold after every operation. A violation rejects the operation. */

import type { JsonObject } from "./state";

export type InvariantResult = { ok: true } | { ok: false; detail: string };

export interface Invariant<S extends JsonObject> {
  readonly id: string;
  readonly description: string;
  check(state: Readonly<S>): InvariantResult;
}

export interface InvariantViolation {
  id: string;
  detail: string;
}

export function checkInvariants<S extends JsonObject>(
  domain: { invariants: readonly Invariant<S>[] },
  state: Readonly<S>,
): InvariantViolation[] {
  const out: InvariantViolation[] = [];
  for (const inv of domain.invariants) {
    const r = inv.check(state);
    if (!r.ok) out.push({ id: inv.id, detail: r.detail });
  }
  return out;
}
