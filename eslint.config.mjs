// Workspace ESLint. Two jobs: (1) the standard recommended rules for our own TypeScript under
// packages/; (2) the randomness ban, which is the CI-enforced non-negotiable from CLAUDE.md.
// Upstream simulator code is linted for the ban only, with a dated exemption (see below).
import js from "@eslint/js";
import tseslint from "typescript-eslint";

const NO_ENTROPY = [
  "error",
  { object: "Math", property: "random", message: "Use Rng from @rtl/core-semantic (rng.ts). Math.random() breaks reproducibility." },
  { object: "crypto", property: "getRandomValues", message: "Use Rng from @rtl/core-semantic. Unseeded entropy is forbidden." },
  { object: "crypto", property: "randomUUID", message: "Derive ids from the seeded Rng, never from random UUIDs." },
];

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**", "**/dist/**", "**/.vite/**", "refs/**", "docs/business/**",
      "sim/bench_env/**", "sim/scripts/**", "sim/public/**", "sim/docs/**", "sim/.nginx/**",
      "**/*.d.ts", "**/*.mjs", "**/*.cjs", "sim/eslint.config.js",
    ],
  },
  // Every TypeScript file is parsed by typescript-eslint, whichever rule blocks apply.
  { files: ["**/*.{ts,tsx}"], languageOptions: { parser: tseslint.parser } },
  // Our TypeScript: full recommended rule sets.
  {
    files: ["packages/**/*.ts", "packages/**/*.tsx"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
  },
  // The randomness ban: our packages and our storefront.
  {
    files: ["packages/**/*.{ts,tsx}", "sim/apps/Storefront/**/*.{ts,tsx}", "sim/apps/Reference*/**/*.{ts,tsx}"],
    rules: { "no-restricted-properties": NO_ENTROPY },
  },
  // Generation paths must not read the wall clock either; the clock is injected.
  {
    files: ["packages/domains/**/src/**/*.ts", "packages/surface-gen/src/**/*.ts", "packages/pathology/src/**/*.ts"],
    rules: {
      "no-restricted-properties": [
        ...NO_ENTROPY,
        { object: "Date", property: "now", message: "Inject a clock; generated data must not depend on wall time." },
      ],
    },
  },
  // core-semantic is domain-agnostic: no commerce or insurance vocabulary in identifiers or
  // string literals. The insurance stub (2.1.3) is the runtime check; this is the static one.
  // Word boundaries respect camelCase: cartTotal and orders fail, production and ordered pass.
  {
    files: ["packages/core-semantic/src/**/*.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Identifier[name=/(^|[^a-zA-Z])(product|Product|PRODUCT|cart|Cart|CART|price|Price|PRICE|checkout|Checkout|CHECKOUT|order|Order|ORDER|coupon|Coupon|COUPON|sku|Sku|SKU|customer|Customer|CUSTOMER|inventory|Inventory|INVENTORY|shipping|Shipping|SHIPPING|payment|Payment|PAYMENT|catalog|Catalog|CATALOG|policy|Policy|POLICY|claim|Claim|CLAIM|premium|Premium|PREMIUM|beneficiary|Beneficiary|BENEFICIARY)s?($|[^a-z])/]",
          message: "no domain vocabulary in core-semantic: this word belongs to a domain package",
        },
        {
          selector: "Literal[value=/(^|[^a-zA-Z])(product|Product|PRODUCT|cart|Cart|CART|price|Price|PRICE|checkout|Checkout|CHECKOUT|order|Order|ORDER|coupon|Coupon|COUPON|sku|Sku|SKU|customer|Customer|CUSTOMER|inventory|Inventory|INVENTORY|shipping|Shipping|SHIPPING|payment|Payment|PAYMENT|catalog|Catalog|CATALOG|policy|Policy|POLICY|claim|Claim|CLAIM|premium|Premium|PREMIUM|beneficiary|Beneficiary|BENEFICIARY)s?($|[^a-z])/]",
          message: "no domain vocabulary in core-semantic: this word belongs to a domain package",
        },
      ],
    },
  },
  // The one legitimate home of entropy primitives.
  { files: ["packages/core-semantic/src/rng.ts"], rules: { "no-restricted-properties": "off" } },
  // Upstream simulator code (sim/os, sim/system, the two reference apps, upstream tests and
  // build config) is parsed but only the ban is applied, and the ban is exempt here because
  // upstream ships 18 Math.random() calls. Sub-chunk 3.3.2 routes them through the seeded
  // Rng and deletes this block. Do not add paths to it.
  {
    files: ["sim/**/*.{ts,tsx}"],
    ignores: ["sim/apps/Storefront/**", "sim/apps/Reference*/**"],
    // Upstream files carry `eslint-disable react-hooks/...` comments for a plugin this
    // workspace does not install. The no-op stub lets those directives resolve; it lints
    // nothing. 3.3.2 decides whether the plugin is adopted for our own components.
    plugins: { "react-hooks": { rules: { "exhaustive-deps": { create: () => ({}) }, "rules-of-hooks": { create: () => ({}) } } } },
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: { "no-restricted-properties": "off" },
  },
);
