import type { OperationDefinition } from "@rtl/core-semantic";
import { CATEGORIES, type CommerceState, type SearchSort } from "../entities.js";
import { OK, no } from "./shared.js";

const SORTS: readonly SearchSort[] = ["relevance", "price_asc", "price_desc"];

function minPrice(state: CommerceState, productId: string): number {
  const p = state.products[productId]!;
  return Math.min(...p.variantIds.map((v) => state.variants[v]!.price.minor));
}

export const search: OperationDefinition<CommerceState, { query: string; category: string; sort: string }> = {
  name: "search",
  description: "find active products by tag or name key within an optional category; the result is recorded in session",
  params: { query: "string", category: "string", sort: { kind: "enum", values: SORTS } },
  precondition: (s, p) => (p.category === "" || CATEGORIES.includes(p.category as never) ? OK : no(`unknown category ${p.category}`)),
  apply: (s, p) => {
    const q = p.query.trim().toLowerCase();
    let ids = Object.keys(s.products).sort().filter((id) => {
      const prod = s.products[id]!;
      if (!prod.active) return false;
      if (p.category && prod.category !== p.category) return false;
      if (!q) return true;
      return prod.nameKey.toLowerCase().includes(q) || prod.tags.some((t) => t.toLowerCase().includes(q)) || prod.category.toLowerCase().includes(q);
    });
    if (p.sort === "price_asc") ids = [...ids].sort((a, b) => minPrice(s, a) - minPrice(s, b) || (a < b ? -1 : 1));
    if (p.sort === "price_desc") ids = [...ids].sort((a, b) => minPrice(s, b) - minPrice(s, a) || (a < b ? -1 : 1));
    return { ...s, session: { ...s.session, lastSearch: { query: p.query, category: p.category, sort: p.sort as SearchSort, resultIds: ids } } };
  },
  sample: (s, rng) => {
    const tags = Array.from(new Set(Object.values(s.products).flatMap((p) => p.tags))).sort();
    const query = rng.bool(0.5) ? rng.pick(tags) : rng.bool(0.5) ? "" : "tag";
    const category = rng.bool(0.5) ? "" : rng.pick(CATEGORIES);
    return { query, category, sort: rng.pick(SORTS) };
  },
};

export const viewProduct: OperationDefinition<CommerceState, { productId: string }> = {
  name: "viewProduct",
  description: "open a product page; recorded in session.recentlyViewed (most recent first, at most 20)",
  params: { productId: { kind: "ref", entity: "product" } },
  precondition: (s, p) => (s.products[p.productId]?.active ? OK : no(`no active product ${p.productId}`)),
  apply: (s, p) => ({ ...s, session: { ...s.session, recentlyViewed: [p.productId, ...s.session.recentlyViewed.filter((x) => x !== p.productId)].slice(0, 20) } }),
  sample: (s, rng) => {
    const ids = Object.keys(s.products).sort().filter((id) => s.products[id]!.active);
    return ids.length ? { productId: rng.pick(ids) } : null;
  },
};
