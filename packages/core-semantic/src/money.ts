/**
 * Money is integer minor units plus an ISO-4217 code. The exponent table below is the only
 * place decimals are known; rendering to a decimal string is the formatter's job (3.1.2).
 * Cross-currency arithmetic throws. No float ever enters a money path.
 * Mirrored by bench/rtlenv/domain_protocol.py.
 */

export const CURRENCY_EXPONENT = {
  ILS: 2, USD: 2, EUR: 2, GBP: 2, AED: 2, SAR: 2, EGP: 2, QAR: 2, MAD: 2, TRY: 2,
  JOD: 3, KWD: 3, BHD: 3, OMR: 3, IQD: 3, TND: 3, LYD: 3,
  JPY: 0,
} as const;

export type CurrencyCode = keyof typeof CURRENCY_EXPONENT;

/** A type alias (not an interface) so it satisfies the JSON index signature of state trees. */
export type Money = {
  readonly minor: number;
  readonly currency: CurrencyCode;
};

export type Rounding = "half-up" | "half-even" | "down" | "up";

export class InvalidMoneyError extends RangeError {}
export class CurrencyMismatchError extends Error {
  constructor(a: CurrencyCode, b: CurrencyCode) {
    super(`currency mismatch: ${a} vs ${b}; convert explicitly, never coerce`);
  }
}

export function isCurrency(code: string): code is CurrencyCode {
  return Object.prototype.hasOwnProperty.call(CURRENCY_EXPONENT, code);
}

export function exponent(currency: CurrencyCode): number {
  if (!isCurrency(currency)) throw new InvalidMoneyError(`unknown currency ${String(currency)}`);
  return CURRENCY_EXPONENT[currency];
}

export function money(minor: number, currency: CurrencyCode): Money {
  if (!Number.isSafeInteger(minor)) throw new InvalidMoneyError(`minor units must be a safe integer, got ${minor}`);
  exponent(currency);
  return { minor, currency };
}

export function zero(currency: CurrencyCode): Money {
  return money(0, currency);
}

export function assertSameCurrency(a: Money, b: Money): void {
  if (a.currency !== b.currency) throw new CurrencyMismatchError(a.currency, b.currency);
}

export function add(a: Money, b: Money): Money {
  assertSameCurrency(a, b);
  return money(a.minor + b.minor, a.currency);
}

export function subtract(a: Money, b: Money): Money {
  assertSameCurrency(a, b);
  return money(a.minor - b.minor, a.currency);
}

export function negate(a: Money): Money {
  return money(-a.minor, a.currency);
}

export function multiply(a: Money, factor: number): Money {
  if (!Number.isSafeInteger(factor)) throw new InvalidMoneyError(`multiply factor must be an integer, got ${factor}`);
  return money(a.minor * factor, a.currency);
}

/** a * numerator / denominator with integer arithmetic and explicit rounding. */
export function scale(a: Money, numerator: number, denominator: number, rounding: Rounding = "half-up"): Money {
  if (!Number.isSafeInteger(numerator) || !Number.isSafeInteger(denominator)) {
    throw new InvalidMoneyError("scale() takes integer numerator and denominator");
  }
  if (denominator === 0) throw new InvalidMoneyError("scale() denominator must not be zero");
  let num = BigInt(a.minor) * BigInt(numerator);
  let den = BigInt(denominator);
  if (den < 0n) {
    num = -num;
    den = -den;
  }
  const negative = num < 0n;
  const abs = negative ? -num : num;
  let q = abs / den;
  const r = abs % den;
  const twice = r * 2n;
  const roundAway =
    rounding === "up" ? r > 0n
    : rounding === "down" ? false
    : rounding === "half-up" ? twice >= den
    : twice > den || (twice === den && q % 2n === 1n);
  if (roundAway) q += 1n;
  const result = Number(negative ? -q : q);
  return money(result, a.currency);
}

export function compare(a: Money, b: Money): -1 | 0 | 1 {
  assertSameCurrency(a, b);
  return a.minor < b.minor ? -1 : a.minor > b.minor ? 1 : 0;
}

export function equals(a: Money, b: Money): boolean {
  return a.currency === b.currency && a.minor === b.minor;
}

export function isZero(a: Money): boolean {
  return a.minor === 0;
}

export function isNegative(a: Money): boolean {
  return a.minor < 0;
}

export function sum(items: readonly Money[], currency: CurrencyCode): Money {
  return items.reduce((acc, m) => add(acc, m), zero(currency));
}
