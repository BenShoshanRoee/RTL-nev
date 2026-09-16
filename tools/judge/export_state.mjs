// Export deterministic commerce states for the Python judge tests. Run after `pnpm -r build`:
//   pnpm node tools/judge/export_state.mjs > bench/tests/judge/fixtures/commerce-states.json
// Everything derives from seed 42 and named child seeds; re-running yields identical bytes.
import { execute, Rng } from "../../packages/core-semantic/dist/index.js";
import { commerceDomain, seedCommerce } from "../../packages/domains/commerce/dist/index.js";

const ctx = { rng: new Rng(7, "export"), now: () => 0 };
const step = (state, op, params) => {
  const r = execute(commerceDomain, state, op, params, ctx);
  if (!r.ok) throw new Error(`${op} rejected: ${r.reason}`);
  return r;
};

const seed = seedCommerce(new Rng(42, "seed"), { currency: "ILS" });
const variantId = Object.keys(seed.variants).sort().find((id) => {
  const p = seed.products[seed.variants[id].productId];
  return p.active && p.variantIds.length > 1 && seed.inventory[id].available >= 3 && p.variantIds.some((v) => v !== id && seed.inventory[v].available >= 2);
});
const product = seed.products[seed.variants[variantId].productId];
const sibling = product.variantIds.find((v) => v !== variantId && seed.inventory[v].available >= 2);

const trace = [];
let r = step(seed, "addToCart", { variantId, quantity: 2 });
trace.push(r.trace);
const afterAdd = r.state;
const lineId = Object.keys(afterAdd.cart.lines)[0];
r = step(afterAdd, "applyCoupon", { code: "WELCOME10" });
trace.push(r.trace);
const afterCoupon = r.state;
r = step(afterCoupon, "setAddress", { addressId: afterCoupon.customer.defaultAddressId });
r = step(r.state, "setShipping", { shippingOptionId: "ship_courier" });
r = step(r.state, "setPaymentMethod", { paymentMethodId: "pm01" });
r = step(r.state, "checkout", {});
const afterCheckout = r.state;

process.stdout.write(JSON.stringify({
  generated_by: "pnpm node tools/judge/export_state.mjs",
  ids: { variantId, sibling, lineId, productId: product.id },
  states: { seed, afterAdd, afterCoupon, afterCheckout },
  trace_add_and_coupon: trace,
}, null, 0) + "\n");
