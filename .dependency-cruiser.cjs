/** Architectural boundaries enforced in CI. See CLAUDE.md non-negotiables. */
module.exports = {
  forbidden: [
    {
      name: "core-semantic-must-not-import-domains",
      severity: "error",
      comment:
        "packages/core-semantic is domain-agnostic. It must never import from packages/domains/*.",
      from: { path: "^packages/core-semantic" },
      to: { path: "^packages/domains" },
    },
    {
      name: "domains-must-not-import-each-other",
      severity: "error",
      comment: "A domain implementation may depend on core-semantic only, never on a sibling domain.",
      from: { path: "^packages/domains/([^/]+)" },
      to: { path: "^packages/domains/(?!$1/)" },
    },
    {
      name: "no-circular",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    {
      name: "not-to-unresolvable",
      severity: "error",
      comment: "An import that does not resolve is either a typo or an undeclared package dependency.",
      from: {},
      to: { couldNotResolve: true },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    exclude: { path: "node_modules|/dist/" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.base.json" },
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default", "types"],
      mainFields: ["module", "main", "types"],
    },
  },
};
