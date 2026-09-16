/**
 * Insurance stub: the permanent leak detector for core-semantic. Deliberately thin. Its only
 * job is to pass the identical conformance suite commerce passes; if a change to the core
 * ever makes this fail, the core has absorbed a commerce assumption.
 *
 * Same rules as any domain: canonical JSON state, integers only, records keyed by id, one
 * currency, no language (resource keys), explicit time in state.
 */

import { money, type DomainDefinition, type Invariant, type Money, type OperationDefinition, type Rng } from "@rtl/core-semantic";

export type PolicyKind = "car" | "home" | "health";
export type PolicyStatus = "active" | "lapsed";
export type ClaimStatus = "filed" | "under_review" | "approved" | "rejected" | "paid";

export type Policy = { id: string; kind: PolicyKind; status: PolicyStatus; coverage: Money; deductible: Money; beneficiaryIds: string[]; startAt: number };
export type Claim = { id: string; policyId: string; amount: Money; status: ClaimStatus; documentIds: string[]; filedAt: number };
export type Premium = { policyId: string; amount: Money; periodDays: number; nextDueAt: number };
export type Beneficiary = { id: string; policyId: string; nameKey: string; relationKey: string; share: number };
export type Document = { id: string; claimId: string; kindKey: string; uploadedAt: number };

export type InsuranceState = {
  config: { currency: "ILS" };
  counters: { claim: number; document: number };
  policies: Record<string, Policy>;
  claims: Record<string, Claim>;
  premiums: Record<string, Premium>;
  beneficiaries: Record<string, Beneficiary>;
  documents: Record<string, Document>;
  session: { now: number; lastStatusCheck: { claimId: string; status: ClaimStatus } | null };
};

const DAY = 86_400_000;
const SEED_NOW = 1_767_603_600_000;
const KINDS: readonly PolicyKind[] = ["car", "home", "health"];
const RELATIONS = ["relation.spouse", "relation.child", "relation.parent", "relation.other"] as const;
const DOC_KINDS = ["document.kind.invoice", "document.kind.photo", "document.kind.police_report", "document.kind.medical"] as const;
const ok = { ok: true } as const;
const no = (reason: string) => ({ ok: false as const, reason });

export function seedInsurance(rng: Rng): InsuranceState {
  const r = rng.child("insurance");
  const policies: Record<string, Policy> = {};
  const premiums: Record<string, Premium> = {};
  const beneficiaries: Record<string, Beneficiary> = {};
  let bSeq = 0;
  const n = r.int(2, 5);
  for (let i = 1; i <= n; i++) {
    const id = `pol${String(i).padStart(3, "0")}`;
    const kind = r.pick(KINDS);
    const coverage = money(r.int(5_000, 200_000) * 100, "ILS");
    const shares = r.pick([[100], [50, 50], [60, 40], [70, 30]]);
    const beneficiaryIds: string[] = [];
    for (const share of shares) {
      const bid = `ben${String(++bSeq).padStart(3, "0")}`;
      beneficiaryIds.push(bid);
      beneficiaries[bid] = { id: bid, policyId: id, nameKey: `person.${bid}`, relationKey: r.pick(RELATIONS), share };
    }
    policies[id] = { id, kind, status: r.bool(0.8) ? "active" : "lapsed", coverage, deductible: money(r.int(0, 1_000) * 100, "ILS"), beneficiaryIds, startAt: SEED_NOW - r.int(30, 900) * DAY };
    premiums[id] = { policyId: id, amount: money(r.int(80, 900) * 100, "ILS"), periodDays: r.pick([30, 90, 365]), nextDueAt: SEED_NOW + r.int(1, 60) * DAY };
  }
  return { config: { currency: "ILS" }, counters: { claim: 0, document: 0 }, policies, claims: {}, premiums, beneficiaries, documents: {}, session: { now: SEED_NOW, lastStatusCheck: null } };
}

const fileClaim: OperationDefinition<InsuranceState, { policyId: string; amount: Money }> = {
  name: "fileClaim",
  description: "open a claim against an active policy, up to its coverage",
  params: { policyId: { kind: "ref", entity: "policy" }, amount: "money" },
  precondition: (s, p) => {
    const pol = s.policies[p.policyId];
    if (!pol) return no(`no policy ${p.policyId}`);
    if (pol.status !== "active") return no("policy is not active");
    if (p.amount.currency !== s.config.currency) return no("wrong currency");
    if (p.amount.minor <= 0) return no("amount must be positive");
    if (p.amount.minor > pol.coverage.minor) return no("amount exceeds coverage");
    return ok;
  },
  apply: (s, p) => {
    const counters = { ...s.counters, claim: s.counters.claim + 1 };
    const id = `clm${String(counters.claim).padStart(4, "0")}`;
    return { ...s, counters, claims: { ...s.claims, [id]: { id, policyId: p.policyId, amount: p.amount, status: "filed", documentIds: [], filedAt: s.session.now } } };
  },
  sample: (s, rng) => {
    const active = Object.keys(s.policies).sort().filter((id) => s.policies[id]!.status === "active");
    if (!active.length) return null;
    const policyId = rng.pick(active);
    return { policyId, amount: money(rng.int(1, s.policies[policyId]!.coverage.minor + 1), s.config.currency) };
  },
};

const uploadDocument: OperationDefinition<InsuranceState, { claimId: string; kindKey: string }> = {
  name: "uploadDocument",
  description: "attach a document to a claim that is not yet decided",
  params: { claimId: { kind: "ref", entity: "claim" }, kindKey: { kind: "enum", values: DOC_KINDS } },
  precondition: (s, p) => {
    const c = s.claims[p.claimId];
    if (!c) return no(`no claim ${p.claimId}`);
    if (c.status === "rejected" || c.status === "paid") return no("claim is closed");
    return ok;
  },
  apply: (s, p) => {
    const counters = { ...s.counters, document: s.counters.document + 1 };
    const id = `doc${String(counters.document).padStart(4, "0")}`;
    const claim = s.claims[p.claimId]!;
    return { ...s, counters, documents: { ...s.documents, [id]: { id, claimId: claim.id, kindKey: p.kindKey, uploadedAt: s.session.now } }, claims: { ...s.claims, [claim.id]: { ...claim, documentIds: [...claim.documentIds, id] } } };
  },
  sample: (s, rng) => {
    const open = Object.keys(s.claims).sort().filter((id) => !["rejected", "paid"].includes(s.claims[id]!.status));
    return open.length ? { claimId: rng.pick(open), kindKey: rng.pick(DOC_KINDS) } : null;
  },
};

const checkStatus: OperationDefinition<InsuranceState, { claimId: string }> = {
  name: "checkStatus",
  description: "look up a claim's status; recorded in session so a task can assert what was checked",
  params: { claimId: { kind: "ref", entity: "claim" } },
  precondition: (s, p) => (s.claims[p.claimId] ? ok : no(`no claim ${p.claimId}`)),
  apply: (s, p) => ({ ...s, session: { ...s.session, lastStatusCheck: { claimId: p.claimId, status: s.claims[p.claimId]!.status } } }),
  sample: (s, rng) => { const ids = Object.keys(s.claims).sort(); return ids.length ? { claimId: rng.pick(ids) } : null; },
};

const updateBeneficiary: OperationDefinition<InsuranceState, { beneficiaryId: string; share: number }> = {
  name: "updateBeneficiary",
  description: "change a beneficiary's share; a policy's shares never exceed 100 percent",
  params: { beneficiaryId: { kind: "ref", entity: "beneficiary" }, share: "integer" },
  precondition: (s, p) => {
    const b = s.beneficiaries[p.beneficiaryId];
    if (!b) return no(`no beneficiary ${p.beneficiaryId}`);
    if (p.share < 0 || p.share > 100) return no("share must be between 0 and 100");
    const others = Object.values(s.beneficiaries).filter((x) => x.policyId === b.policyId && x.id !== b.id).reduce((n, x) => n + x.share, 0);
    if (others + p.share > 100) return no(`shares for the policy would exceed 100 (others hold ${others})`);
    return ok;
  },
  apply: (s, p) => ({ ...s, beneficiaries: { ...s.beneficiaries, [p.beneficiaryId]: { ...s.beneficiaries[p.beneficiaryId]!, share: p.share } } }),
  sample: (s, rng) => {
    const ids = Object.keys(s.beneficiaries).sort();
    if (!ids.length) return null;
    const beneficiaryId = rng.pick(ids);
    const b = s.beneficiaries[beneficiaryId]!;
    const others = Object.values(s.beneficiaries).filter((x) => x.policyId === b.policyId && x.id !== b.id).reduce((n, x) => n + x.share, 0);
    return { beneficiaryId, share: rng.int(0, 100 - others + 1) };
  },
};

const invariants: readonly Invariant<InsuranceState>[] = [
  { id: "claims-within-coverage", description: "every claim is on an existing policy and within its coverage", check: (s) => { for (const c of Object.values(s.claims)) { const p = s.policies[c.policyId]; if (!p) return { ok: false, detail: `${c.id} -> missing policy` }; if (c.amount.minor <= 0 || c.amount.minor > p.coverage.minor) return { ok: false, detail: `${c.id} amount ${c.amount.minor} vs coverage ${p.coverage.minor}` }; } return ok; } },
  { id: "documents-belong-to-claims", description: "documents and claims reference each other consistently", check: (s) => { for (const d of Object.values(s.documents)) { const c = s.claims[d.claimId]; if (!c || !c.documentIds.includes(d.id)) return { ok: false, detail: `${d.id} orphaned` }; } for (const c of Object.values(s.claims)) for (const id of c.documentIds) if (s.documents[id]?.claimId !== c.id) return { ok: false, detail: `${c.id} lists ${id}` }; return ok; } },
  { id: "beneficiary-shares", description: "per policy, shares are 0..100 each and sum to at most 100; beneficiary lists match", check: (s) => { for (const p of Object.values(s.policies)) { let sum = 0; for (const id of p.beneficiaryIds) { const b = s.beneficiaries[id]; if (!b || b.policyId !== p.id) return { ok: false, detail: `${p.id} lists ${id}` }; if (b.share < 0 || b.share > 100) return { ok: false, detail: `${id} share ${b.share}` }; sum += b.share; } if (sum > 100) return { ok: false, detail: `${p.id} shares sum to ${sum}` }; } return ok; } },
  { id: "premiums-per-policy", description: "every policy has a premium and every premium a policy", check: (s) => { for (const id of Object.keys(s.policies)) if (!s.premiums[id]) return { ok: false, detail: `${id} has no premium` }; for (const pr of Object.values(s.premiums)) if (!s.policies[pr.policyId]) return { ok: false, detail: `premium for missing ${pr.policyId}` }; return ok; } },
  { id: "single-currency", description: "every money value is in config.currency", check: (s) => { const all = [...Object.values(s.policies).flatMap((p) => [p.coverage, p.deductible]), ...Object.values(s.claims).map((c) => c.amount), ...Object.values(s.premiums).map((p) => p.amount)]; const bad = all.find((m) => m.currency !== s.config.currency); return bad ? { ok: false, detail: `found ${bad.currency}` } : ok; } },
  { id: "counters-monotonic", description: "counters cover issued ids", check: (s) => (s.counters.claim < Object.keys(s.claims).length || s.counters.document < Object.keys(s.documents).length ? { ok: false, detail: "counter behind" } : ok) },
];

export const insuranceDomain: DomainDefinition<InsuranceState> = {
  id: "insurance-stub",
  version: "0.1.0",
  entities: {
    policy: { key: "id", fields: { id: "string", kind: { kind: "enum", values: KINDS }, status: { kind: "enum", values: ["active", "lapsed"] }, coverage: "money", deductible: "money", beneficiaryIds: { kind: "list", of: { kind: "ref", entity: "beneficiary" } }, startAt: "integer" } },
    claim: { key: "id", fields: { id: "string", policyId: { kind: "ref", entity: "policy" }, amount: "money", status: { kind: "enum", values: ["filed", "under_review", "approved", "rejected", "paid"] }, documentIds: { kind: "list", of: { kind: "ref", entity: "document" } }, filedAt: "integer" } },
    premium: { key: "policyId", fields: { policyId: { kind: "ref", entity: "policy" }, amount: "money", periodDays: "integer", nextDueAt: "integer" } },
    beneficiary: { key: "id", fields: { id: "string", policyId: { kind: "ref", entity: "policy" }, nameKey: "string", relationKey: "string", share: "integer" } },
    document: { key: "id", fields: { id: "string", claimId: { kind: "ref", entity: "claim" }, kindKey: "string", uploadedAt: "integer" } },
  },
  operations: { fileClaim, uploadDocument, checkStatus, updateBeneficiary },
  invariants,
  seedState: (rng) => seedInsurance(rng),
};
