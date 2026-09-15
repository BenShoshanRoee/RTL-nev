import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

describe("source hygiene", () => {
  const src = new URL("../src", import.meta.url).pathname;
  const files = walk(src).filter((f) => f.endsWith(".ts"));
  it("has no float formatting or parsing anywhere in src", () => {
    const hits = files.flatMap((f) => readFileSync(f, "utf-8").split("\n").map((l, i) => [f, i + 1, l] as const)).filter(([, , l]) => /\.toFixed\(|parseFloat\(|Number\.parseFloat|\bMath\.round\(|\/ 100\b/.test(l));
    expect(hits.map(([f, n, l]) => `${f}:${n}: ${l.trim()}`)).toEqual([]);
  });
  it("has no Hebrew or Arabic script anywhere in src (language belongs to content)", () => {
    const hits = files.filter((f) => /[֐-׿؀-ۿ]/.test(readFileSync(f, "utf-8")));
    expect(hits).toEqual([]);
  });
});
