/**
 * The identical conformance suite commerce runs. If a future change to core-semantic absorbs
 * a commerce assumption, this file fails and the core has leaked.
 */
import { describe, expect, it } from "vitest";
import { conformanceChecks } from "@rtl/core-semantic";
import { insuranceDomain } from "../src/index.js";

describe("insurance stub passes the core conformance suite", () => {
  for (const c of conformanceChecks(insuranceDomain, { seed: 3, sequences: 30, length: 15 })) {
    it(c.id, () => {
      expect(c.ok, c.detail).toBe(true);
    });
  }
});
