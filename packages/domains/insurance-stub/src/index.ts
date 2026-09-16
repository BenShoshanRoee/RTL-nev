export const PACKAGE_NAME = "@rtl/domain-insurance-stub" as const;

export { insuranceDomain, seedInsurance } from "./domain.js";
export type { Beneficiary, Claim, Document, InsuranceState, Policy, Premium } from "./domain.js";
