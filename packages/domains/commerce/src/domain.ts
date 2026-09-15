import type { DomainDefinition, Rng } from "@rtl/core-semantic";
import { type CommerceState } from "./entities.js";
import { invariants } from "./invariants.js";
import { operations } from "./operations/index.js";
import { seedCommerce } from "./seed.js";

export const commerceDomain: DomainDefinition<CommerceState> = {
  id: "commerce",
  version: "0.1.0",
  entities: {
    product: { key: "id", fields: { id: "string", nameKey: "string", category: "string", sizeSystem: { kind: "enum", values: ["numeric", "letters", "words", "none"] }, variantIds: { kind: "list", of: { kind: "ref", entity: "variant" } }, tags: { kind: "list", of: "string" }, active: "boolean" } },
    variant: { key: "id", fields: { id: "string", productId: { kind: "ref", entity: "product" }, sizeKey: "string", colourKey: "string", price: "money", weightGrams: "integer" } },
    inventory: { key: "variantId", fields: { variantId: { kind: "ref", entity: "variant" }, available: "integer", reserved: "integer" } },
    coupon: { key: "code", fields: { code: "string", kind: { kind: "enum", values: ["percent", "fixed", "free_shipping"] }, value: "integer", minSubtotal: "money", category: "string", expiresAt: "integer", maxUses: "integer", uses: "integer", active: "boolean" } },
    shippingOption: { key: "id", fields: { id: "string", nameKey: "string", price: "money", etaDaysMin: "integer", etaDaysMax: "integer", requiresSlot: "boolean", cities: { kind: "list", of: "string" } } },
    deliverySlot: { key: "id", fields: { id: "string", shippingOptionId: { kind: "ref", entity: "shippingOption" }, day: "integer", windowKey: "string", capacity: "integer", booked: "integer" } },
    customer: { key: "id", fields: { id: "string", nameKey: "string", phone: "string", email: "string", defaultAddressId: { kind: "ref", entity: "address" }, defaultPaymentMethodId: { kind: "ref", entity: "paymentMethod" }, loyaltyPoints: "integer" } },
    address: { key: "id", fields: { id: "string", recipient: "string", street: "string", houseNumber: "string", apartment: "string", city: "string", postalCode: "string", notes: "string" } },
    paymentMethod: { key: "id", fields: { id: "string", kind: { kind: "enum", values: ["card", "wallet", "cod"] }, last4: "string", expired: "boolean" } },
    cartLine: { key: "id", fields: { id: "string", variantId: { kind: "ref", entity: "variant" }, quantity: "integer", unitPrice: "money" } },
    deliveryGroup: { key: "id", fields: { id: "string", lineIds: { kind: "list", of: { kind: "ref", entity: "cartLine" } }, shippingOptionId: { kind: "ref", entity: "shippingOption" }, deliverySlotId: "string" } },
    savedItem: { key: "id", fields: { id: "string", variantId: { kind: "ref", entity: "variant" }, quantity: "integer" } },
    order: { key: "id", fields: { id: "string", number: "integer", customerId: { kind: "ref", entity: "customer" }, paymentMethodId: { kind: "ref", entity: "paymentMethod" }, couponCode: "string", loyaltyPointsUsed: "integer", refunded: "money", status: { kind: "enum", values: ["pending", "partially_dispatched", "dispatched", "delivered", "cancelled"] }, placedAt: "integer" } },
    orderLine: { key: "id", fields: { id: "string", variantId: { kind: "ref", entity: "variant" }, quantity: "integer", unitPrice: "money", cancelled: "integer", returned: "integer", shipmentId: { kind: "ref", entity: "shipment" } } },
    shipment: { key: "id", fields: { id: "string", lineIds: { kind: "list", of: { kind: "ref", entity: "orderLine" } }, shippingOptionId: { kind: "ref", entity: "shippingOption" }, deliverySlotId: "string", status: { kind: "enum", values: ["pending", "dispatched", "delivered"] }, dispatchedAt: "integer", deliveredAt: "integer" } },
    returnRequest: { key: "id", fields: { id: "string", orderId: { kind: "ref", entity: "order" }, reasonKey: "string", status: { kind: "enum", values: ["requested", "approved", "received", "refunded", "rejected"] }, refund: "money", requestedAt: "integer" } },
  },
  operations,
  invariants,
  seedState: (rng: Rng) => seedCommerce(rng, { currency: "ILS" }),
};
