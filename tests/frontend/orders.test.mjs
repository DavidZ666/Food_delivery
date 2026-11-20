import test from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../../frontend/js/api.js";
import {
  fetchOrder,
  fetchOrders,
  fetchRestaurantNames,
  isOrder,
  money,
  orderIdFrom,
  placedAt,
} from "../../frontend/js/orders.js";

const order = {
  order_id: 3,
  customer_id: 7,
  restaurant_id: 101,
  delivery_address: { address: "1 Main St", city: "Kelowna", province: "BC", postal_code: "V1V 1V1" },
  items: [
    { product_id: 1, name: "Taco", unit_price: 5, quantity: 3, line_total: 15 },
    { product_id: 2, name: "Churro", unit_price: 2, quantity: 1, line_total: 2 },
  ],
  subtotal: 17,
  total: 17,
  status: "placed",
  created_at: "2026-11-20T23:32:36.123456Z",
};

test("isOrder accepts a backend order", () => {
  assert.equal(isOrder(order), true);
});

for (const [name, broken] of [
  ["null", null],
  ["missing id", { ...order, order_id: undefined }],
  ["no items", { ...order, items: [] }],
  ["bad item", { ...order, items: [{ ...order.items[0], quantity: "3" }] }],
  ["bad total", { ...order, total: Infinity }],
  ["missing address", { ...order, delivery_address: null }],
  ["bad timestamp", { ...order, created_at: 42 }],
]) {
  test(`isOrder rejects an order with ${name}`, () => {
    assert.equal(isOrder(broken), false);
  });
}

test("fetchOrders reads the customer's orders", async () => {
  const calls = [];
  const orders = await fetchOrders(7, async (path) => {
    calls.push(path);
    return [order];
  });
  assert.deepEqual(calls, ["/customers/7/orders"]);
  assert.deepEqual(orders, [order]);
});

test("fetchOrders rejects a malformed list", async () => {
  await assert.rejects(fetchOrders(7, async () => [order, { order_id: 4 }]), ApiError);
  await assert.rejects(fetchOrders(7, async () => ({ orders: [] })), ApiError);
});

test("fetchOrder reads one order and passes API errors through", async () => {
  const calls = [];
  assert.deepEqual(await fetchOrder(7, 3, async (path) => {
    calls.push(path);
    return order;
  }), order);
  assert.deepEqual(calls, ["/customers/7/orders/3"]);

  const notFound = new ApiError("Order not found", { status: 404, detail: "Order not found" });
  await assert.rejects(fetchOrder(7, 99, async () => { throw notFound; }), notFound);
  await assert.rejects(fetchOrder(7, 3, async () => ({ ...order, items: [] })), ApiError);
});

test("fetchRestaurantNames maps ids to names", async () => {
  const names = await fetchRestaurantNames(async (path) => {
    assert.equal(path, "/restaurants");
    return [{ id: 101, name: "Testaurant" }, { id: 102, name: "McTest" }];
  });
  assert.deepEqual([...names], [[101, "Testaurant"], [102, "McTest"]]);
});

test("fetchRestaurantNames gives an empty map if restaurants can't load", async () => {
  // names are just nice to have, the orders still show without them
  const names = await fetchRestaurantNames(async () => { throw new ApiError("down"); });
  assert.equal(names.size, 0);
  assert.equal((await fetchRestaurantNames(async () => null)).size, 0);
});

test("orderIdFrom only accepts positive whole numbers", () => {
  assert.equal(orderIdFrom("?id=3"), 3);
  // no id means show the list
  assert.equal(orderIdFrom(""), null);
  for (const bad of ["?id=0", "?id=-1", "?id=1.5", "?id=abc", "?id=", "?id=03"]) {
    assert.equal(orderIdFrom(bad), false, bad);
  }
});

test("money and placedAt format for display only", () => {
  assert.equal(money(17), "$17.00");
  assert.equal(money(0.3), "$0.30");
  assert.equal(placedAt(order.created_at), "2026-11-20 23:32 UTC");
});
