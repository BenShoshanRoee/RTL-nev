import { describe, expect, it } from "vitest";
import { equals, money, add, multiply, subtract } from "@rtl/core-semantic";
import { paidShare } from "../src/index.js";
import { ctx, ok, rejected, seeded, stockedVariant } from "./helpers.js";

describe("full commerce flow", () => {
  it("search -> add -> change size -> coupon -> checkout -> partial cancel -> return", () => {
    let s = seeded(42);
    const cur = s.config.currency;

    // search records its result in state
    const v1 = stockedVariant(s, 3);
    const product = s.products[s.variants[v1]!.productId]!;
    s = ok(s, "search", { query: product.tags[0] ?? "", category: product.category, sort: "price_asc" });
    expect(s.session.lastSearch?.resultIds).toContain(product.id);
    s = ok(s, "viewProduct", { productId: product.id });
    expect(s.session.recentlyViewed[0]).toBe(product.id);

    // add two units
    s = ok(s, "addToCart", { variantId: v1, quantity: 2 });
    const line = Object.values(s.cart.lines)[0]!;
    expect(line.variantId).toBe(v1);
    expect(line.quantity).toBe(2);
    expect(equals(s.cart.totals.subtotal, multiply(s.variants[v1]!.price, 2))).toBe(true);

    // change size to a sibling variant with stock
    const sibling = product.variantIds.find((id) => id !== v1 && s.inventory[id]!.available >= 2)!;
    expect(sibling).toBeDefined();
    s = ok(s, "changeVariant", { lineId: line.id, variantId: sibling });
    expect(s.cart.lines[line.id]!.variantId).toBe(sibling);
    expect(equals(s.cart.lines[line.id]!.unitPrice, s.variants[sibling]!.price)).toBe(true);

    // coupon: a valid percent coupon from the seed
    const coupon = Object.values(s.coupons).find((c) => c.kind === "percent" && c.active && c.expiresAt === null && c.minSubtotal.minor === 0)!;
    expect(coupon).toBeDefined();
    s = ok(s, "applyCoupon", { code: coupon.code });
    expect(s.cart.couponCode).toBe(coupon.code);
    expect(s.cart.totals.discount.minor).toBeGreaterThan(0);
    expect(rejected(s, "applyCoupon", { code: coupon.code })).toMatch(/coupon/i);

    // address, shipping, payment
    const addressId = s.customer.defaultAddressId;
    s = ok(s, "setAddress", { addressId });
    const option = Object.values(s.shippingOptions).find((o) => !o.requiresSlot && (o.cities === null || o.cities.includes(s.addresses[addressId]!.city)))!;
    s = ok(s, "setShipping", { shippingOptionId: option.id });
    const pm = Object.values(s.paymentMethods).find((p) => !p.expired)!;
    s = ok(s, "setPaymentMethod", { paymentMethodId: pm.id });
    const expectedTotal = add(subtract(s.cart.totals.subtotal, s.cart.totals.discount), option.price);
    expect(equals(s.cart.totals.total, expectedTotal)).toBe(true);
    expect(s.cart.totals.vat.minor).toBeGreaterThan(0);

    // checkout
    const availableBefore = s.inventory[sibling]!.available;
    const usesBefore = s.coupons[coupon.code]!.uses;
    const ordersBefore = Object.keys(s.orders).length;
    s = ok(s, "checkout", {});
    expect(Object.keys(s.orders).length).toBe(ordersBefore + 1);
    const order = Object.values(s.orders).sort((a, b) => b.number - a.number)[0]!;
    expect(order.status).toBe("pending");
    expect(order.couponCode).toBe(coupon.code);
    expect(equals(order.totals.total, expectedTotal)).toBe(true);
    expect(s.inventory[sibling]!.available).toBe(availableBefore - 2);
    expect(s.inventory[sibling]!.reserved).toBe(2);
    expect(s.coupons[coupon.code]!.uses).toBe(usesBefore + 1);
    expect(Object.keys(s.cart.lines)).toEqual([]);
    expect(s.cart.couponCode).toBeNull();

    // partial cancel before dispatch: 1 of 2 units
    const oline = Object.values(order.lines)[0]!;
    s = ok(s, "cancelLine", { orderId: order.id, lineId: oline.id, quantity: 1 });
    expect(s.orders[order.id]!.lines[oline.id]!.cancelled).toBe(1);
    expect(s.inventory[sibling]!.available).toBe(availableBefore - 1);
    expect(s.inventory[sibling]!.reserved).toBe(1);
    expect(equals(s.orders[order.id]!.refunded, paidShare(order, oline.id, 1))).toBe(true);
    expect(s.orders[order.id]!.refunded.minor).toBeLessThan(s.variants[sibling]!.price.minor); // coupon share deducted

    // dispatch and deliver, then the remaining unit cannot be cancelled
    const shipmentId = Object.keys(s.orders[order.id]!.shipments)[0]!;
    s = ok(s, "advanceShipment", { orderId: order.id, shipmentId });
    expect(s.orders[order.id]!.shipments[shipmentId]!.status).toBe("dispatched");
    expect(s.inventory[sibling]!.reserved).toBe(0);
    expect(rejected(s, "cancelLine", { orderId: order.id, lineId: oline.id, quantity: 1 })).toMatch(/dispatch/i);
    s = ok(s, "advanceShipment", { orderId: order.id, shipmentId });
    expect(s.orders[order.id]!.status).toBe("delivered");

    // return the remaining unit within the window
    s = ok(s, "requestReturn", { orderId: order.id, lines: { [oline.id]: 1 }, reasonKey: "return.reason.wrong_size" });
    const ret = Object.values(s.returns).sort((a, b) => b.requestedAt - a.requestedAt)[0]!;
    expect(ret.orderId).toBe(order.id);
    expect(ret.status).toBe("requested");
    expect(equals(ret.refund, paidShare(order, oline.id, 1))).toBe(true);
    expect(s.orders[order.id]!.refunded.minor).toBeLessThanOrEqual(order.totals.total.minor);
    expect(s.orders[order.id]!.lines[oline.id]!.returned).toBe(1);
    expect(rejected(s, "requestReturn", { orderId: order.id, lines: { [oline.id]: 1 }, reasonKey: "return.reason.wrong_size" })).toMatch(/quantity/i);
    expect(money(0, cur).currency).toBe("ILS");
    void ctx;
  });
});
