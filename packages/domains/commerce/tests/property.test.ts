import { describe, expect, it } from "vitest";
import { checkInvariants, execute, Rng } from "@rtl/core-semantic";
import { commerceDomain } from "../src/index.js";
import { seeded } from "./helpers.js";

describe("property: random legal operation sequences", () => {
  it("applies at least 10,000 operations across seeds with every invariant holding after each", () => {
    const names = Object.keys(commerceDomain.operations).sort();
    let applied = 0;
    let rejectedCount = 0;
    const perOp: Record<string, number> = {};
    for (let seed = 0; applied < 10_000; seed++) {
      let s = seeded(1000 + seed);
      const rng = new Rng(seed, "property");
      for (let i = 0; i < 60; i++) {
        const name = names[rng.int(0, names.length)]!;
        const params = commerceDomain.operations[name]!.sample(s, rng.child(`sample:${i}`));
        if (!params) continue;
        const r = execute(commerceDomain, s, name, params, { rng: rng.child(`apply:${i}`), now: () => 0 });
        if (!r.ok) {
          rejectedCount++;
          expect(r.violations, `${name}: ${r.reason}`).toBeUndefined();
          continue;
        }
        applied++;
        perOp[name] = (perOp[name] ?? 0) + 1;
        const v = checkInvariants(commerceDomain, r.state);
        expect(v, `after ${name} at step ${i} seed ${seed}`).toEqual([]);
        s = r.state;
      }
      expect(seed).toBeLessThan(2000);
    }
    expect(applied).toBeGreaterThanOrEqual(10_000);
    // every operation was exercised at least once
    for (const n of names) expect(perOp[n] ?? 0, `operation ${n} never applied`).toBeGreaterThan(0);
    expect(rejectedCount).toBeGreaterThanOrEqual(0);
  }, 120_000);
});
