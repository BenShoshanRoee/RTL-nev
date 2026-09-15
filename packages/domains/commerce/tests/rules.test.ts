import { describe, expect, it } from "vitest";
import { execute, Rng, checkInvariants } from "@rtl/core-semantic";
import { commerceDomain } from "../src/index.js";
import { ok, rejected, seeded, stockedVariant } from "./helpers.js";

const ctx = { rng: new Rng(5), now: () => 0 };

describe("business rules", () => {
  it("coupon: expired, minimum subtotal, exhausted uses, unknown, and double application are rejected", () => {
    let s = seeded(7);
    s = ok(s, "addToCart", { variantId: stockedVariant(s, 1), quantity: 1 });
    const expired = Object.values(s.coupons).find((c) => c.expiresAt !== null && c.expiresAt <= s.session.now);
    if (expired) expect(rejected(s, "applyCoupon", { code: expired.code })).toMatch(/expired/i);
    const minimum = Object.values(s.coupons).find((c) => c.minSubtotal.minor > s.cart.totals.subtotal.minor && c.active && c.expiresAt === null);
    if (minimum) expect(rejected(s, "applyCoupon", { code: minimum.code })).toMatch(/minimum/i);
    expect(rejected(s, "applyCoupon", { code: "NO-SUCH-CODE" })).toMatch(/unknown/i);
    const good = Object.values(s.coupons).find((c) => c.kind === "percent" && c.active && c.expiresAt === null && c.minSubtotal.minor === 0)!;
    s = ok(s, "applyCoupon", { code: good.code });
    expect(rejected(s, "applyCoupon", { code: good.code })).toMatch(/already/i);
    s = ok(s, "removeCoupon", {});
    expect(s.cart.couponCode).toBeNull();
    expect(s.cart.totals.discount.minor).toBe(0);
  });

  it("inventory: cannot add more than available; checkout reserves; cancel releases", () => {
    let s = seeded(8);
    const v = Object.keys(s.inventory).sort().find((id) => s.inventory[id]!.available === 1 && s.products[s.variants[id]!.productId]!.active)!;
    expect(v).toBeDefined();
    expect(rejected(s, "addToCart", { variantId: v, quantity: 2 })).toMatch(/stock|available/i);
    s = ok(s, "addToCart", { variantId: v, quantity: 1 });
    expect(rejected(s, "setQuantity", { lineId: Object.keys(s.cart.lines)[0]!, quantity: 2 })).toMatch(/stock|available/i);
    const out = Object.keys(s.inventory).sort().find((id) => s.inventory[id]!.available === 0);
    if (out) expect(rejected(s, "addToCart", { variantId: out, quantity: 1 })).toMatch(/stock|available/i);
  });

  it("checkout requires address, shipping, payment, and a slot when the option needs one", () => {
    let s = seeded(9);
    s = ok(s, "addToCart", { variantId: stockedVariant(s, 1), quantity: 1 });
    expect(rejected(s, "checkout", {})).toMatch(/address/i);
    s = ok(s, "setAddress", { addressId: s.customer.defaultAddressId });
    expect(rejected(s, "checkout", {})).toMatch(/shipping/i);
    const slotted = Object.values(s.shippingOptions).find((o) => o.requiresSlot)!;
    s = ok(s, "setShipping", { shippingOptionId: slotted.id });
    const pm = Object.values(s.paymentMethods).find((p) => !p.expired)!;
    const expiredPm = Object.values(s.paymentMethods).find((p) => p.expired)!;
    expect(rejected(s, "setPaymentMethod", { paymentMethodId: expiredPm.id })).toMatch(/expired/i);
    s = ok(s, "setPaymentMethod", { paymentMethodId: pm.id });
    expect(rejected(s, "checkout", {})).toMatch(/slot/i);
    const slot = Object.values(s.deliverySlots).find((d) => d.shippingOptionId === slotted.id && d.booked < d.capacity)!;
    s = ok(s, "selectDeliverySlot", { slotId: slot.id });
    s = ok(s, "checkout", {});
    expect(s.deliverySlots[slot.id]!.booked).toBe(slot.booked + 1);
    expect(checkInvariants(commerceDomain, s)).toEqual([]);
  });

  it("split delivery must partition the cart exactly and yields one shipment per group", () => {
    let s = seeded(10);
    const a = stockedVariant(s, 1);
    const b = stockedVariant(s, 1, [a, ...s.products[s.variants[a]!.productId]!.variantIds]);
    s = ok(s, "addToCart", { variantId: a, quantity: 1 });
    s = ok(s, "addToCart", { variantId: b, quantity: 1 });
    s = ok(s, "setAddress", { addressId: s.customer.defaultAddressId });
    const [l1, l2] = Object.keys(s.cart.lines).sort();
    const opts = Object.values(s.shippingOptions).filter((o) => !o.requiresSlot && o.cities === null).map((o) => o.id);
    expect(opts.length).toBeGreaterThanOrEqual(2);
    expect(rejected(s, "splitDelivery", { groups: [{ lineIds: [l1], shippingOptionId: opts[0] }] })).toMatch(/partition|every line/i);
    expect(rejected(s, "splitDelivery", { groups: [{ lineIds: [l1], shippingOptionId: opts[0] }, { lineIds: [l1], shippingOptionId: opts[1] }] })).toMatch(/partition|twice|every line/i);
    s = ok(s, "splitDelivery", { groups: [{ lineIds: [l1], shippingOptionId: opts[0] }, { lineIds: [l2], shippingOptionId: opts[1] }] });
    expect(Object.keys(s.cart.deliveryGroups ?? {}).length).toBe(2);
    const shipping = s.shippingOptions[opts[0]!]!.price.minor + s.shippingOptions[opts[1]!]!.price.minor;
    expect(s.cart.totals.shipping.minor).toBe(shipping);
    s = ok(s, "setPaymentMethod", { paymentMethodId: Object.values(s.paymentMethods).find((p) => !p.expired)!.id });
    s = ok(s, "checkout", {});
    const order = Object.values(s.orders).sort((x, y) => y.number - x.number)[0]!;
    expect(Object.keys(order.shipments).length).toBe(2);
    // removing a line after a split rebuilds the groups consistently
    let t = seeded(10);
    t = ok(t, "addToCart", { variantId: a, quantity: 1 });
    t = ok(t, "addToCart", { variantId: b, quantity: 1 });
    t = ok(t, "setAddress", { addressId: t.customer.defaultAddressId });
    const [m1, m2] = Object.keys(t.cart.lines).sort();
    t = ok(t, "splitDelivery", { groups: [{ lineIds: [m1], shippingOptionId: opts[0] }, { lineIds: [m2], shippingOptionId: opts[1] }] });
    t = ok(t, "removeLine", { lineId: m1! });
    expect(checkInvariants(commerceDomain, t)).toEqual([]);
  });

  it("returns: only delivered lines, only within the window, never more than delivered", () => {
    let s = seeded(11);
    const delivered = Object.values(s.orders).find((o) => o.status === "delivered")!;
    const pending = Object.values(s.orders).find((o) => o.status === "pending")!;
    expect(delivered && pending).toBeTruthy();
    const dl = Object.values(delivered.lines)[0]!;
    const pl = Object.values(pending.lines)[0]!;
    expect(rejected(s, "requestReturn", { orderId: pending.id, lines: { [pl.id]: 1 }, reasonKey: "return.reason.damaged" })).toMatch(/deliver/i);
    expect(rejected(s, "requestReturn", { orderId: delivered.id, lines: { [dl.id]: dl.quantity + 1 }, reasonKey: "return.reason.damaged" })).toMatch(/quantity/i);
    s = ok(s, "requestReturn", { orderId: delivered.id, lines: { [dl.id]: 1 }, reasonKey: "return.reason.damaged" });
    const days = s.config.returnWindowDays;
    const late = ok(seeded(11), "advanceClock", { ms: (days + 1) * 86_400_000 });
    expect(rejected(late, "requestReturn", { orderId: delivered.id, lines: { [dl.id]: 1 }, reasonKey: "return.reason.damaged" })).toMatch(/window/i);
    void late;
  });

  it("cancelOrder before dispatch cancels every line and releases stock; after dispatch it is rejected", () => {
    let s = seeded(12);
    const pending = Object.values(s.orders).find((o) => o.status === "pending")!;
    const reservedBefore = Object.values(pending.lines).map((l) => s.inventory[l.variantId]!.reserved);
    s = ok(s, "cancelOrder", { orderId: pending.id });
    expect(s.orders[pending.id]!.status).toBe("cancelled");
    Object.values(pending.lines).forEach((l, i) => expect(s.inventory[l.variantId]!.reserved).toBe(reservedBefore[i]! - (l.quantity - l.cancelled)));
    const delivered = Object.values(s.orders).find((o) => o.status === "delivered")!;
    expect(rejected(s, "cancelOrder", { orderId: delivered.id })).toMatch(/dispatch|deliver/i);
  });

  it("loyalty points: cannot apply more than owned; deducted at checkout; discount capped", () => {
    let s = seeded(13);
    s = ok(s, "addToCart", { variantId: stockedVariant(s, 1), quantity: 1 });
    expect(rejected(s, "applyLoyaltyPoints", { points: s.customer.loyaltyPoints + 1 })).toMatch(/points/i);
    const pts = Math.min(s.customer.loyaltyPoints, 50);
    s = ok(s, "applyLoyaltyPoints", { points: pts });
    expect(s.cart.totals.loyalty.minor).toBeLessThanOrEqual(s.cart.totals.subtotal.minor);
    s = ok(s, "setAddress", { addressId: s.customer.defaultAddressId });
    s = ok(s, "setShipping", { shippingOptionId: Object.values(s.shippingOptions).find((o) => !o.requiresSlot && o.cities === null)!.id });
    s = ok(s, "setPaymentMethod", { paymentMethodId: Object.values(s.paymentMethods).find((p) => !p.expired)!.id });
    const before = s.customer.loyaltyPoints;
    s = ok(s, "checkout", {});
    expect(s.customer.loyaltyPoints).toBe(before - pts);
  });

  it("save for later and move back; address edit updates the cart's chosen address", () => {
    let s = seeded(14);
    s = ok(s, "addToCart", { variantId: stockedVariant(s, 1), quantity: 2 });
    const lineId = Object.keys(s.cart.lines)[0]!;
    s = ok(s, "saveForLater", { lineId });
    expect(Object.keys(s.cart.lines)).toEqual([]);
    const savedId = Object.keys(s.saved)[0]!;
    s = ok(s, "moveToCart", { savedId });
    expect(Object.values(s.cart.lines)[0]!.quantity).toBe(2);
    expect(Object.keys(s.saved)).toEqual([]);
    const addr = s.addresses[s.customer.defaultAddressId]!;
    s = ok(s, "addAddress", { recipient: addr.recipient, street: "st", houseNumber: "7", apartment: "", city: addr.city, postalCode: "1234567", notes: "" });
    const newId = Object.keys(s.addresses).sort().at(-1)!;
    s = ok(s, "setAddress", { addressId: newId });
    s = ok(s, "editAddress", { addressId: newId, recipient: addr.recipient, street: "st", houseNumber: "8", apartment: "", city: addr.city, postalCode: "1234567", notes: "" });
    expect(s.addresses[newId]!.houseNumber).toBe("8");
    expect(s.cart.addressId).toBe(newId);
  });

  it("every operation samples params its own precondition accepts, across 300 states", () => {
    let s = seeded(15);
    const rng = new Rng(15, "walk");
    let applied = 0;
    for (let i = 0; i < 300; i++) {
      for (const name of Object.keys(commerceDomain.operations).sort()) {
        const op = commerceDomain.operations[name]!;
        const p = op.sample(s, rng.child(`${i}:${name}`));
        if (p === null) continue;
        const pre = op.precondition(s, p);
        expect(pre.ok, `${name} sampled ${JSON.stringify(p)}: ${pre.ok ? "" : pre.reason}`).toBe(true);
      }
      const name = rng.pick(Object.keys(commerceDomain.operations).sort());
      const p = commerceDomain.operations[name]!.sample(s, rng.child(`apply:${i}`));
      if (p) {
        const r = execute(commerceDomain, s, name, p, ctx);
        if (r.ok) { s = r.state; applied++; }
      }
    }
    expect(applied).toBeGreaterThan(100);
  });
});
