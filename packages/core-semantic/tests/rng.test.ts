import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Rng, childSeed, seedFromString, sha256Hex } from "../src/rng";

type Parity = {
  sha256: Record<string, string>;
  child_seeds: { root: number; namespaces: string[]; seeds: number[] };
  streams: Array<{
    seed: number;
    next32: number[];
    float: number[];
    int_0_1000: number[];
    shuffle_10: number[];
    weighted: number[];
  }>;
};
const parity: Parity = JSON.parse(
  readFileSync(new URL("./fixtures/rng-parity.json", import.meta.url), "utf-8"),
);

describe("sha256Hex", () => {
  it("matches known vectors, including UTF-8 input", () => {
    expect(sha256Hex("")).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    for (const [input, hex] of Object.entries(parity.sha256)) expect(sha256Hex(input)).toBe(hex);
  });
});

describe("childSeed", () => {
  it("reproduces the 1000-namespace sequence from the cross-language fixture", () => {
    const { root, namespaces, seeds } = parity.child_seeds;
    expect(namespaces.length).toBe(1000);
    expect(namespaces.map((ns) => childSeed(root, ns))).toEqual(seeds);
  });
  it("is a uint32 and depends on both root and namespace", () => {
    const a = childSeed(1, "catalog");
    expect(Number.isInteger(a) && a >= 0 && a < 2 ** 32).toBe(true);
    expect(childSeed(2, "catalog")).not.toBe(a);
    expect(childSeed(1, "copy")).not.toBe(a);
  });
  it("rejects seeds outside uint32", () => {
    expect(() => childSeed(-1, "x")).toThrow();
    expect(() => childSeed(2 ** 32, "x")).toThrow();
    expect(() => childSeed(1.5, "x")).toThrow();
  });
});

describe("Rng streams", () => {
  it("reproduce the cross-language fixture for every seed", () => {
    for (const s of parity.streams) {
      const r = new Rng(s.seed);
      expect(s.next32.map(() => r.next32())).toEqual(s.next32);
      const r2 = new Rng(s.seed);
      expect(s.float.map(() => r2.float())).toEqual(s.float);
      const r3 = new Rng(s.seed);
      expect(s.int_0_1000.map(() => r3.int(0, 1000))).toEqual(s.int_0_1000);
      const r4 = new Rng(s.seed);
      expect(r4.shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])).toEqual(s.shuffle_10);
      const r5 = new Rng(s.seed);
      expect(s.weighted.map(() => r5.weighted([0, 1, 2], [0.5, 0.3, 0.2]))).toEqual(s.weighted);
    }
  });
  it("same seed, same output, for three seeds", () => {
    for (const seed of [0, 12345, 4294967295]) {
      const a = new Rng(seed);
      const b = new Rng(seed);
      expect(Array.from({ length: 100 }, () => a.next32())).toEqual(
        Array.from({ length: 100 }, () => b.next32()),
      );
    }
  });
  it("different seed, different output", () => {
    const a = new Rng(1);
    const b = new Rng(2);
    expect(Array.from({ length: 8 }, () => a.next32())).not.toEqual(
      Array.from({ length: 8 }, () => b.next32()),
    );
  });
  it("isolation: extra draws in namespace A leave namespace B byte-identical", () => {
    const root = new Rng(777);
    const b1 = Array.from({ length: 50 }, () => root.child("B").next32());
    const a = root.child("A");
    for (let i = 0; i < 1000; i++) a.next32();
    const b2 = Array.from({ length: 50 }, () => root.child("B").next32());
    expect(b2).toEqual(b1);
  });
  it("int is in range and unbiased at the edges; float in [0,1)", () => {
    const r = new Rng(9);
    const seen = new Set<number>();
    for (let i = 0; i < 5000; i++) {
      const v = r.int(-3, 3);
      expect(v >= -3 && v < 3 && Number.isInteger(v)).toBe(true);
      seen.add(v);
      const f = r.float();
      expect(f >= 0 && f < 1).toBe(true);
    }
    expect(seen.size).toBe(6);
    expect(() => r.int(5, 5)).toThrow();
  });
  it("shuffle returns a permutation and leaves the input untouched", () => {
    const input = [1, 2, 3, 4, 5];
    const out = new Rng(3).shuffle(input);
    expect(input).toEqual([1, 2, 3, 4, 5]);
    expect([...out].sort()).toEqual([1, 2, 3, 4, 5]);
  });
  it("order independence: seeds derived per item do not depend on iteration order", () => {
    const root = 42;
    const ids = ["c", "a", "b"];
    const forward = Object.fromEntries(ids.map((id) => [id, new Rng(childSeed(root, id)).next32()]));
    const reversed = Object.fromEntries(
      [...ids].reverse().map((id) => [id, new Rng(childSeed(root, id)).next32()]),
    );
    expect(reversed).toEqual(forward);
  });
  it("seedFromString is stable", () => {
    expect(seedFromString("run-2026-09-15")).toBe(seedFromString("run-2026-09-15"));
    expect(seedFromString("a")).not.toBe(seedFromString("b"));
  });
});
