/**
 * The plugin interface every domain implements. The core never inspects a domain's
 * vocabulary: it sees entities, operations, invariants and a seeded initial state.
 * eslint's no-domain-vocabulary rule keeps this package free of any domain's words.
 *
 * Rules a domain must follow (the conformance suite checks them):
 * - state is canonical JSON: integers only, collections keyed by id
 * - seedState draws only from the given Rng
 * - operations are pure, sampleable, and never touch the wall clock (ctx.now is injected)
 * - invariants hold on the seed state and after every legal operation
 */

import type { Invariant } from "./invariant.js";
import type { EntitySchema, OperationDefinition } from "./operation.js";
import type { Rng } from "./rng.js";
import type { JsonObject } from "./state.js";

export interface DomainDefinition<S extends JsonObject> {
  /** Stable identifier chosen by the domain, e.g. its package name. */
  readonly id: string;
  /** Semantic version of the domain's own contract. */
  readonly version: string;
  readonly entities: Record<string, EntitySchema>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- each operation has its own params type
  readonly operations: Record<string, OperationDefinition<S, any>>;
  readonly invariants: readonly Invariant<S>[];
  /** Deterministic initial state for a seed. Same Rng seed, same state. */
  seedState(rng: Rng): S;
}
