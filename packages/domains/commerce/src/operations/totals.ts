/** Cart and order totals. Prices are VAT-inclusive; `vat` is the VAT contained in `total`. */

import { add, money, scale, subtract, sum, type CurrencyCode, type Money } from "@rtl/core-semantic";
import type { CartLine, CommerceState, DeliveryGroup, OrderLine, Totals } from "../entities.js";

export function emptyTotals(currency: CurrencyCode): Totals {
  const z = money(0, currency);
  return { subtotal: z, discount: z, loyalty: z, shipping: z, vat: z, total: z };
}

export interface TotalsInput {
  lines: Record<string, CartLine>;
  couponCode: string | null;
  loyaltyPointsApplied: number;
  shippingOptionId: string | null;
  deliveryGroups: Record<string, DeliveryGroup> | null;
}

export function lineTotal(line: { unitPrice: Money; quantity: number }): Money {
  return money(line.unitPrice.minor * line.quantity, line.unitPrice.currency);
}

function minMoney(a: Money, b: Money): Money {
  return a.minor <= b.minor ? a : b;
}

export function couponDiscount(state: CommerceState, input: TotalsInput, subtotal: Money): Money {
  const currency = state.config.currency;
  if (!input.couponCode) return money(0, currency);
  const coupon = state.coupons[input.couponCode];
  if (!coupon) return money(0, currency);
  const eligible = coupon.category
    ? sum(Object.values(input.lines).filter((l) => state.products[state.variants[l.variantId]!.productId]!.category === coupon.category).map(lineTotal), currency)
    : subtotal;
  if (coupon.kind === "percent") return scale(eligible, coupon.value, 100, "half-up");
  if (coupon.kind === "fixed") return minMoney(money(coupon.value, currency), eligible);
  return money(0, currency);
}

export function computeTotals(state: CommerceState, input: TotalsInput): Totals {
  const currency = state.config.currency;
  const subtotal = sum(Object.values(input.lines).map(lineTotal), currency);
  const discount = minMoney(couponDiscount(state, input, subtotal), subtotal);
  const afterDiscount = subtract(subtotal, discount);
  const loyalty = minMoney(money(input.loyaltyPointsApplied * state.config.loyaltyPointValueMinor, currency), afterDiscount);
  const freeShipping = input.couponCode !== null && state.coupons[input.couponCode]?.kind === "free_shipping";
  let shipping = money(0, currency);
  if (!freeShipping) {
    if (input.deliveryGroups) {
      shipping = sum(Object.values(input.deliveryGroups).map((g) => state.shippingOptions[g.shippingOptionId]?.price ?? money(0, currency)), currency);
    } else if (input.shippingOptionId) {
      shipping = state.shippingOptions[input.shippingOptionId]?.price ?? money(0, currency);
    }
  }
  const total = add(subtract(afterDiscount, loyalty), shipping);
  const vat = scale(total, state.config.vatPercent, 100 + state.config.vatPercent, "half-up");
  return { subtotal, discount, loyalty, shipping, vat, total };
}

/**
 * What the customer actually paid for `quantity` units of an order line: the gross line
 * amount reduced by the order's discount and loyalty share, rounded down so the refunds of
 * all lines never exceed what was paid.
 */
export function paidShare(order: { totals: Totals; lines: Record<string, OrderLine> }, lineId: string, quantity: number): Money {
  const line = order.lines[lineId]!;
  const gross = lineTotal({ unitPrice: line.unitPrice, quantity });
  const subtotal = order.totals.subtotal.minor;
  if (subtotal === 0) return money(0, gross.currency);
  const net = subtotal - order.totals.discount.minor - order.totals.loyalty.minor;
  return scale(gross, net, subtotal, "down");
}

/** Recompute cart totals after any cart mutation. */
export function withTotals(state: CommerceState): CommerceState {
  return { ...state, cart: { ...state.cart, totals: computeTotals(state, state.cart) } };
}
