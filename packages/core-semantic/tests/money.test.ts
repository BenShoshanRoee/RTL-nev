import { describe, expect, it } from "vitest";
import {
  CURRENCY_EXPONENT,
  CurrencyMismatchError,
  add,
  compare,
  equals,
  exponent,
  money,
  multiply,
  scale,
  subtract,
  sum,
  zero,
} from "../src/money.js";

describe("Money", () => {
  it("is integer minor units plus an ISO-4217 code, with a per-currency exponent", () => {
    expect(money(1990, "ILS")).toEqual({ minor: 1990, currency: "ILS" });
    expect(exponent("ILS")).toBe(2);
    expect(exponent("KWD")).toBe(3);
    expect(exponent("JPY")).toBe(0);
    expect(CURRENCY_EXPONENT.BHD).toBe(3);
  });
  it("rejects floats, non-integers, unsafe integers and unknown currencies", () => {
    expect(() => money(19.9, "ILS")).toThrow();
    expect(() => money(Number.NaN, "ILS")).toThrow();
    expect(() => money(2 ** 53, "ILS")).toThrow();
    expect(() => money(1, "XXX" as never)).toThrow();
  });
  it("adds, subtracts and multiplies by integers only", () => {
    expect(add(money(100, "ILS"), money(250, "ILS"))).toEqual(money(350, "ILS"));
    expect(subtract(money(100, "ILS"), money(250, "ILS"))).toEqual(money(-150, "ILS"));
    expect(multiply(money(1500, "KWD"), 3)).toEqual(money(4500, "KWD"));
    expect(() => multiply(money(100, "ILS"), 1.5)).toThrow();
  });
  it("throws on any cross-currency arithmetic, never coerces", () => {
    expect(() => add(money(100, "ILS"), money(100, "KWD"))).toThrow(CurrencyMismatchError);
    expect(() => subtract(money(100, "USD"), money(100, "ILS"))).toThrow(CurrencyMismatchError);
    expect(() => compare(money(1, "ILS"), money(1, "USD"))).toThrow(CurrencyMismatchError);
    expect(() => sum([money(1, "ILS"), money(1, "KWD")], "ILS")).toThrow(CurrencyMismatchError);
  });
  it("scales with integer arithmetic and explicit rounding (VAT-style)", () => {
    // 17% of 10.00 ILS = 1.70; 17% of 10.05 = 1.7085 -> half-up 1.71, down 1.70
    expect(scale(money(1000, "ILS"), 17, 100)).toEqual(money(170, "ILS"));
    expect(scale(money(1005, "ILS"), 17, 100, "half-up")).toEqual(money(171, "ILS"));
    expect(scale(money(1005, "ILS"), 17, 100, "down")).toEqual(money(170, "ILS"));
    expect(scale(money(1005, "ILS"), 17, 100, "up")).toEqual(money(171, "ILS"));
    // 3-decimal currency: 1.500 KWD * 2/3 = 1.000 KWD exactly
    expect(scale(money(1500, "KWD"), 2, 3)).toEqual(money(1000, "KWD"));
    // half-even tie: 12.5 -> 12, 13.5 -> 14
    expect(scale(money(25, "ILS"), 1, 2, "half-even")).toEqual(money(12, "ILS"));
    expect(scale(money(27, "ILS"), 1, 2, "half-even")).toEqual(money(14, "ILS"));
    expect(() => scale(money(1, "ILS"), 1, 0)).toThrow();
    // large amounts do not lose precision
    expect(scale(money(9_007_199_254_740, "ILS"), 3, 3)).toEqual(money(9_007_199_254_740, "ILS"));
  });
  it("compares, sums and has a zero", () => {
    expect(compare(money(1, "ILS"), money(2, "ILS"))).toBe(-1);
    expect(equals(money(2, "ILS"), money(2, "ILS"))).toBe(true);
    expect(sum([money(1, "KWD"), money(2, "KWD")], "KWD")).toEqual(money(3, "KWD"));
    expect(sum([], "KWD")).toEqual(zero("KWD"));
  });
});
