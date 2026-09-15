import { describe, expect, it } from "vitest";
import { conformanceChecks } from "../src/conformance/suite.js";
import type { DomainDefinition } from "../src/domain.js";
import { checkInvariants } from "../src/invariant.js";
import { add, money, type Money } from "../src/money.js";
import { execute } from "../src/operation.js";
import { Rng } from "../src/rng.js";
import { hashState } from "../src/state.js";

/** A deliberately neutral toy domain: labelled slots with a level, a counter, and funds. */
type Slot = { id: string; label: string; level: number };
type ToyState = { slots: Record<string, Slot>; counter: number; funds: Money };

const toy: DomainDefinition<ToyState> = {
  id: "toy",
  version: "1.0.0",
  entities: {
    slot: { key: "id", fields: { id: "string", label: "string", level: "integer" } },
  },
  operations: {
    create: {
      name: "create",
      description: "add a slot at level 0; id derives from the counter",
      params: { label: "string" },
      precondition: (s, p) => (typeof p.label === "string" && p.label.length > 0 ? { ok: true } : { ok: false, reason: "label required" }),
      apply: (s, p) => {
        const id = `s${s.counter + 1}`;
        return { ...s, counter: s.counter + 1, slots: { ...s.slots, [id]: { id, label: p.label as string, level: 0 } } };
      },
      sample: (s, rng) => ({ label: rng.pick(["alef", "bet", "gimel"]) }),
    },
    raise: {
      name: "raise",
      description: "raise a slot's level by 1..3, never above 10",
      params: { id: "string", by: "integer" },
      precondition: (s, p) => {
        const slot = s.slots[p.id as string];
        if (!slot) return { ok: false, reason: "no such slot" };
        if (slot.level + (p.by as number) > 10) return { ok: false, reason: "level cap" };
        return { ok: true };
      },
      apply: (s, p) => {
        const slot = s.slots[p.id as string] as Slot;
        return { ...s, slots: { ...s.slots, [slot.id]: { ...slot, level: slot.level + (p.by as number) } } };
      },
      sample: (s, rng) => {
        const ids = Object.keys(s.slots).sort();
        if (ids.length === 0) return null;
        return { id: rng.pick(ids), by: rng.int(1, 4) };
      },
    },
    deposit: {
      name: "deposit",
      description: "add funds",
      params: { minor: "integer" },
      precondition: (s, p) => ((p.minor as number) > 0 ? { ok: true } : { ok: false, reason: "must be positive" }),
      apply: (s, p) => ({ ...s, funds: add(s.funds, money(p.minor as number, s.funds.currency)) }),
      sample: (s, rng) => ({ minor: rng.int(1, 1000) }),
    },
  },
  invariants: [
    { id: "level-range", description: "0 <= level <= 10", check: (s) => { const bad = Object.values(s.slots).find((x) => x.level < 0 || x.level > 10); return bad ? { ok: false, detail: `slot ${bad.id} level ${bad.level}` } : { ok: true }; } },
    { id: "counter-covers-slots", description: "counter >= number of slots", check: (s) => (s.counter >= Object.keys(s.slots).length ? { ok: true } : { ok: false, detail: "counter behind" }) },
    { id: "funds-non-negative", description: "funds never negative", check: (s) => (s.funds.minor >= 0 ? { ok: true } : { ok: false, detail: "negative funds" }) },
  ],
  seedState: (rng) => {
    const n = rng.int(1, 4);
    const slots: Record<string, Slot> = {};
    for (let i = 1; i <= n; i++) slots[`s${i}`] = { id: `s${i}`, label: rng.pick(["alef", "bet"]), level: rng.int(0, 5) };
    return { slots, counter: n, funds: money(rng.int(0, 500), "ILS") };
  },
};

describe("conformance suite on the toy domain", () => {
  const results = conformanceChecks(toy, { seed: 7, sequences: 10, length: 12 });
  it("produces at least eight named checks", () => {
    expect(results.length).toBeGreaterThanOrEqual(8);
  });
  for (const r of results) {
    it(r.id, () => {
      expect(r.ok, r.detail).toBe(true);
    });
  }
});

describe("execute", () => {
  const ctx = { rng: new Rng(1), now: () => 0 };
  it("applies a legal operation, returning new state plus a trace with hashes and changes", () => {
    const s0 = toy.seedState(new Rng(3));
    const r = execute(toy, s0, "create", { label: "dalet" }, ctx);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.state.counter).toBe(s0.counter + 1);
    expect(r.trace.op).toBe("create");
    expect(r.trace.beforeHash).toBe(hashState(s0));
    expect(r.trace.afterHash).toBe(hashState(r.state));
    expect(r.trace.changes.changes.length).toBeGreaterThan(0);
  });
  it("rejects a failed precondition and an unknown operation without touching state", () => {
    const s0 = toy.seedState(new Rng(3));
    const h = hashState(s0);
    const r = execute(toy, s0, "deposit", { minor: -5 }, ctx);
    expect(r.ok).toBe(false);
    expect(hashState(s0)).toBe(h);
    expect(execute(toy, s0, "nope", {}, ctx).ok).toBe(false);
  });
  it("rejects params of the wrong type before running the operation", () => {
    const s0 = toy.seedState(new Rng(3));
    const r = execute(toy, s0, "deposit", { minor: "ten" }, ctx);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toMatch(/minor/);
  });
  it("rejects an operation whose result violates an invariant, leaving state unchanged", () => {
    const broken: DomainDefinition<ToyState> = {
      ...toy,
      operations: {
        ...toy.operations,
        drain: {
          name: "drain", description: "bug: takes more than there is", params: {},
          precondition: () => ({ ok: true }),
          apply: (s) => ({ ...s, funds: money(-1, s.funds.currency) }),
          sample: () => ({}),
        },
      },
    };
    const s0 = broken.seedState(new Rng(3));
    const r = execute(broken, s0, "drain", {}, ctx);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.violations?.map((v) => v.id)).toEqual(["funds-non-negative"]);
    expect(checkInvariants(broken, s0)).toEqual([]);
  });
  it("throws if apply mutates its input", () => {
    const mutating: DomainDefinition<ToyState> = {
      ...toy,
      operations: {
        bump: {
          name: "bump", description: "bug: mutates", params: {},
          precondition: () => ({ ok: true }),
          apply: (s) => { (s as ToyState).counter += 1; return s as ToyState; },
          sample: () => ({}),
        },
      },
    };
    expect(() => execute(mutating, mutating.seedState(new Rng(3)), "bump", {}, ctx)).toThrow();
  });
});
