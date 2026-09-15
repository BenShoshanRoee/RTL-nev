import type { OperationDefinition } from "@rtl/core-semantic";
import type { CartLine, CommerceState } from "../entities.js";
import { OK, cartLineIds, no, pad, pickOrNull, stockedVariantIds } from "./shared.js";
import { withTotals } from "./totals.js";

function inCartFor(state: CommerceState, variantId: string, exceptLine?: string): number {
  return Object.values(state.cart.lines).filter((l) => l.variantId === variantId && l.id !== exceptLine).reduce((n, l) => n + l.quantity, 0);
}

function rebuildGroups(state: CommerceState): CommerceState {
  if (!state.cart.deliveryGroups) return state;
  const ids = new Set(Object.keys(state.cart.lines));
  const groups = Object.fromEntries(
    Object.entries(state.cart.deliveryGroups)
      .map(([k, g]) => [k, { ...g, lineIds: g.lineIds.filter((l) => ids.has(l)) }] as const)
      .filter(([, g]) => g.lineIds.length > 0),
  );
  const covered = new Set(Object.values(groups).flatMap((g) => g.lineIds));
  const orphan = [...ids].filter((l) => !covered.has(l));
  if (orphan.length === 0 && Object.keys(groups).length >= 2) return { ...state, cart: { ...state.cart, deliveryGroups: groups } };
  // a split that no longer partitions the cart collapses back to single delivery
  const first = Object.values(state.cart.deliveryGroups).sort((a, b) => (a.id < b.id ? -1 : 1))[0];
  return { ...state, cart: { ...state.cart, deliveryGroups: null, shippingOptionId: first?.shippingOptionId ?? state.cart.shippingOptionId, deliverySlotId: first?.deliverySlotId ?? null } };
}

export const addToCart: OperationDefinition<CommerceState, { variantId: string; quantity: number }> = {
  name: "addToCart",
  description: "add units of a variant; merges into an existing line for the same variant",
  params: { variantId: { kind: "ref", entity: "variant" }, quantity: "integer" },
  precondition: (s, p) => {
    const v = s.variants[p.variantId];
    if (!v || !s.products[v.productId]!.active) return no(`no active variant ${p.variantId}`);
    if (p.quantity < 1) return no("quantity must be at least 1");
    const want = inCartFor(s, p.variantId) + p.quantity;
    if (want > s.inventory[p.variantId]!.available) return no(`only ${s.inventory[p.variantId]!.available} available in stock`);
    return OK;
  },
  apply: (s, p) => {
    const existing = Object.values(s.cart.lines).find((l) => l.variantId === p.variantId);
    let lines: Record<string, CartLine>;
    let counters = s.counters;
    if (existing) {
      lines = { ...s.cart.lines, [existing.id]: { ...existing, quantity: existing.quantity + p.quantity } };
    } else {
      counters = { ...s.counters, line: s.counters.line + 1 };
      const id = `l${pad(counters.line, 5)}`;
      lines = { ...s.cart.lines, [id]: { id, variantId: p.variantId, quantity: p.quantity, unitPrice: s.variants[p.variantId]!.price } };
    }
    let next: CommerceState = { ...s, counters, cart: { ...s.cart, lines } };
    if (next.cart.deliveryGroups && !existing) {
      const groups = Object.values(next.cart.deliveryGroups).sort((a, b) => (a.id < b.id ? -1 : 1));
      const g = groups[0]!;
      next = { ...next, cart: { ...next.cart, deliveryGroups: { ...next.cart.deliveryGroups, [g.id]: { ...g, lineIds: [...g.lineIds, Object.keys(lines).sort().at(-1)!] } } } };
    }
    return withTotals(next);
  },
  sample: (s, rng) => {
    const ids = stockedVariantIds(s).filter((id) => s.inventory[id]!.available - inCartFor(s, id) >= 1);
    if (!ids.length) return null;
    const variantId = rng.pick(ids);
    const room = s.inventory[variantId]!.available - inCartFor(s, variantId);
    return { variantId, quantity: rng.int(1, Math.min(room, 3) + 1) };
  },
};

export const changeVariant: OperationDefinition<CommerceState, { lineId: string; variantId: string }> = {
  name: "changeVariant",
  description: "switch a cart line to a sibling variant of the same product (size or colour), keeping the quantity",
  params: { lineId: { kind: "ref", entity: "cartLine" }, variantId: { kind: "ref", entity: "variant" } },
  precondition: (s, p) => {
    const line = s.cart.lines[p.lineId];
    if (!line) return no(`no cart line ${p.lineId}`);
    const from = s.variants[line.variantId]!;
    const to = s.variants[p.variantId];
    if (!to) return no(`no variant ${p.variantId}`);
    if (to.productId !== from.productId) return no("variant belongs to a different product");
    if (to.id === from.id) return no("already that variant");
    if (Object.values(s.cart.lines).some((l) => l.id !== line.id && l.variantId === to.id)) return no("that variant is already a separate cart line");
    if (line.quantity > s.inventory[to.id]!.available) return no(`only ${s.inventory[to.id]!.available} available in stock`);
    return OK;
  },
  apply: (s, p) => {
    const line = s.cart.lines[p.lineId]!;
    return withTotals({ ...s, cart: { ...s.cart, lines: { ...s.cart.lines, [line.id]: { ...line, variantId: p.variantId, unitPrice: s.variants[p.variantId]!.price } } } });
  },
  sample: (s, rng) => {
    const options = cartLineIds(s).flatMap((lineId) => {
      const line = s.cart.lines[lineId]!;
      const product = s.products[s.variants[line.variantId]!.productId]!;
      return product.variantIds
        .filter((v) => v !== line.variantId && s.inventory[v]!.available >= line.quantity && !Object.values(s.cart.lines).some((l) => l.id !== lineId && l.variantId === v))
        .map((variantId) => ({ lineId, variantId }));
    });
    return pickOrNull(rng, options);
  },
};

export const setQuantity: OperationDefinition<CommerceState, { lineId: string; quantity: number }> = {
  name: "setQuantity",
  description: "set a cart line's quantity (at least 1; use removeLine to drop it)",
  params: { lineId: { kind: "ref", entity: "cartLine" }, quantity: "integer" },
  precondition: (s, p) => {
    const line = s.cart.lines[p.lineId];
    if (!line) return no(`no cart line ${p.lineId}`);
    if (p.quantity < 1) return no("quantity must be at least 1");
    if (p.quantity + inCartFor(s, line.variantId, line.id) > s.inventory[line.variantId]!.available) return no(`only ${s.inventory[line.variantId]!.available} available in stock`);
    return OK;
  },
  apply: (s, p) => withTotals({ ...s, cart: { ...s.cart, lines: { ...s.cart.lines, [p.lineId]: { ...s.cart.lines[p.lineId]!, quantity: p.quantity } } } }),
  sample: (s, rng) => {
    const ids = cartLineIds(s);
    if (!ids.length) return null;
    const lineId = rng.pick(ids);
    const line = s.cart.lines[lineId]!;
    const max = s.inventory[line.variantId]!.available - inCartFor(s, line.variantId, line.id);
    if (max < 1) return null;
    return { lineId, quantity: rng.int(1, Math.min(max, 5) + 1) };
  },
};

export const removeLine: OperationDefinition<CommerceState, { lineId: string }> = {
  name: "removeLine",
  description: "remove a cart line",
  params: { lineId: { kind: "ref", entity: "cartLine" } },
  precondition: (s, p) => (s.cart.lines[p.lineId] ? OK : no(`no cart line ${p.lineId}`)),
  apply: (s, p) => {
    const lines = { ...s.cart.lines };
    delete lines[p.lineId];
    return withTotals(rebuildGroups({ ...s, cart: { ...s.cart, lines } }));
  },
  sample: (s, rng) => pickOrNull(rng, cartLineIds(s).map((lineId) => ({ lineId }))),
};

export const saveForLater: OperationDefinition<CommerceState, { lineId: string }> = {
  name: "saveForLater",
  description: "move a cart line to the saved list",
  params: { lineId: { kind: "ref", entity: "cartLine" } },
  precondition: (s, p) => (s.cart.lines[p.lineId] ? OK : no(`no cart line ${p.lineId}`)),
  apply: (s, p) => {
    const line = s.cart.lines[p.lineId]!;
    const lines = { ...s.cart.lines };
    delete lines[p.lineId];
    const counters = { ...s.counters, saved: s.counters.saved + 1 };
    const id = `sv${pad(counters.saved, 4)}`;
    return withTotals(rebuildGroups({ ...s, counters, saved: { ...s.saved, [id]: { id, variantId: line.variantId, quantity: line.quantity } }, cart: { ...s.cart, lines } }));
  },
  sample: (s, rng) => pickOrNull(rng, cartLineIds(s).map((lineId) => ({ lineId }))),
};

export const moveToCart: OperationDefinition<CommerceState, { savedId: string }> = {
  name: "moveToCart",
  description: "move a saved item back into the cart",
  params: { savedId: { kind: "ref", entity: "savedItem" } },
  precondition: (s, p) => {
    const item = s.saved[p.savedId];
    if (!item) return no(`no saved item ${p.savedId}`);
    const v = s.variants[item.variantId]!;
    if (!s.products[v.productId]!.active) return no("product no longer available");
    if (item.quantity + inCartFor(s, item.variantId) > s.inventory[item.variantId]!.available) return no(`only ${s.inventory[item.variantId]!.available} available in stock`);
    return OK;
  },
  apply: (s, p) => {
    const item = s.saved[p.savedId]!;
    const saved = { ...s.saved };
    delete saved[p.savedId];
    const stripped = { ...s, saved };
    return addToCart.apply(stripped, { variantId: item.variantId, quantity: item.quantity }, undefined as never);
  },
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.saved).sort().filter((id) => moveToCart.precondition(s, { savedId: id }).ok).map((savedId) => ({ savedId }))),
};
