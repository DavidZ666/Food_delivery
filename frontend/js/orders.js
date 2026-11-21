// order helpers (#97) shared by the checkout confirmation and the orders page.
// no DOM code here so the node tests can import it

import { ApiError, apiRequest } from "./api.js";

export const INVALID_ORDER = "The server returned an invalid order.";

const isAmount = (value) => typeof value === "number" && Number.isFinite(value);
const isId = (value) => Number.isSafeInteger(value) && value > 0;

function isOrderItem(item) {
  return item !== null && typeof item === "object" &&
    isId(item.product_id) &&
    typeof item.name === "string" &&
    Number.isSafeInteger(item.quantity) &&
    isAmount(item.unit_price) &&
    isAmount(item.line_total);
}

// check the response shape before showing it, same idea as isCart in cart.js
export function isOrder(order) {
  return order !== null && typeof order === "object" &&
    isId(order.order_id) &&
    isId(order.restaurant_id) &&
    Array.isArray(order.items) && order.items.length > 0 && order.items.every(isOrderItem) &&
    isAmount(order.subtotal) &&
    isAmount(order.total) &&
    typeof order.status === "string" &&
    typeof order.created_at === "string" &&
    order.delivery_address !== null && typeof order.delivery_address === "object";
}

export async function fetchOrders(customerId, request = apiRequest) {
  const orders = await request(`/customers/${customerId}/orders`);
  if (!Array.isArray(orders) || !orders.every(isOrder)) {
    throw new ApiError("The server returned an invalid order list.");
  }
  return orders;
}

export async function fetchOrder(customerId, orderId, request = apiRequest) {
  const order = await request(`/customers/${customerId}/orders/${orderId}`);
  if (!isOrder(order)) throw new ApiError(INVALID_ORDER);
  return order;
}

// orders only store the restaurant id, so look up names for display.
// if that fails we just show "Restaurant #id" instead
export async function fetchRestaurantNames(request = apiRequest) {
  try {
    const restaurants = await request("/restaurants");
    if (!Array.isArray(restaurants)) return new Map();
    return new Map(restaurants
      .filter((restaurant) => isId(restaurant?.id) && typeof restaurant.name === "string")
      .map((restaurant) => [restaurant.id, restaurant.name]));
  } catch {
    return new Map();
  }
}

// ?id=3 -> 3, no id -> null (show the list), anything else -> false
export function orderIdFrom(search) {
  const id = new URLSearchParams(search).get("id");
  if (id === null) return null;
  return /^[1-9]\d*$/.test(id) ? Number(id) : false;
}

// formatting only, the amounts all come from the backend
export const money = (value) => `$${value.toFixed(2)}`;

// "2026-11-20T23:32:36.123Z" -> "2026-11-20 23:32 UTC"
export const placedAt = (createdAt) => `${createdAt.slice(0, 16).replace("T", " ")} UTC`;
