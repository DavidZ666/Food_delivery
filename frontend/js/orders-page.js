// orders page (#97). lists the signed-in customer's orders, or shows one
// order with ?id=. request and validation logic is in orders.js

import { orderDetails } from "./order-view.js";
import {
  fetchOrder,
  fetchOrders,
  fetchRestaurantNames,
  money,
  orderIdFrom,
  placedAt,
} from "./orders.js";
import { getCustomer, getToken } from "./session.js";

const main = document.querySelector("#main");
const heading = document.querySelector("#orders-heading");
const status = document.querySelector("#orders-status");
const back = document.querySelector("#orders-back");
const signIn = document.querySelector("#orders-sign-in");
const empty = document.querySelector("#orders-empty");
const list = document.querySelector("#orders-list");
const detail = document.querySelector("#order-detail");

function showStatus(message, isError = false) {
  status.textContent = message;
  status.dataset.kind = isError ? "error" : "info";
}

const restaurantLabel = (names, id) => names.get(id) ?? `Restaurant #${id}`;

async function showList(customerId) {
  const [orders, names] = await Promise.all([fetchOrders(customerId), fetchRestaurantNames()]);
  if (!orders.length) {
    empty.hidden = false;
    return;
  }

  // newest first, the API sends them oldest first
  for (const order of [...orders].reverse()) {
    const row = document.createElement("li");
    const title = document.createElement("h2");
    const link = document.createElement("a");
    link.href = `orders.html?id=${order.order_id}`;
    link.textContent = `Order #${order.order_id}`;
    title.append(link);

    const count = order.items.reduce((sum, item) => sum + item.quantity, 0);
    const summary = document.createElement("p");
    summary.textContent = `${restaurantLabel(names, order.restaurant_id)} · ` +
      `${count} ${count === 1 ? "item" : "items"} · ${money(order.total)} · ` +
      `placed ${placedAt(order.created_at)}`;

    row.append(title, summary);
    list.append(row);
  }
  list.hidden = false;
}

async function showOne(customerId, orderId) {
  back.hidden = false;
  heading.textContent = `Order #${orderId}`;
  document.title = `Order #${orderId} · ByteBites`;

  const [order, names] = await Promise.all([
    fetchOrder(customerId, orderId),
    fetchRestaurantNames(),
  ]);
  detail.replaceChildren(orderDetails(order, restaurantLabel(names, order.restaurant_id)));
  detail.hidden = false;
}

async function start() {
  const customer = getCustomer();
  if (!getToken() || !customer) {
    signIn.hidden = false;
    return;
  }

  const orderId = orderIdFrom(window.location.search);
  if (orderId === false) {
    back.hidden = false;
    showStatus("Invalid or missing order ID.", true);
    return;
  }

  showStatus(orderId === null ? "Loading your orders..." : "Loading order...");
  main.setAttribute("aria-busy", "true");
  try {
    if (orderId === null) {
      await showList(customer.id);
    } else {
      await showOne(customer.id, orderId);
    }
    showStatus("");
  } catch (error) {
    showStatus(error.message || "Could not load your orders.", true);
    // api.js already dropped the expired session, so offer to sign in again
    if (error.status === 401) signIn.hidden = false;
  } finally {
    main.setAttribute("aria-busy", "false");
  }
}

void start();
