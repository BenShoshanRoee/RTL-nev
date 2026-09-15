import type { OperationDefinition } from "@rtl/core-semantic";
import type { CommerceState } from "../entities.js";
import { search, viewProduct } from "./catalog.js";
import { addToCart, changeVariant, moveToCart, removeLine, saveForLater, setQuantity } from "./cart.js";
import { addAddress, applyCoupon, applyLoyaltyPoints, checkout, editAddress, removeCoupon, selectDeliverySlot, setAddress, setPaymentMethod, setShipping, splitDelivery } from "./checkout.js";
import { cancelLine, cancelOrder, requestReturn, trackOrder } from "./orders.js";
import { advanceClock, advanceShipment, restock } from "./system.js";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- each operation has its own params type
export const operations: Record<string, OperationDefinition<CommerceState, any>> = {
  search, viewProduct,
  addToCart, changeVariant, setQuantity, removeLine, saveForLater, moveToCart,
  applyCoupon, removeCoupon, applyLoyaltyPoints, addAddress, editAddress, setAddress, setShipping, selectDeliverySlot, splitDelivery, setPaymentMethod, checkout,
  cancelLine, cancelOrder, requestReturn, trackOrder,
  advanceClock, advanceShipment, restock,
};

/** Operations the shopper performs, as opposed to the environment (system actor). */
export const SHOPPER_OPERATIONS = Object.keys(operations).filter((n) => !["advanceClock", "advanceShipment", "restock"].includes(n)).sort();
export const SYSTEM_OPERATIONS = ["advanceClock", "advanceShipment", "restock"] as const;
