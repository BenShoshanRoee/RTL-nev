/**
 * What must hold after every operation. A violation rejects the operation with the untouched
 * input state, so no reachable state ever breaks these.
 */

import { equals, money, scale, type Invariant, type Money } from "@rtl/core-semantic";
import type { CommerceState } from "./entities.js";
import { computeTotals, paidShare } from "./operations/totals.js";
import { deriveOrderStatus } from "./operations/orders.js";

type Inv = Invariant<CommerceState>;
const ok = { ok: true } as const;
const bad = (detail: string) => ({ ok: false as const, detail });

function every<T>(items: Iterable<T>, test: (item: T) => string | null): string | null {
  for (const item of items) { const d = test(item); if (d) return d; }
  return null;
}
const wrap = (d: string | null) => (d ? bad(d) : ok);

function moneyValues(value: unknown, path: string, out: Array<[string, Money]>): void {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const o = value as Record<string, unknown>;
    if (typeof o["minor"] === "number" && typeof o["currency"] === "string" && Object.keys(o).length === 2) { out.push([path, o as unknown as Money]); return; }
    for (const [k, v] of Object.entries(o)) moneyValues(v, `${path}.${k}`, out);
  } else if (Array.isArray(value)) value.forEach((v, i) => moneyValues(v, `${path}[${i}]`, out));
}

export const invariants: readonly Inv[] = [
  {
    id: "cart-totals-consistent",
    description: "subtotal = sum of lines; discount and loyalty capped; total = subtotal - discount - loyalty + shipping; vat = total * r/(100+r)",
    check: (s) => {
      const t = computeTotals(s, s.cart);
      const c = s.cart.totals;
      for (const k of ["subtotal", "discount", "loyalty", "shipping", "vat", "total"] as const) if (!equals(t[k], c[k])) return bad(`cart.totals.${k} is ${c[k].minor}, expected ${t[k].minor}`);
      return ok;
    },
  },
  {
    id: "inventory-never-negative",
    description: "available and reserved are non-negative integers for every variant",
    check: (s) => wrap(every(Object.values(s.inventory), (i) => (i.available < 0 || i.reserved < 0 || !Number.isSafeInteger(i.available) || !Number.isSafeInteger(i.reserved) ? `inventory ${i.variantId}: available ${i.available} reserved ${i.reserved}` : null))),
  },
  {
    id: "reserved-matches-pending-orders",
    description: "reserved stock equals the un-cancelled quantity of every pending (not yet dispatched) order line",
    check: (s) => {
      const expected: Record<string, number> = {};
      for (const o of Object.values(s.orders)) for (const l of Object.values(o.lines)) if (o.shipments[l.shipmentId]!.status === "pending") expected[l.variantId] = (expected[l.variantId] ?? 0) + (l.quantity - l.cancelled);
      return wrap(every(Object.values(s.inventory), (i) => (i.reserved !== (expected[i.variantId] ?? 0) ? `inventory ${i.variantId}: reserved ${i.reserved}, pending order lines need ${expected[i.variantId] ?? 0}` : null)));
    },
  },
  {
    id: "coupon-applies-once",
    description: "at most one coupon per cart, uses within maxUses, and uses equal the orders that consumed it",
    check: (s) => {
      if (s.cart.couponCode !== null && !s.coupons[s.cart.couponCode]) return bad(`cart coupon ${s.cart.couponCode} does not exist`);
      const used: Record<string, number> = {};
      for (const o of Object.values(s.orders)) if (o.couponCode) used[o.couponCode] = (used[o.couponCode] ?? 0) + 1;
      return wrap(every(Object.values(s.coupons), (c) => (c.uses > c.maxUses ? `coupon ${c.code} used ${c.uses} > max ${c.maxUses}` : c.uses !== (used[c.code] ?? 0) ? `coupon ${c.code} uses ${c.uses} but ${used[c.code] ?? 0} orders carry it` : null)));
    },
  },
  {
    id: "no-cancellation-after-dispatch",
    description: "for a dispatched or delivered shipment, every line's cancelled quantity equals the value frozen at dispatch",
    check: (s) => wrap(every(Object.values(s.orders), (o) => every(Object.values(o.shipments), (sh) => {
      if (sh.status === "pending") return sh.cancelledAtDispatch === null ? null : `${o.id}/${sh.id}: pending shipment has a dispatch snapshot`;
      if (!sh.cancelledAtDispatch || sh.dispatchedAt === null) return `${o.id}/${sh.id}: ${sh.status} without dispatch record`;
      return every(sh.lineIds, (l) => (o.lines[l]!.cancelled !== sh.cancelledAtDispatch![l] ? `${o.id}/${l}: cancelled ${o.lines[l]!.cancelled} after dispatch (frozen at ${sh.cancelledAtDispatch![l]})` : null));
    }))),
  },
  {
    id: "vat-consistent",
    description: "vat is the VAT contained in the total at the configured rate, for the cart and every order",
    check: (s) => {
      const r = s.config.vatPercent;
      const check = (label: string, t: { total: Money; vat: Money }) => (equals(t.vat, scale(t.total, r, 100 + r, "half-up")) ? null : `${label}: vat ${t.vat.minor} for total ${t.total.minor} at ${r}%`);
      return wrap(check("cart", s.cart.totals) ?? every(Object.values(s.orders), (o) => check(o.id, o.totals)));
    },
  },
  {
    id: "referential-integrity",
    description: "every id a record points at exists",
    check: (s) => wrap(
      every(Object.values(s.variants), (v) => (s.products[v.productId] ? (s.inventory[v.id] ? null : `variant ${v.id} has no inventory record`) : `variant ${v.id} -> missing product ${v.productId}`))
      ?? every(Object.values(s.products), (p) => every(p.variantIds, (v) => (s.variants[v]?.productId === p.id ? null : `product ${p.id} lists variant ${v} that is not its own`)))
      ?? every(Object.values(s.cart.lines), (l) => (s.variants[l.variantId] ? null : `cart line ${l.id} -> missing variant ${l.variantId}`))
      ?? every(Object.values(s.saved), (i) => (s.variants[i.variantId] ? null : `saved ${i.id} -> missing variant`))
      ?? (s.cart.addressId && !s.addresses[s.cart.addressId] ? `cart -> missing address ${s.cart.addressId}` : null)
      ?? (s.cart.shippingOptionId && !s.shippingOptions[s.cart.shippingOptionId] ? `cart -> missing shipping option` : null)
      ?? (s.cart.deliverySlotId && !s.deliverySlots[s.cart.deliverySlotId] ? `cart -> missing delivery slot` : null)
      ?? (s.cart.paymentMethodId && !s.paymentMethods[s.cart.paymentMethodId] ? `cart -> missing payment method` : null)
      ?? (s.addresses[s.customer.defaultAddressId] ? null : "customer default address missing")
      ?? (s.paymentMethods[s.customer.defaultPaymentMethodId] ? null : "customer default payment method missing")
      ?? every(Object.values(s.deliverySlots), (d) => (s.shippingOptions[d.shippingOptionId] ? null : `slot ${d.id} -> missing shipping option`))
      ?? every(Object.values(s.orders), (o) => every(Object.values(o.lines), (l) => (!s.variants[l.variantId] ? `${o.id}/${l.id} -> missing variant` : !o.shipments[l.shipmentId] ? `${o.id}/${l.id} -> missing shipment ${l.shipmentId}` : null)) ?? every(Object.values(o.shipments), (sh) => every(sh.lineIds, (l) => (o.lines[l]?.shipmentId === sh.id ? null : `${o.id}/${sh.id} lists line ${l} not assigned to it`))))
      ?? every(Object.values(s.returns), (r) => (!s.orders[r.orderId] ? `return ${r.id} -> missing order` : every(Object.keys(r.lines), (l) => (s.orders[r.orderId]!.lines[l] ? null : `return ${r.id} -> missing line ${l}`)))),
    ),
  },
  {
    id: "delivery-groups-partition-cart",
    description: "when split, the groups cover every cart line exactly once and there are at least two",
    check: (s) => {
      const g = s.cart.deliveryGroups;
      if (g === null) return ok;
      const groups = Object.values(g);
      if (groups.length < 2) return bad(`split with ${groups.length} group(s)`);
      if (s.cart.shippingOptionId !== null) return bad("split cart also has a single shipping option");
      const seen = new Map<string, number>();
      for (const grp of groups) { if (!s.shippingOptions[grp.shippingOptionId]) return bad(`group ${grp.id} -> missing shipping option`); for (const l of grp.lineIds) seen.set(l, (seen.get(l) ?? 0) + 1); }
      for (const l of Object.keys(s.cart.lines)) if (seen.get(l) !== 1) return bad(`cart line ${l} appears ${seen.get(l) ?? 0} times across groups`);
      if (seen.size !== Object.keys(s.cart.lines).length) return bad("a group lists a line that is not in the cart");
      return ok;
    },
  },
  {
    id: "returns-bounded",
    description: "per line: cancelled + returned <= quantity; per return: refund equals the paid share of its lines; order.refunded never exceeds what was paid",
    check: (s) => wrap(
      every(Object.values(s.orders), (o) => every(Object.values(o.lines), (l) => (l.cancelled < 0 || l.returned < 0 || l.cancelled + l.returned > l.quantity ? `${o.id}/${l.id}: cancelled ${l.cancelled} + returned ${l.returned} > quantity ${l.quantity}` : null))
        ?? (o.refunded.minor > o.totals.total.minor ? `${o.id}: refunded ${o.refunded.minor} > paid ${o.totals.total.minor}` : null))
      ?? every(Object.values(s.returns), (r) => {
        const o = s.orders[r.orderId]!;
        const expected = Object.entries(r.lines).reduce((acc, [l, q]) => acc + paidShare(o, l, q).minor, 0);
        return r.refund.minor !== expected ? `return ${r.id}: refund ${r.refund.minor} != ${expected}` : every(Object.values(r.lines), (q) => (q >= 1 ? null : `return ${r.id}: non-positive quantity`));
      }),
    ),
  },
  {
    id: "slot-capacity",
    description: "bookings never exceed a delivery slot's capacity",
    check: (s) => wrap(every(Object.values(s.deliverySlots), (d) => (d.booked < 0 || d.booked > d.capacity ? `slot ${d.id}: booked ${d.booked} of ${d.capacity}` : null))),
  },
  {
    id: "loyalty-points-non-negative",
    description: "the account never goes negative and the cart never applies more than it holds",
    check: (s) => (s.customer.loyaltyPoints < 0 ? bad(`loyalty points ${s.customer.loyaltyPoints}`) : s.cart.loyaltyPointsApplied < 0 || s.cart.loyaltyPointsApplied > s.customer.loyaltyPoints ? bad(`cart applies ${s.cart.loyaltyPointsApplied} of ${s.customer.loyaltyPoints} points`) : ok),
  },
  {
    id: "single-currency",
    description: "every money value in the state is in config.currency",
    check: (s) => { const out: Array<[string, Money]> = []; moneyValues(s, "state", out); return wrap(every(out, ([p, m]) => (m.currency === s.config.currency ? null : `${p} is ${m.currency}, state currency is ${s.config.currency}`))); },
  },
  {
    id: "lines-well-formed",
    description: "cart and order lines have positive quantities, and cart line prices match the current variant price",
    check: (s) => wrap(
      every(Object.values(s.cart.lines), (l) => (l.quantity < 1 ? `cart line ${l.id}: quantity ${l.quantity}` : !equals(l.unitPrice, s.variants[l.variantId]!.price) ? `cart line ${l.id}: unit price ${l.unitPrice.minor} != variant price ${s.variants[l.variantId]!.price.minor}` : null))
      ?? every(Object.values(s.orders), (o) => every(Object.values(o.lines), (l) => (l.quantity < 1 ? `${o.id}/${l.id}: quantity ${l.quantity}` : null))),
    ),
  },
  {
    id: "order-status-derived",
    description: "each order's stored status equals the status derived from its shipments and lines",
    check: (s) => wrap(every(Object.values(s.orders), (o) => (o.status === deriveOrderStatus(o) ? null : `${o.id}: status ${o.status}, derived ${deriveOrderStatus(o)}`))),
  },
  {
    id: "counters-monotonic",
    description: "id counters are at least the number of records they have issued",
    check: (s) => {
      const lines = Object.keys(s.cart.lines).length + Object.values(s.orders).reduce((n, o) => n + Object.keys(o.lines).length, 0);
      const shipments = Object.values(s.orders).reduce((n, o) => n + Object.keys(o.shipments).length, 0);
      const checks: Array<[string, number, number]> = [["order", s.counters.order, Object.keys(s.orders).length], ["line", s.counters.line, lines], ["shipment", s.counters.shipment, shipments], ["return", s.counters.return, Object.keys(s.returns).length], ["address", s.counters.address, Object.keys(s.addresses).length], ["saved", s.counters.saved, Object.keys(s.saved).length]];
      return wrap(every(checks, ([k, c, n]) => (c < n ? `counter ${k} = ${c} < ${n} records` : null)) ?? (Object.values(s.orders).some((o) => o.number > s.counters.order) ? "order number exceeds counter" : null) ?? (money(0, s.config.currency) ? null : "unreachable"));
    },
  },
];
