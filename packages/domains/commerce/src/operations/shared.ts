import type { Precondition, Rng } from "@rtl/core-semantic";
import type { CommerceState } from "../entities.js";

export const OK: Precondition = { ok: true };
export const no = (reason: string): Precondition => ({ ok: false, reason });

export function pad(n: number, width: number): string {
  return String(n).padStart(width, "0");
}

export function stockedVariantIds(state: CommerceState, min = 1): string[] {
  return Object.keys(state.variants).sort().filter((id) => state.inventory[id]!.available >= min && state.products[state.variants[id]!.productId]!.active);
}

export function cartLineIds(state: CommerceState): string[] {
  return Object.keys(state.cart.lines).sort();
}

export function pickOrNull<T>(rng: Rng, items: readonly T[]): T | null {
  return items.length ? rng.pick(items) : null;
}

export function cityEligible(state: CommerceState, shippingOptionId: string, addressId: string | null): boolean {
  const opt = state.shippingOptions[shippingOptionId];
  if (!opt) return false;
  if (opt.cities === null) return true;
  if (!addressId) return false;
  const addr = state.addresses[addressId];
  return !!addr && opt.cities.includes(addr.city);
}
