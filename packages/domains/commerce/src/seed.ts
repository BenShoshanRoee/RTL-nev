/**
 * Deterministic initial state. Every draw comes from the given Rng (named children per
 * section), ids are sequential, and nothing here is language: names, sizes, colours and
 * cities are resource keys.
 */

import { money, type CurrencyCode, type Rng, exponent } from "@rtl/core-semantic";
import {
  CATEGORIES, CITIES, COLOURS, SIZE_KEYS,
  type Address, type CommerceState, type Coupon, type DeliverySlot, type Order, type Product,
  type ShippingOption, type SizeSystem, type Variant,
} from "./entities.js";
import { computeTotals, emptyTotals } from "./operations/totals.js";
import { deriveOrderStatus } from "./operations/orders.js";

export interface SeedOptions {
  currency?: CurrencyCode;
  products?: number;
}

const DAY = 86_400_000;
/** A fixed epoch for the session clock: 2026-01-05T09:00:00Z. Advanced only by advanceClock. */
export const SEED_NOW = 1_767_603_600_000;

/** Psychological price points in the currency's minor units (e.g. 49.90 -> 4990 agorot). */
function pricePoint(rng: Rng, currency: CurrencyCode, category: string): number {
  const unit = 10 ** exponent(currency);
  const bands: Record<string, [number, number]> = {
    "cat.apparel": [39, 349], "cat.shoes": [149, 699], "cat.home": [19, 899],
    "cat.electronics": [89, 3999], "cat.grocery": [4, 89],
  };
  const [lo, hi] = bands[category] ?? [10, 500];
  const major = rng.int(lo, hi + 1);
  const ending = rng.pick([0, 0, 9, 9, 9, 5]);
  const tenths = ending === 0 ? 0 : unit === 1 ? 0 : (ending * unit) / 10;
  return major * unit + Math.trunc(tenths);
}

export function seedCommerce(rng: Rng, opts: SeedOptions = {}): CommerceState {
  const currency = opts.currency ?? "ILS";
  const r = rng.child(`commerce:${currency}`);
  const productCount = opts.products ?? r.child("count").int(40, 61);

  const products: Record<string, Product> = {};
  const variants: Record<string, Variant> = {};
  const inventory: CommerceState["inventory"] = {};
  const cat = r.child("catalog");
  let variantSeq = 0;
  for (let i = 1; i <= productCount; i++) {
    const id = `p${String(i).padStart(3, "0")}`;
    const category = cat.pick(CATEGORIES);
    const sizeSystem: SizeSystem =
      category === "cat.shoes" ? "numeric"
      : category === "cat.apparel" ? cat.pick(["letters", "words", "numeric"] as const)
      : "none";
    const sizes = sizeSystem === "none" ? [null] : cat.shuffle(SIZE_KEYS[sizeSystem]).slice(0, cat.int(1, 5));
    const colours = cat.bool(0.6) ? cat.shuffle(COLOURS).slice(0, cat.int(1, 3)) : [null];
    const base = pricePoint(cat, currency, category);
    const variantIds: string[] = [];
    for (const size of sizes) {
      for (const colour of colours) {
        const vid = `v${String(++variantSeq).padStart(4, "0")}`;
        variantIds.push(vid);
        const bump = cat.bool(0.2) ? cat.int(1, 4) * 10 ** exponent(currency) : 0;
        variants[vid] = { id: vid, productId: id, sizeKey: size, colourKey: colour, price: money(base + bump, currency), weightGrams: cat.int(50, 5000) };
        const roll = cat.float();
        inventory[vid] = { variantId: vid, available: roll < 0.12 ? 0 : roll < 0.25 ? 1 : cat.int(2, 31), reserved: 0 };
      }
    }
    const tagPool = ["tag.sale", "tag.new", "tag.bestseller", "tag.eco", "tag.kids", "tag.gift", `tag.${category.slice(4)}`];
    products[id] = { id, nameKey: `product.${id}`, category, sizeSystem, variantIds, tags: cat.shuffle(tagPool).slice(0, cat.int(1, 4)).sort(), active: cat.bool(0.95) };
  }

  const a = r.child("account");
  const homeCity = a.pick(CITIES);
  const addresses: Record<string, Address> = {
    a001: { id: "a001", recipient: "customer.name", street: "street.1", houseNumber: String(a.int(1, 120)), apartment: String(a.int(1, 40)), city: homeCity, postalCode: String(a.int(1_000_000, 9_999_999)), notes: "" },
    a002: { id: "a002", recipient: "customer.name", street: "street.2", houseNumber: String(a.int(1, 120)), apartment: "", city: a.pick(CITIES.filter((c) => c !== homeCity)), postalCode: String(a.int(1_000_000, 9_999_999)), notes: "address.note.leave_at_door" },
  };
  const paymentMethods: CommerceState["paymentMethods"] = {
    pm01: { id: "pm01", kind: "card", last4: String(a.int(1000, 9999)), expired: false },
    pm02: { id: "pm02", kind: "card", last4: String(a.int(1000, 9999)), expired: true },
    pm03: { id: "pm03", kind: "wallet", last4: "", expired: false },
  };

  const sh = r.child("shipping");
  const unit = 10 ** exponent(currency);
  const shippingOptions: Record<string, ShippingOption> = {
    ship_pickup: { id: "ship_pickup", nameKey: "shipping.pickup_point", price: money(0, currency), etaDaysMin: 2, etaDaysMax: 5, requiresSlot: false, cities: null },
    ship_courier: { id: "ship_courier", nameKey: "shipping.courier", price: money(sh.int(15, 35) * unit, currency), etaDaysMin: 1, etaDaysMax: 3, requiresSlot: false, cities: null },
    ship_express: { id: "ship_express", nameKey: "shipping.express", price: money(sh.int(40, 70) * unit, currency), etaDaysMin: 0, etaDaysMax: 1, requiresSlot: false, cities: ["city.tel_aviv", "city.rishon", "city.netanya"] },
    ship_slot: { id: "ship_slot", nameKey: "shipping.scheduled", price: money(sh.int(25, 45) * unit, currency), etaDaysMin: 1, etaDaysMax: 4, requiresSlot: true, cities: null },
  };
  const deliverySlots: Record<string, DeliverySlot> = {};
  for (let d = 1; d <= 4; d++) {
    for (const [w, key] of [["m", "slot.window.morning"], ["a", "slot.window.afternoon"], ["e", "slot.window.evening"]] as const) {
      const id = `slot_d${d}${w}`;
      const capacity = sh.int(1, 4);
      deliverySlots[id] = { id, shippingOptionId: "ship_slot", day: d, windowKey: key, capacity, booked: sh.int(0, capacity) };
    }
  }

  const cp = r.child("coupons");
  const coupons: Record<string, Coupon> = {};
  const mk = (code: string, c: Omit<Coupon, "code" | "uses">) => { coupons[code] = { code, uses: 0, ...c }; };
  mk("WELCOME10", { kind: "percent", value: 10, minSubtotal: money(0, currency), category: "", expiresAt: null, maxUses: 100, active: true });
  mk("SAVE20", { kind: "percent", value: 20, minSubtotal: money(cp.int(150, 300) * unit, currency), category: "", expiresAt: null, maxUses: 100, active: true });
  mk("FIXED30", { kind: "fixed", value: 30 * unit, minSubtotal: money(0, currency), category: "", expiresAt: null, maxUses: 100, active: true });
  mk("FREESHIP", { kind: "free_shipping", value: 0, minSubtotal: money(cp.int(100, 200) * unit, currency), category: "", expiresAt: null, maxUses: 100, active: true });
  mk("OLD2025", { kind: "percent", value: 15, minSubtotal: money(0, currency), category: "", expiresAt: SEED_NOW - 30 * DAY, maxUses: 100, active: true });
  mk("SHOES5", { kind: "percent", value: 5, minSubtotal: money(0, currency), category: "cat.shoes", expiresAt: SEED_NOW + 20 * DAY, maxUses: 100, active: true });
  mk("ONESHOT", { kind: "fixed", value: 10 * unit, minSubtotal: money(0, currency), category: "", expiresAt: null, maxUses: 1, active: cp.bool(0.5) });

  const base: CommerceState = {
    config: { currency, vatPercent: 18, returnWindowDays: 14, loyaltyPointValueMinor: unit },
    counters: { order: 0, line: 0, shipment: 0, return: 0, address: 2, group: 0, saved: 0 },
    products, variants, inventory, coupons, shippingOptions, deliverySlots,
    customer: { id: "c001", nameKey: "customer.name", phone: `05${a.int(10_000_000, 99_999_999)}`, email: "customer@example.test", defaultAddressId: "a001", defaultPaymentMethodId: "pm01", loyaltyPoints: a.int(0, 400) },
    addresses, paymentMethods,
    cart: { lines: {}, couponCode: null, loyaltyPointsApplied: 0, addressId: null, shippingOptionId: null, deliverySlotId: null, deliveryGroups: null, paymentMethodId: null, totals: emptyTotals(currency) },
    saved: {},
    orders: {},
    returns: {},
    session: { now: SEED_NOW, lastSearch: null, recentlyViewed: [], lastTrackedOrderId: null },
  };

  // Two existing orders: one delivered (returnable) and one pending (cancellable).
  const oh = r.child("history");
  const stocked = Object.keys(variants).sort().filter((v) => inventory[v]!.available >= 2 && products[variants[v]!.productId]!.active);
  const past: Array<{ status: "delivered" | "pending"; daysAgo: number }> = [{ status: "delivered", daysAgo: 6 }, { status: "pending", daysAgo: 1 }];
  let state = base;
  for (const p of past) {
    const picks = oh.shuffle(stocked).slice(0, 2);
    const lines: Order["lines"] = {};
    const shipmentId = `sh${String(++state.counters.shipment).padStart(4, "0")}`;
    for (const vid of picks) {
      const lineId = `l${String(++state.counters.line).padStart(5, "0")}`;
      const quantity = oh.int(1, 3);
      lines[lineId] = { id: lineId, variantId: vid, quantity, unitPrice: variants[vid]!.price, cancelled: 0, returned: 0, shipmentId };
      inventory[vid] = { ...inventory[vid]!, available: Math.max(0, inventory[vid]!.available - quantity), reserved: inventory[vid]!.reserved + (p.status === "pending" ? quantity : 0) };
    }
    const placedAt = SEED_NOW - p.daysAgo * DAY;
    const number = ++state.counters.order;
    const orderId = `o${String(number).padStart(4, "0")}`;
    const cartLike = { lines: Object.fromEntries(Object.values(lines).map((l) => [l.id, { id: l.id, variantId: l.variantId, quantity: l.quantity, unitPrice: l.unitPrice }])), couponCode: null, loyaltyPointsApplied: 0, deliveryGroups: null, shippingOptionId: "ship_courier" };
    const totals = computeTotals(state, cartLike);
    const shipment: Order["shipments"][string] = {
      id: shipmentId, lineIds: Object.keys(lines).sort(), shippingOptionId: "ship_courier", deliverySlotId: null,
      status: p.status === "delivered" ? "delivered" : "pending",
      dispatchedAt: p.status === "delivered" ? placedAt + DAY : null,
      deliveredAt: p.status === "delivered" ? placedAt + 2 * DAY : null,
      cancelledAtDispatch: p.status === "delivered" ? Object.fromEntries(Object.keys(lines).map((k) => [k, 0])) : null,
    };
    const events: Order["events"] = [{ kind: "placed", at: placedAt, ref: orderId }];
    if (p.status === "delivered") events.push({ kind: "dispatched", at: placedAt + DAY, ref: shipmentId }, { kind: "delivered", at: placedAt + 2 * DAY, ref: shipmentId });
    const order: Order = {
      id: orderId, number, customerId: "c001", lines, shipments: { [shipmentId]: shipment }, address: addresses["a001"]!,
      paymentMethodId: "pm01", couponCode: null, loyaltyPointsUsed: 0, totals, refunded: money(0, currency), status: "pending", placedAt, events,
    };
    order.status = deriveOrderStatus(order);
    state = { ...state, orders: { ...state.orders, [orderId]: order }, inventory: { ...inventory } };
  }
  return state;
}
