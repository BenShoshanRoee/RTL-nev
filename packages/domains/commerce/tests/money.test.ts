import { describe, expect, it } from "vitest";
import { CurrencyMismatchError, Rng, execute, exponent, money } from "@rtl/core-semantic";
import { commerceDomain, seedCommerce } from "../src/index.js";
import { ok, stockedVariant } from "./helpers.js";

describe("money in a three-decimal currency", () => {
  it("a KWD cart totals with exponent 3 and VAT is integer-scaled", () => {
    let s = seedCommerce(new Rng(42, "seed"), { currency: "KWD" });
    expect(s.config.currency).toBe("KWD");
    expect(exponent(s.config.currency)).toBe(3);
    const v = stockedVariant(s, 2);
    expect(s.variants[v]!.price.currency).toBe("KWD");
    s = ok(s, "addToCart", { variantId: v, quantity: 2 });
    expect(s.cart.totals.subtotal).toEqual(money(s.variants[v]!.price.minor * 2, "KWD"));
    const rate = s.config.vatPercent;
    const total = s.cart.totals.total.minor;
    const vat = Math.round((total * rate) / (100 + rate));
    expect(Math.abs(s.cart.totals.vat.minor - vat)).toBeLessThanOrEqual(1);
    expect(Number.isInteger(s.cart.totals.vat.minor)).toBe(true);
  });
  it("adding an ILS-priced line to a KWD cart throws CurrencyMismatchError", () => {
    const s = seedCommerce(new Rng(42, "seed"), { currency: "KWD" });
    const v = stockedVariant(s, 2);
    const poisoned = { ...s, variants: { ...s.variants, [v]: { ...s.variants[v]!, price: money(1990, "ILS") } } };
    expect(() => execute(commerceDomain, poisoned, "addToCart", { variantId: v, quantity: 1 }, { rng: new Rng(1), now: () => 0 })).toThrow(CurrencyMismatchError);
  });
  it("a 1.500 KWD item times three is 4.500 KWD", () => {
    let s = seedCommerce(new Rng(42, "seed"), { currency: "KWD" });
    const v = stockedVariant(s, 3);
    s = { ...s, variants: { ...s.variants, [v]: { ...s.variants[v]!, price: money(1500, "KWD") } } };
    s = ok(s, "addToCart", { variantId: v, quantity: 3 });
    expect(s.cart.totals.subtotal).toEqual(money(4500, "KWD"));
  });
});
