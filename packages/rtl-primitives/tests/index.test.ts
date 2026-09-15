import { describe, expect, it } from "vitest";
import { PACKAGE_NAME } from "../src/index";

describe("@rtl/rtl-primitives", () => {
  it("exports its package name", () => {
    expect(PACKAGE_NAME).toBe("@rtl/rtl-primitives");
  });
});
