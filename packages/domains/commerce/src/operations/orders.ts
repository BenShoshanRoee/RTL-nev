import { add, money, sum, type OperationDefinition } from "@rtl/core-semantic";
import { RETURN_REASONS, type CommerceState, type Order } from "../entities.js";
import { OK, no, pad, pickOrNull } from "./shared.js";
import { paidShare } from "./totals.js";

const DAY = 86_400_000;

export function deriveOrderStatus(order: Order): Order["status"] {
  const lines = Object.values(order.lines);
  if (lines.length && lines.every((l) => l.cancelled === l.quantity)) return "cancelled";
  const live = Object.values(order.shipments).filter((sh) => sh.lineIds.some((l) => order.lines[l]!.cancelled < order.lines[l]!.quantity));
  if (live.length && live.every((sh) => sh.status === "delivered")) return "delivered";
  if (live.length && live.every((sh) => sh.status !== "pending")) return "dispatched";
  if (live.some((sh) => sh.status !== "pending")) return "partially_dispatched";
  return "pending";
}

function withOrder(s: CommerceState, order: Order): CommerceState {
  return { ...s, orders: { ...s.orders, [order.id]: { ...order, status: deriveOrderStatus(order) } } };
}

export const cancelLine: OperationDefinition<CommerceState, { orderId: string; lineId: string; quantity: number }> = {
  name: "cancelLine",
  description: "cancel units of an order line before its shipment is dispatched; stock is released and the amount refunded",
  params: { orderId: { kind: "ref", entity: "order" }, lineId: { kind: "ref", entity: "orderLine" }, quantity: "integer" },
  precondition: (s, p) => {
    const order = s.orders[p.orderId];
    if (!order) return no(`no order ${p.orderId}`);
    const line = order.lines[p.lineId];
    if (!line) return no(`no line ${p.lineId} in order ${p.orderId}`);
    if (order.shipments[line.shipmentId]!.status !== "pending") return no("line has already been dispatched and cannot be cancelled");
    if (p.quantity < 1) return no("quantity must be at least 1");
    if (p.quantity > line.quantity - line.cancelled) return no(`only ${line.quantity - line.cancelled} units can still be cancelled`);
    return OK;
  },
  apply: (s, p) => {
    const order = s.orders[p.orderId]!;
    const line = order.lines[p.lineId]!;
    const inv = s.inventory[line.variantId]!;
    const lines = { ...order.lines, [line.id]: { ...line, cancelled: line.cancelled + p.quantity } };
    let refund = paidShare(order, line.id, p.quantity);
    if (Object.values(lines).every((l) => l.cancelled === l.quantity)) refund = add(refund, order.totals.shipping);
    const next: Order = {
      ...order,
      lines,
      refunded: add(order.refunded, refund),
      events: [...order.events, { kind: "line_cancelled", at: s.session.now, ref: line.id }],
    };
    return withOrder({ ...s, inventory: { ...s.inventory, [line.variantId]: { ...inv, available: inv.available + p.quantity, reserved: inv.reserved - p.quantity } } }, next);
  },
  sample: (s, rng) => {
    const options = Object.values(s.orders).flatMap((o) => Object.values(o.lines).filter((l) => o.shipments[l.shipmentId]!.status === "pending" && l.cancelled < l.quantity).map((l) => ({ orderId: o.id, lineId: l.id, max: l.quantity - l.cancelled })));
    const pick = pickOrNull(rng, options.sort((a, b) => (a.lineId < b.lineId ? -1 : 1)));
    return pick ? { orderId: pick.orderId, lineId: pick.lineId, quantity: rng.int(1, pick.max + 1) } : null;
  },
};

export const cancelOrder: OperationDefinition<CommerceState, { orderId: string }> = {
  name: "cancelOrder",
  description: "cancel a whole order while every shipment is still pending",
  params: { orderId: { kind: "ref", entity: "order" } },
  precondition: (s, p) => {
    const order = s.orders[p.orderId];
    if (!order) return no(`no order ${p.orderId}`);
    if (order.status === "cancelled") return no("order is already cancelled");
    if (Object.values(order.shipments).some((sh) => sh.status !== "pending")) return no("order has dispatched or delivered shipments and cannot be cancelled");
    return OK;
  },
  apply: (s, p) => {
    const order = s.orders[p.orderId]!;
    const inventory = { ...s.inventory };
    let refund = money(0, s.config.currency);
    const lines = { ...order.lines };
    for (const l of Object.values(order.lines)) {
      const remaining = l.quantity - l.cancelled;
      if (remaining === 0) continue;
      const inv = inventory[l.variantId]!;
      inventory[l.variantId] = { ...inv, available: inv.available + remaining, reserved: inv.reserved - remaining };
      refund = add(refund, paidShare(order, l.id, remaining));
      lines[l.id] = { ...l, cancelled: l.quantity };
    }
    refund = add(refund, order.totals.shipping);
    return withOrder({ ...s, inventory }, { ...order, lines, refunded: add(order.refunded, refund), events: [...order.events, { kind: "cancelled", at: s.session.now, ref: order.id }] });
  },
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.orders).sort().filter((id) => cancelOrder.precondition(s, { orderId: id }).ok).map((orderId) => ({ orderId }))),
};

export function returnBlocker(s: CommerceState, orderId: string, lines: Record<string, number>): string | null {
  const order = s.orders[orderId];
  if (!order) return `no order ${orderId}`;
  const entries = Object.entries(lines);
  if (!entries.length) return "choose at least one line to return";
  for (const [lineId, qty] of entries) {
    const line = order.lines[lineId];
    if (!line) return `no line ${lineId} in order ${orderId}`;
    const sh = order.shipments[line.shipmentId]!;
    if (sh.status !== "delivered") return "only delivered lines can be returned";
    if (s.session.now - sh.deliveredAt! > s.config.returnWindowDays * DAY) return `return window of ${s.config.returnWindowDays} days has passed`;
    if (!Number.isSafeInteger(qty) || qty < 1) return "return quantity must be at least 1";
    if (qty > line.quantity - line.cancelled - line.returned) return `return quantity exceeds the ${line.quantity - line.cancelled - line.returned} units still held`;
  }
  return null;
}

export const requestReturn: OperationDefinition<CommerceState, { orderId: string; lines: Record<string, number>; reasonKey: string }> = {
  name: "requestReturn",
  description: "open a return for delivered units within the return window",
  params: { orderId: { kind: "ref", entity: "order" }, lines: { kind: "record", entity: "quantities" }, reasonKey: { kind: "enum", values: RETURN_REASONS } },
  precondition: (s, p) => { const why = returnBlocker(s, p.orderId, p.lines); return why ? no(why) : OK; },
  apply: (s, p) => {
    const order = s.orders[p.orderId]!;
    const counters = { ...s.counters, return: s.counters.return + 1 };
    const id = `r${pad(counters.return, 4)}`;
    const refund = sum(Object.entries(p.lines).map(([lineId, qty]) => paidShare(order, lineId, qty)), s.config.currency);
    const lines = { ...order.lines };
    for (const [lineId, qty] of Object.entries(p.lines)) lines[lineId] = { ...lines[lineId]!, returned: lines[lineId]!.returned + qty };
    const next: Order = { ...order, lines, refunded: add(order.refunded, refund), events: [...order.events, { kind: "return_requested", at: s.session.now, ref: id }] };
    return withOrder({ ...s, counters, returns: { ...s.returns, [id]: { id, orderId: order.id, lines: { ...p.lines }, reasonKey: p.reasonKey, status: "requested", refund, requestedAt: s.session.now } } }, next);
  },
  sample: (s, rng) => {
    const options = Object.values(s.orders).flatMap((o) => Object.values(o.lines).filter((l) => returnBlocker(s, o.id, { [l.id]: 1 }) === null).map((l) => ({ orderId: o.id, lineId: l.id, max: l.quantity - l.cancelled - l.returned })));
    const pick = pickOrNull(rng, options.sort((a, b) => (a.lineId < b.lineId ? -1 : 1)));
    return pick ? { orderId: pick.orderId, lines: { [pick.lineId]: rng.int(1, pick.max + 1) }, reasonKey: rng.pick(RETURN_REASONS) } : null;
  },
};

export const trackOrder: OperationDefinition<CommerceState, { orderId: string }> = {
  name: "trackOrder",
  description: "open an order's tracking page; recorded in session.lastTrackedOrderId",
  params: { orderId: { kind: "ref", entity: "order" } },
  precondition: (s, p) => (s.orders[p.orderId] ? OK : no(`no order ${p.orderId}`)),
  apply: (s, p) => ({ ...s, session: { ...s.session, lastTrackedOrderId: p.orderId } }),
  sample: (s, rng) => pickOrNull(rng, Object.keys(s.orders).sort().map((orderId) => ({ orderId }))),
};
