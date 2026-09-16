import { describe, expect, it } from "vitest";
import { Rng, execute, money, type JsonObject } from "@rtl/core-semantic";
import { insuranceDomain, seedInsurance, type InsuranceState } from "../src/index.js";

const ctx = { rng: new Rng(1), now: () => 0 };
const run = (s: InsuranceState, op: string, p: JsonObject) => execute(insuranceDomain, s, op, p, ctx);

describe("insurance stub behaviour", () => {
  it("files a claim within coverage, uploads a document, and records a status check", () => {
    let s = seedInsurance(new Rng(4, "seed"));
    const policy = Object.values(s.policies).find((p) => p.status === "active")!;
    const r = run(s, "fileClaim", { policyId: policy.id, amount: money(Math.min(100_00, policy.coverage.minor), s.config.currency) });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    s = r.state;
    const claim = Object.values(s.claims).sort((a, b) => b.filedAt - a.filedAt)[0]!;
    expect(claim.policyId).toBe(policy.id);
    const d = run(s, "uploadDocument", { claimId: claim.id, kindKey: "document.kind.invoice" });
    expect(d.ok).toBe(true);
    if (!d.ok) return;
    s = d.state;
    expect(s.claims[claim.id]!.documentIds.length).toBe(1);
    const c = run(s, "checkStatus", { claimId: claim.id });
    expect(c.ok).toBe(true);
    if (!c.ok) return;
    expect(c.state.session.lastStatusCheck).toEqual({ claimId: claim.id, status: "filed" });
  });
  it("rejects a claim above coverage, on a lapsed policy, and beneficiary shares above 100", () => {
    const s = seedInsurance(new Rng(4, "seed"));
    const policy = Object.values(s.policies).find((p) => p.status === "active")!;
    const over = run(s, "fileClaim", { policyId: policy.id, amount: money(policy.coverage.minor + 1, s.config.currency) });
    expect(over.ok).toBe(false);
    const lapsed = Object.values(s.policies).find((p) => p.status === "lapsed");
    if (lapsed) expect(run(s, "fileClaim", { policyId: lapsed.id, amount: money(1, s.config.currency) }).ok).toBe(false);
    const b = Object.values(s.beneficiaries)[0]!;
    expect(run(s, "updateBeneficiary", { beneficiaryId: b.id, share: 101 }).ok).toBe(false);
  });
  it("mentions nothing from commerce", () => {
    const names = [...Object.keys(insuranceDomain.entities), ...Object.keys(insuranceDomain.operations)].join(" ");
    expect(names).not.toMatch(/cart|product|checkout|coupon|order/i);
  });
});
