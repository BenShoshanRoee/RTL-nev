import { describe, expect, it } from "vitest";
import { conformanceChecks } from "@rtl/core-semantic";
import { commerceDomain } from "../src/index.js";

describe("commerce passes the core conformance suite", () => {
  for (const c of conformanceChecks(commerceDomain, { seed: 3, sequences: 30, length: 15 })) {
    it(c.id, () => {
      expect(c.ok, c.detail).toBe(true);
    });
  }
});
