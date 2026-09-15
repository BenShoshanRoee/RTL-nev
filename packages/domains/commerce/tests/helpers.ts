import { execute, Rng, type CurrencyCode, type JsonObject } from "@rtl/core-semantic";
import { commerceDomain, seedCommerce, type CommerceState } from "../src/index.js";

export const ctx = { rng: new Rng(99, "test"), now: () => 0 };

export function seeded(seed = 42, currency: CurrencyCode = "ILS"): CommerceState {
  return seedCommerce(new Rng(seed, "seed"), { currency });
}

/** Apply an operation that must succeed; returns the new state. */
export function ok(state: CommerceState, op: string, params: JsonObject = {}): CommerceState {
  const r = execute(commerceDomain, state, op, params, ctx);
  if (!r.ok) throw new Error(`${op} rejected: ${r.reason}`);
  return r.state;
}

/** Apply an operation that must be rejected; returns the reason. */
export function rejected(state: CommerceState, op: string, params: JsonObject = {}): string {
  const r = execute(commerceDomain, state, op, params, ctx);
  if (r.ok) throw new Error(`${op} unexpectedly succeeded`);
  return r.reason;
}

/** First variant with at least `min` units available, preferring products with several variants. */
export function stockedVariant(state: CommerceState, min = 3, exclude: string[] = []): string {
  const ids = Object.keys(state.variants).sort();
  for (const id of ids) {
    const v = state.variants[id]!;
    const p = state.products[v.productId]!;
    if (exclude.includes(id) || !p.active) continue;
    if (state.inventory[id]!.available >= min && p.variantIds.length > 1) return id;
  }
  throw new Error("no stocked multi-variant product in seed");
}
