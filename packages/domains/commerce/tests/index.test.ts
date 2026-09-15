import { describe, expect, it } from "vitest";
import { PACKAGE_NAME } from "../src/index";

describe("@rtl/domain-commerce", () => {
  it("exports its package name", () => {
    expect(PACKAGE_NAME).toBe("@rtl/domain-commerce");
  });
});
