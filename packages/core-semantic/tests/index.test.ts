import { describe, expect, it } from "vitest";
import { PACKAGE_NAME } from "../src/index";

describe("@rtl/core-semantic", () => {
  it("exports its package name", () => {
    expect(PACKAGE_NAME).toBe("@rtl/core-semantic");
  });
});
