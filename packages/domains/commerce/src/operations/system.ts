/** System-actor operations: the environment moves time and shipments, never the shopper. */

import type { OperationDefinition } from "@rtl/core-semantic";
import type { CommerceState, Order } from "../entities.js";
import { deriveOrderStatus } from "./orders.js";
import { OK, no, pickOrNull } from "./shared.js";

const DAY = 86_400_000;

export const advanceClock: OperationDefinition<CommerceState, { ms: number }> = {
  name: "advanceClock",
  description: "system: move session.now forward",
  params: { ms: "integer" },
  precondition: (s, p) => (p.ms > 0 ? OK : no("ms must be positive")),
  apply: (s, p) => ({ ...s, session: { ...s.session, now: s.session.now + p.ms } }),
  sample: (s, rng) => ({ ms: rng.pick([3_600_000, DAY, 3 * DAY, 10 * DAY]) }),
};

export const advanceShipment: OperationDefinition<CommerceState, { orderId: string; shipmentId: string }> = {
  name: "advanceShipment",
  description: "system: pending -> dispatched (stock leaves, cancellations freeze) -> delivered",
  params: { orderId: { kind: "ref", entity: "order" }, shipmentId: { kind: "ref", entity: "shipment" } },
  precondition: (s, p) => {
    const order = s.orders[p.orderId];
    if (!order) return no(`no order ${p.orderId}`);
    const sh = order.shipments[p.shipmentId];
    if (!sh) return no(`no shipment ${p.shipmentId}`);
    if (sh.status === "delivered") return no("shipment already delivered");
    if (sh.lineIds.every((l) => order.lines[l]!.cancelled === order.lines[l]!.quantity)) return no("every line in the shipment is cancelled");
    return OK;
  },
  apply: (s, p) => {
    const order = s.orders[p.orderId]!;
    const sh = order.shipments[p.shipmentId]!;
    const now = s.session.now;
    let inventory = s.inventory;
    let next: Order;
    if (sh.status === "pending") {
      inventory = { ...s.inventory };
      for (const l of sh.lineIds) {
        const line = order.lines[l]!;
        const inv = inventory[line.variantId]!;
        inventory[line.variantId] = { ...inv, reserved: inv.reserved - (line.quantity - line.cancelled) };
      }
      const frozen = Object.fromEntries(sh.lineIds.map((l) => [l, order.lines[l]!.cancelled]));
      next = { ...order, shipments: { ...order.shipments, [sh.id]: { ...sh, status: "dispatched", dispatchedAt: now, cancelledAtDispatch: frozen } }, events: [...order.events, { kind: "dispatched", at: now, ref: sh.id }] };
    } else {
      next = { ...order, shipments: { ...order.shipments, [sh.id]: { ...sh, status: "delivered", deliveredAt: now } }, events: [...order.events, { kind: "delivered", at: now, ref: sh.id }] };
    }
    return { ...s, inventory, orders: { ...s.orders, [order.id]: { ...next, status: deriveOrderStatus(next) } } };
  },
  sample: (s, rng) => pickOrNull(rng, Object.values(s.orders).flatMap((o) => Object.keys(o.shipments).sort().filter((sh) => advanceShipment.precondition(s, { orderId: o.id, shipmentId: sh }).ok).map((shipmentId) => ({ orderId: o.id, shipmentId }))).sort((a, b) => (a.shipmentId < b.shipmentId ? -1 : 1))),
};

export const restock: OperationDefinition<CommerceState, { variantId: string; quantity: number }> = {
  name: "restock",
  description: "system: add units to a variant's available stock",
  params: { variantId: { kind: "ref", entity: "variant" }, quantity: "integer" },
  precondition: (s, p) => (!s.inventory[p.variantId] ? no(`no variant ${p.variantId}`) : p.quantity < 1 ? no("quantity must be at least 1") : OK),
  apply: (s, p) => ({ ...s, inventory: { ...s.inventory, [p.variantId]: { ...s.inventory[p.variantId]!, available: s.inventory[p.variantId]!.available + p.quantity } } }),
  sample: (s, rng) => ({ variantId: rng.pick(Object.keys(s.inventory).sort()), quantity: rng.int(1, 10) }),
};
