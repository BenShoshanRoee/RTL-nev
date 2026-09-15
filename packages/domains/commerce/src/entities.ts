/**
 * Commerce entities. State is canonical JSON: integers only, collections keyed by id, one
 * currency per state. No language: names, sizes, colours and reasons are resource keys the
 * surface layer resolves (res/strings.<lang>.json), so Arabic is a content swap.
 *
 * Time is explicit state (`session.now`, epoch milliseconds) advanced by the system operation
 * `advanceClock`; the domain never reads a wall clock, so every run is reproducible.
 */

import type { CurrencyCode, Money } from "@rtl/core-semantic";

export type SizeSystem = "numeric" | "letters" | "words" | "none";

export type Product = {
  id: string;
  nameKey: string;
  category: string;
  sizeSystem: SizeSystem;
  variantIds: string[];
  tags: string[];
  active: boolean;
};

export type Variant = {
  id: string;
  productId: string;
  sizeKey: string | null;
  colourKey: string | null;
  price: Money;
  weightGrams: number;
};

export type InventoryRecord = {
  variantId: string;
  available: number;
  reserved: number;
};

export type CouponKind = "percent" | "fixed" | "free_shipping";

export type Coupon = {
  code: string;
  kind: CouponKind;
  /** percent: whole percent; fixed: minor units; free_shipping: unused (0). */
  value: number;
  minSubtotal: Money;
  /** "" means the whole catalog; otherwise a category id. */
  category: string;
  expiresAt: number | null;
  maxUses: number;
  uses: number;
  active: boolean;
};

export type ShippingOption = {
  id: string;
  nameKey: string;
  price: Money;
  etaDaysMin: number;
  etaDaysMax: number;
  requiresSlot: boolean;
  /** null means every city. */
  cities: string[] | null;
};

export type DeliverySlot = {
  id: string;
  shippingOptionId: string;
  day: number;
  windowKey: string;
  capacity: number;
  booked: number;
};

export type Customer = {
  id: string;
  nameKey: string;
  phone: string;
  email: string;
  defaultAddressId: string;
  defaultPaymentMethodId: string;
  loyaltyPoints: number;
};

export type Address = {
  id: string;
  recipient: string;
  street: string;
  houseNumber: string;
  apartment: string;
  city: string;
  postalCode: string;
  notes: string;
};

export type PaymentKind = "card" | "wallet" | "cod";

export type PaymentMethod = {
  id: string;
  kind: PaymentKind;
  last4: string;
  expired: boolean;
};

export type CartLine = {
  id: string;
  variantId: string;
  quantity: number;
  /** Snapshot of the variant price when added; kept equal to the current price by invariant. */
  unitPrice: Money;
};

export type DeliveryGroup = {
  id: string;
  lineIds: string[];
  shippingOptionId: string;
  deliverySlotId: string | null;
};

export type Totals = {
  subtotal: Money;
  discount: Money;
  loyalty: Money;
  shipping: Money;
  /** VAT contained in `total` (prices are VAT-inclusive). */
  vat: Money;
  total: Money;
};

export type Cart = {
  lines: Record<string, CartLine>;
  couponCode: string | null;
  loyaltyPointsApplied: number;
  addressId: string | null;
  shippingOptionId: string | null;
  deliverySlotId: string | null;
  /** null when not split; otherwise an exact partition of the cart lines. */
  deliveryGroups: Record<string, DeliveryGroup> | null;
  paymentMethodId: string | null;
  totals: Totals;
};

export type SavedItem = {
  id: string;
  variantId: string;
  quantity: number;
};

export type ShipmentStatus = "pending" | "dispatched" | "delivered";

export type Shipment = {
  id: string;
  lineIds: string[];
  shippingOptionId: string;
  deliverySlotId: string | null;
  status: ShipmentStatus;
  dispatchedAt: number | null;
  deliveredAt: number | null;
  /** Per line, the cancelled quantity frozen at dispatch: nothing can be cancelled after. */
  cancelledAtDispatch: Record<string, number> | null;
};

export type OrderLine = {
  id: string;
  variantId: string;
  quantity: number;
  unitPrice: Money;
  cancelled: number;
  returned: number;
  shipmentId: string;
};

export type OrderStatus = "pending" | "partially_dispatched" | "dispatched" | "delivered" | "cancelled";

export type OrderEvent = {
  kind: string;
  at: number;
  ref: string;
};

export type Order = {
  id: string;
  number: number;
  customerId: string;
  lines: Record<string, OrderLine>;
  shipments: Record<string, Shipment>;
  address: Address;
  paymentMethodId: string;
  couponCode: string | null;
  loyaltyPointsUsed: number;
  totals: Totals;
  /** Money returned to the customer so far through cancellations and returns. */
  refunded: Money;
  status: OrderStatus;
  placedAt: number;
  events: OrderEvent[];
};

export type ReturnStatus = "requested" | "approved" | "received" | "refunded" | "rejected";

export type ReturnRequest = {
  id: string;
  orderId: string;
  lines: Record<string, number>;
  reasonKey: string;
  status: ReturnStatus;
  refund: Money;
  requestedAt: number;
};

export type SearchSort = "relevance" | "price_asc" | "price_desc";

export type SearchResult = {
  query: string;
  category: string;
  sort: SearchSort;
  resultIds: string[];
};

export type CommerceConfig = {
  currency: CurrencyCode;
  /** Whole percent; prices are VAT-inclusive and `vat` is the part contained in the total. */
  vatPercent: number;
  returnWindowDays: number;
  /** Value of one loyalty point in minor units. */
  loyaltyPointValueMinor: number;
};

export type Counters = {
  order: number;
  line: number;
  shipment: number;
  return: number;
  address: number;
  group: number;
  saved: number;
};

export type CommerceState = {
  config: CommerceConfig;
  counters: Counters;
  products: Record<string, Product>;
  variants: Record<string, Variant>;
  inventory: Record<string, InventoryRecord>;
  coupons: Record<string, Coupon>;
  shippingOptions: Record<string, ShippingOption>;
  deliverySlots: Record<string, DeliverySlot>;
  customer: Customer;
  addresses: Record<string, Address>;
  paymentMethods: Record<string, PaymentMethod>;
  cart: Cart;
  saved: Record<string, SavedItem>;
  orders: Record<string, Order>;
  returns: Record<string, ReturnRequest>;
  session: {
    now: number;
    lastSearch: SearchResult | null;
    recentlyViewed: string[];
    lastTrackedOrderId: string | null;
  };
};

export const CATEGORIES = ["cat.apparel", "cat.shoes", "cat.home", "cat.electronics", "cat.grocery"] as const;
export const COLOURS = ["colour.black", "colour.white", "colour.blue", "colour.red", "colour.green", "colour.beige"] as const;
export const SIZE_KEYS: Record<SizeSystem, readonly string[]> = {
  numeric: ["size.num.36", "size.num.37", "size.num.38", "size.num.39", "size.num.40", "size.num.41", "size.num.42", "size.num.43", "size.num.44"],
  letters: ["size.letter.xs", "size.letter.s", "size.letter.m", "size.letter.l", "size.letter.xl", "size.letter.xxl"],
  words: ["size.words.small", "size.words.medium", "size.words.large"],
  none: [],
};
export const RETURN_REASONS = ["return.reason.wrong_size", "return.reason.damaged", "return.reason.not_as_described", "return.reason.changed_mind"] as const;
export const CITIES = ["city.tel_aviv", "city.jerusalem", "city.haifa", "city.beer_sheva", "city.eilat", "city.netanya", "city.rishon"] as const;
