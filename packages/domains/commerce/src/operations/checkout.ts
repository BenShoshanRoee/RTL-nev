import { money, type OperationDefinition } from "@rtl/core-semantic";
import type { Address, CommerceState, DeliveryGroup, Order, OrderLine, Shipment } from "../entities.js";
import { OK, cartLineIds, cityEligible, no, pad, pickOrNull } from "./shared.js";
import { computeTotals, emptyTotals, withTotals } from "./totals.js";

export function couponUsable(s: CommerceState, code: string): string | null {
  const c = s.coupons[code];
  if (!c) return `unknown coupon ${code}`;
  if (!c.active) return "coupon is not active";
  if (c.expiresAt !== null && c.expiresAt <= s.session.now) return "coupon has expired";
  if (c.uses >= c.maxUses) return "coupon has no uses left";
  if (s.cart.totals.subtotal.minor < c.minSubtotal.minor) return "cart is below the coupon's minimum subtotal";
  if (c.category && !Object.values(s.cart.lines).some((l) => s.products[s.variants[l.variantId]!.productId]!.category === c.category)) return "no cart line is in the coupon's category";
  return null;
}

export const applyCoupon: OperationDefinition<CommerceState, { code: string }> = {
  name: "applyCoupon",
  description: "apply one coupon code to the cart; a second coupon is rejected",
  params: { code: "string" },
  precondition: (s, p) => {
    if (s.cart.couponCode) return no(s.cart.couponCode === p.code ? "coupon already applied" : "a coupon is already applied; remove it first");
    const why = couponUsable(s, p.code);
    return why ? no(why) : OK;
  },
  apply: (s, p) => withTotals({ ...s, cart: { ...s.cart, couponCode: p.code } }),
  sample: (s, rng) => (s.cart.couponCode ? null : pickOrNull(rng, Object.keys(s.coupons).sort().filter((c) => couponUsable(s, c) === null).map((code) => ({ code })))),
};

export const removeCoupon: OperationDefinition<CommerceState, Record<string, never>> = {
  name: "removeCoupon",
  description: "remove the applied coupon",
  params: {},
  precondition: (s) => (s.cart.couponCode ? OK : no("no coupon applied")),
  apply: (s) => withTotals({ ...s, cart: { ...s.cart, couponCode: null } }),
  sample: (s) => (s.cart.couponCode ? {} : null),
};

export const applyLoyaltyPoints: OperationDefinition<CommerceState, { points: number }> = {
  name: "applyLoyaltyPoints",
  description: "spend loyalty points on the cart (0 clears); deducted from the account at checkout",
  params: { points: "integer" },
  precondition: (s, p) => (p.points < 0 ? no("points must not be negative") : p.points > s.customer.loyaltyPoints ? no(`only ${s.customer.loyaltyPoints} points available`) : OK),
  apply: (s, p) => withTotals({ ...s, cart: { ...s.cart, loyaltyPointsApplied: p.points } }),
  sample: (s, rng) => (s.customer.loyaltyPoints > 0 && cartLineIds(s).length ? { points: rng.int(0, Math.min(s.customer.loyaltyPoints, 100) + 1) } : null),
};

const ADDRESS_FIELDS = { recipient: "string", street: "string", houseNumber: "string", apartment: "string", city: "string", postalCode: "string", notes: "string" } as const;
type AddressFields = Omit<Address, "id">;

function validAddress(p: AddressFields): string | null {
  if (!p.recipient) return "recipient is required";
  if (!p.street || !p.houseNumber) return "street and house number are required";
  if (!p.city) return "city is required";
  if (!/^\d{5,7}$/.test(p.postalCode)) return "postal code must be 5 to 7 digits";
  return null;
}

export const addAddress: OperationDefinition<CommerceState, AddressFields> = {
  name: "addAddress",
  description: "add a delivery address to the account",
  params: ADDRESS_FIELDS,
  precondition: (s, p) => { const why = validAddress(p); return why ? no(why) : OK; },
  apply: (s, p) => {
    const counters = { ...s.counters, address: s.counters.address + 1 };
    const id = `a${pad(counters.address, 3)}`;
    return { ...s, counters, addresses: { ...s.addresses, [id]: { id, ...p } } };
  },
  sample: (s, rng) => {
    const tmpl = s.addresses[s.customer.defaultAddressId]!;
    return { recipient: tmpl.recipient, street: `street.${rng.int(1, 9)}`, houseNumber: String(rng.int(1, 200)), apartment: rng.bool() ? String(rng.int(1, 50)) : "", city: rng.pick(["city.tel_aviv", "city.haifa", "city.jerusalem", "city.eilat"]), postalCode: String(rng.int(1_000_000, 9_999_999)), notes: "" };
  },
};

export const editAddress: OperationDefinition<CommerceState, AddressFields & { addressId: string }> = {
  name: "editAddress",
  description: "replace an address's fields; the cart keeps pointing at it",
  params: { addressId: { kind: "ref", entity: "address" }, ...ADDRESS_FIELDS },
  precondition: (s, p) => {
    if (!s.addresses[p.addressId]) return no(`no address ${p.addressId}`);
    const why = validAddress(p);
    if (why) return no(why);
    if (s.cart.addressId === p.addressId) {
      const ids = s.cart.deliveryGroups ? Object.values(s.cart.deliveryGroups).map((g) => g.shippingOptionId) : s.cart.shippingOptionId ? [s.cart.shippingOptionId] : [];
      for (const o of ids) { const opt = s.shippingOptions[o]!; if (opt.cities && !opt.cities.includes(p.city)) return no(`shipping option ${o} does not serve ${p.city}; change shipping first`); }
    }
    return OK;
  },
  apply: (s, p) => {
    const { addressId, ...fields } = p;
    return { ...s, addresses: { ...s.addresses, [addressId]: { id: addressId, ...fields } } };
  },
  sample: (s, rng) => {
    const ids = Object.keys(s.addresses).sort();
    const addressId = rng.pick(ids);
    const a = s.addresses[addressId]!;
    const p = { addressId, ...a, houseNumber: String(rng.int(1, 200)), apartment: rng.bool() ? String(rng.int(1, 50)) : "" };
    delete (p as { id?: string }).id;
    return editAddress.precondition(s, p).ok ? p : null;
  },
};

export const setAddress: OperationDefinition<CommerceState, { addressId: string }> = {
  name: "setAddress",
  description: "choose the delivery address for the cart",
  params: { addressId: { kind: "ref", entity: "address" } },
  precondition: (s, p) => {
    if (!s.addresses[p.addressId]) return no(`no address ${p.addressId}`);
    const opts = s.cart.deliveryGroups ? Object.values(s.cart.deliveryGroups).map((g) => g.shippingOptionId) : s.cart.shippingOptionId ? [s.cart.shippingOptionId] : [];
    for (const o of opts) if (!cityEligible(s, o, p.addressId)) return no(`shipping option ${o} does not serve that city; change shipping first`);
    return OK;
  },
  apply: (s, p) => ({ ...s, cart: { ...s.cart, addressId: p.addressId } }),
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.addresses).sort().filter((id) => setAddress.precondition(s, { addressId: id }).ok).map((addressId) => ({ addressId }))),
};

export const setShipping: OperationDefinition<CommerceState, { shippingOptionId: string }> = {
  name: "setShipping",
  description: "choose one shipping option for the whole cart (clears any split); slot-based options need selectDeliverySlot",
  params: { shippingOptionId: { kind: "ref", entity: "shippingOption" } },
  precondition: (s, p) => {
    if (!s.shippingOptions[p.shippingOptionId]) return no(`no shipping option ${p.shippingOptionId}`);
    if (!s.cart.addressId) return no("choose an address before shipping");
    if (!cityEligible(s, p.shippingOptionId, s.cart.addressId)) return no("shipping option does not serve the chosen city");
    return OK;
  },
  apply: (s, p) => withTotals({ ...s, cart: { ...s.cart, shippingOptionId: p.shippingOptionId, deliverySlotId: null, deliveryGroups: null } }),
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.shippingOptions).sort().filter((id) => setShipping.precondition(s, { shippingOptionId: id }).ok).map((shippingOptionId) => ({ shippingOptionId }))),
};

export const selectDeliverySlot: OperationDefinition<CommerceState, { slotId: string }> = {
  name: "selectDeliverySlot",
  description: "book a delivery window for a slot-based shipping option",
  params: { slotId: { kind: "ref", entity: "deliverySlot" } },
  precondition: (s, p) => {
    const slot = s.deliverySlots[p.slotId];
    if (!slot) return no(`no delivery slot ${p.slotId}`);
    if (s.cart.deliveryGroups) return no("select slots per group through splitDelivery");
    if (slot.shippingOptionId !== s.cart.shippingOptionId) return no("slot belongs to a different shipping option");
    if (slot.booked >= slot.capacity) return no("slot is full");
    return OK;
  },
  apply: (s, p) => ({ ...s, cart: { ...s.cart, deliverySlotId: p.slotId } }),
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.deliverySlots).sort().filter((id) => selectDeliverySlot.precondition(s, { slotId: id }).ok).map((slotId) => ({ slotId }))),
};

type GroupInput = { lineIds: string[]; shippingOptionId: string; deliverySlotId?: string };

export const splitDelivery: OperationDefinition<CommerceState, { groups: GroupInput[] }> = {
  name: "splitDelivery",
  description: "deliver the cart in two or more groups, each with its own shipping option; groups must partition the cart exactly",
  params: { groups: { kind: "list", of: { kind: "record", entity: "deliveryGroup" } } },
  precondition: (s, p) => {
    if (!s.cart.addressId) return no("choose an address before splitting delivery");
    if (!Array.isArray(p.groups) || p.groups.length < 2) return no("a split needs at least two groups that partition the cart");
    const seen = new Set<string>();
    for (const g of p.groups) {
      if (!Array.isArray(g.lineIds) || g.lineIds.length === 0) return no("every group needs at least one line");
      for (const l of g.lineIds) {
        if (!s.cart.lines[l]) return no(`no cart line ${l}`);
        if (seen.has(l)) return no(`line ${l} appears twice; groups must partition the cart`);
        seen.add(l);
      }
      if (!cityEligible(s, g.shippingOptionId, s.cart.addressId)) return no(`shipping option ${g.shippingOptionId} unavailable for that city`);
      const opt = s.shippingOptions[g.shippingOptionId]!;
      if (opt.requiresSlot) {
        const slot = g.deliverySlotId ? s.deliverySlots[g.deliverySlotId] : undefined;
        if (!slot || slot.shippingOptionId !== opt.id || slot.booked >= slot.capacity) return no(`shipping option ${opt.id} needs an available delivery slot`);
      }
    }
    if (seen.size !== Object.keys(s.cart.lines).length) return no("groups must cover every line in the cart; groups must partition the cart");
    return OK;
  },
  apply: (s, p) => {
    let counters = s.counters;
    const groups: Record<string, DeliveryGroup> = {};
    for (const g of p.groups) {
      counters = { ...counters, group: counters.group + 1 };
      const id = `g${pad(counters.group, 4)}`;
      groups[id] = { id, lineIds: [...g.lineIds].sort(), shippingOptionId: g.shippingOptionId, deliverySlotId: g.deliverySlotId ?? null };
    }
    return withTotals({ ...s, counters, cart: { ...s.cart, deliveryGroups: groups, shippingOptionId: null, deliverySlotId: null } });
  },
  sample: (s, rng) => {
    const ids = cartLineIds(s);
    if (ids.length < 2 || !s.cart.addressId) return null;
    const opts = Object.keys(s.shippingOptions).sort().filter((o) => !s.shippingOptions[o]!.requiresSlot && cityEligible(s, o, s.cart.addressId));
    if (opts.length < 2) return null;
    const shuffled = rng.shuffle(ids);
    const cut = rng.int(1, shuffled.length);
    const [o1, o2] = rng.shuffle(opts);
    return { groups: [{ lineIds: shuffled.slice(0, cut), shippingOptionId: o1! }, { lineIds: shuffled.slice(cut), shippingOptionId: o2! }] };
  },
};

export const setPaymentMethod: OperationDefinition<CommerceState, { paymentMethodId: string }> = {
  name: "setPaymentMethod",
  description: "choose a payment method; expired cards are rejected",
  params: { paymentMethodId: { kind: "ref", entity: "paymentMethod" } },
  precondition: (s, p) => {
    const pm = s.paymentMethods[p.paymentMethodId];
    if (!pm) return no(`no payment method ${p.paymentMethodId}`);
    if (pm.expired) return no("payment method has expired");
    return OK;
  },
  apply: (s, p) => ({ ...s, cart: { ...s.cart, paymentMethodId: p.paymentMethodId } }),
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.paymentMethods).sort().filter((id) => !s.paymentMethods[id]!.expired).map((paymentMethodId) => ({ paymentMethodId }))),
};

export function checkoutBlocker(s: CommerceState): string | null {
  if (Object.keys(s.cart.lines).length === 0) return "cart is empty";
  if (!s.cart.addressId) return "choose a delivery address";
  if (!s.cart.deliveryGroups && !s.cart.shippingOptionId) return "choose a shipping option";
  if (!s.cart.deliveryGroups) {
    const opt = s.shippingOptions[s.cart.shippingOptionId!]!;
    if (!cityEligible(s, opt.id, s.cart.addressId)) return "shipping option does not serve the chosen city";
    if (opt.requiresSlot) {
      const slot = s.cart.deliverySlotId ? s.deliverySlots[s.cart.deliverySlotId] : undefined;
      if (!slot) return "choose a delivery slot";
      if (slot.booked >= slot.capacity) return "the chosen delivery slot is full";
    }
  } else {
    for (const g of Object.values(s.cart.deliveryGroups)) {
      const opt = s.shippingOptions[g.shippingOptionId]!;
      if (opt.requiresSlot) {
        const slot = g.deliverySlotId ? s.deliverySlots[g.deliverySlotId] : undefined;
        if (!slot || slot.booked >= slot.capacity) return `group ${g.id} needs an available delivery slot`;
      }
    }
  }
  if (!s.cart.paymentMethodId) return "choose a payment method";
  if (s.paymentMethods[s.cart.paymentMethodId]!.expired) return "payment method has expired";
  for (const l of Object.values(s.cart.lines)) if (l.quantity > s.inventory[l.variantId]!.available) return `not enough stock for line ${l.id}`;
  if (s.cart.couponCode) { const why = couponUsable(s, s.cart.couponCode); if (why) return why; }
  if (s.cart.loyaltyPointsApplied > s.customer.loyaltyPoints) return "not enough loyalty points";
  return null;
}

export const checkout: OperationDefinition<CommerceState, Record<string, never>> = {
  name: "checkout",
  description: "place the order: reserves stock, consumes the coupon use, spends loyalty points, books slots, empties the cart",
  params: {},
  precondition: (s) => { const why = checkoutBlocker(s); return why ? no(why) : OK; },
  apply: (s) => {
    const now = s.session.now;
    let counters = { ...s.counters, order: s.counters.order + 1 };
    const orderId = `o${pad(counters.order, 4)}`;
    const groups: Array<{ lineIds: string[]; shippingOptionId: string; deliverySlotId: string | null }> = s.cart.deliveryGroups
      ? Object.values(s.cart.deliveryGroups).sort((a, b) => (a.id < b.id ? -1 : 1))
      : [{ lineIds: Object.keys(s.cart.lines).sort(), shippingOptionId: s.cart.shippingOptionId!, deliverySlotId: s.cart.deliverySlotId }];
    const lines: Record<string, OrderLine> = {};
    const shipments: Record<string, Shipment> = {};
    const inventory = { ...s.inventory };
    const deliverySlots = { ...s.deliverySlots };
    for (const g of groups) {
      counters = { ...counters, shipment: counters.shipment + 1 };
      const shipmentId = `sh${pad(counters.shipment, 4)}`;
      shipments[shipmentId] = { id: shipmentId, lineIds: [...g.lineIds].sort(), shippingOptionId: g.shippingOptionId, deliverySlotId: g.deliverySlotId, status: "pending", dispatchedAt: null, deliveredAt: null, cancelledAtDispatch: null };
      if (g.deliverySlotId) deliverySlots[g.deliverySlotId] = { ...deliverySlots[g.deliverySlotId]!, booked: deliverySlots[g.deliverySlotId]!.booked + 1 };
      for (const lineId of g.lineIds) {
        const cl = s.cart.lines[lineId]!;
        lines[lineId] = { id: lineId, variantId: cl.variantId, quantity: cl.quantity, unitPrice: cl.unitPrice, cancelled: 0, returned: 0, shipmentId };
        const inv = inventory[cl.variantId]!;
        inventory[cl.variantId] = { ...inv, available: inv.available - cl.quantity, reserved: inv.reserved + cl.quantity };
      }
    }
    const totals = computeTotals(s, s.cart);
    const coupons = s.cart.couponCode ? { ...s.coupons, [s.cart.couponCode]: { ...s.coupons[s.cart.couponCode]!, uses: s.coupons[s.cart.couponCode]!.uses + 1 } } : s.coupons;
    const order: Order = {
      id: orderId, number: counters.order, customerId: s.customer.id, lines, shipments, address: s.addresses[s.cart.addressId!]!,
      paymentMethodId: s.cart.paymentMethodId!, couponCode: s.cart.couponCode, loyaltyPointsUsed: s.cart.loyaltyPointsApplied,
      totals, refunded: money(0, s.config.currency), status: "pending", placedAt: now, events: [{ kind: "placed", at: now, ref: orderId }],
    };
    return {
      ...s, counters, inventory, deliverySlots, coupons,
      customer: { ...s.customer, loyaltyPoints: s.customer.loyaltyPoints - s.cart.loyaltyPointsApplied },
      orders: { ...s.orders, [orderId]: order },
      cart: { lines: {}, couponCode: null, loyaltyPointsApplied: 0, addressId: s.cart.addressId, shippingOptionId: null, deliverySlotId: null, deliveryGroups: null, paymentMethodId: s.cart.paymentMethodId, totals: emptyTotals(s.config.currency) },
      session: { ...s.session, lastTrackedOrderId: orderId },
    };
  },
  sample: (s) => (checkoutBlocker(s) === null ? {} : null),
};
