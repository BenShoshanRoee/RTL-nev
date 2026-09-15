import { describe, expect, it } from "vitest";
import { PACKAGE_NAME } from "../src/index.js";

describe("@rtl/surface-gen", () => {
  it("exports its package name", () => {
    expect(PACKAGE_NAME).toBe("@rtl/surface-gen");
  });
});
