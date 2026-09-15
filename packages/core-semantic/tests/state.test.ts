import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  canonicalJson,
  diff,
  fork,
  getPath,
  hashState,
  isEmpty,
  patch,
  snapshot,
  unchanged,
  type Changeset,
  type JsonValue,
} from "../src/state";

type Parity = {
  cases: Array<{ name: string; before: JsonValue; after: JsonValue; changeset: Changeset; hash_before: string; hash_after: string; canonical_before: string }>;
};
const parity: Parity = JSON.parse(
  readFileSync(new URL("./fixtures/state-parity.json", import.meta.url), "utf-8"),
);

describe("canonicalJson / hashState", () => {
  it("sorts keys, keeps unicode, and rejects floats", () => {
    expect(canonicalJson({ b: 1, a: { d: "שלום", c: [1, 2] } })).toBe('{"a":{"c":[1,2],"d":"שלום"},"b":1}');
    expect(() => canonicalJson({ x: 1.5 })).toThrow();
    expect(() => canonicalJson({ x: Number.NaN })).toThrow();
    expect(hashState({ a: 1 })).toMatch(/^[0-9a-f]{64}$/);
    expect(hashState({ a: 1, b: 2 })).toBe(hashState({ b: 2, a: 1 }));
  });
  it("matches the cross-language fixture for every case", () => {
    expect(parity.cases.length).toBeGreaterThanOrEqual(8);
    for (const c of parity.cases) {
      expect(canonicalJson(c.before), c.name).toBe(c.canonical_before);
      expect(hashState(c.before), c.name).toBe(c.hash_before);
      expect(hashState(c.after), c.name).toBe(c.hash_after);
    }
  });
});

describe("diff / patch", () => {
  it("returns an empty changeset for identical states", () => {
    const s = { a: { b: [1, 2, { c: "x" }] }, n: null };
    expect(isEmpty(diff(s, s))).toBe(true);
    expect(isEmpty(diff(s, snapshot(s)))).toBe(true);
    expect(diff(s, s).changes).toEqual([]);
  });
  it("reports leaf-level added / removed / changed entries with sorted paths", () => {
    const cs = diff({ a: 1, b: { x: 1, y: 2 }, l: [1, 2] }, { a: 2, b: { x: 1, z: 3 }, l: [1, 2, 3] });
    expect(cs.changes).toEqual([
      { path: ["a"], kind: "changed", before: 1, after: 2 },
      { path: ["b", "y"], kind: "removed", before: 2 },
      { path: ["b", "z"], kind: "added", after: 3 },
      { path: ["l", 2], kind: "added", after: 3 },
    ]);
  });
  it("treats a type change as a single changed leaf", () => {
    expect(diff({ a: { x: 1 } }, { a: [1] }).changes).toEqual([{ path: ["a"], kind: "changed", before: { x: 1 }, after: [1] }]);
  });
  it("patch(before, diff(before, after)) reproduces after exactly, for the fixture and beyond", () => {
    for (const c of parity.cases) {
      expect(diff(c.before, c.after), c.name).toEqual(c.changeset);
      expect(patch(c.before, c.changeset), c.name).toEqual(c.after);
    }
    const before = { k: { "1": { v: 1 }, "2": { v: 2 } }, arr: [1, [2, 3]] };
    const after = { k: { "2": { v: 5 }, "3": { v: 3 } }, arr: [1, [2]], extra: true };
    expect(patch(before, diff(before, after))).toEqual(after);
  });
  it("fork gives an independent copy; getPath and unchanged read subtrees", () => {
    const s = { a: { b: 1 } };
    const f = fork(s);
    f.a.b = 2;
    expect(s.a.b).toBe(1);
    expect(getPath(s, ["a", "b"])).toBe(1);
    expect(getPath(s, ["a", "zz"])).toBeUndefined();
    const before = { cart_like: { n: 1 }, other: { n: 1 } };
    const after = { cart_like: { n: 2 }, other: { n: 1 } };
    expect(unchanged(before, after, [["other"]])).toEqual([]);
    expect(unchanged(before, after, [["cart_like"]]).map((c) => c.path)).toEqual([["cart_like", "n"]]);
  });
});
