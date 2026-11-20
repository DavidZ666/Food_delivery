// checkout from the cart panel (#97)
import test from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../../frontend/js/api.js";
import { createCartController } from "../../frontend/js/cart.js";

const fullCart = {
  cart_id: 1,
  customer_id: 7,
  restaurant_id: 101,
  items: [{ product_id: 1, name: "Taco", unit_price: 4.5, quantity: 2, line_total: 9 }],
  subtotal: 9,
  total: 9,
};
const emptyCart = { ...fullCart, restaurant_id: null, items: [], subtotal: 0, total: 0 };
const order = {
  order_id: 3,
  customer_id: 7,
  restaurant_id: 101,
  delivery_address: { address: "1 Main St", city: "Kelowna", province: "BC", postal_code: "V1V 1V1" },
  // the price went up since it was added, checkout uses the new one
  items: [{ product_id: 1, name: "Taco", unit_price: 5, quantity: 2, line_total: 10 }],
  subtotal: 10,
  total: 10,
  status: "placed",
  created_at: "2026-11-20T23:32:36Z",
};

// load() runs first with the full cart, then `respond` handles everything after
function setup(respond) {
  const calls = [];
  const rendered = [];
  const messages = [];
  const orders = [];
  let denied = false;
  let loaded = false;

  const controller = createCartController({
    customerId: 7,
    request: async (path, options) => {
      if (!loaded) {
        loaded = true;
        return fullCart;
      }
      calls.push({ path, method: options?.method ?? "GET" });
      return respond(path, options, calls.length);
    },
    render: (cart) => rendered.push(cart),
    showStatus: (message, error) => messages.push({ message, error }),
    setBusy: () => {},
    onDenied: () => { denied = true; },
    onOrder: (placed) => orders.push(placed),
  });

  return { controller, calls, rendered, messages, orders, isDenied: () => denied };
}

test("checkout posts the order, shows it, then reloads the empty cart", async () => {
  const ui = setup((path) => (path.endsWith("/checkout") ? order : emptyCart));
  await ui.controller.load();

  assert.equal(await ui.controller.checkout(), true);
  assert.deepEqual(ui.calls, [
    { path: "/customers/7/checkout", method: "POST" },
    { path: "/customers/7/cart", method: "GET" },
  ]);
  assert.deepEqual(ui.orders, [order]);
  assert.deepEqual(ui.rendered.at(-1), emptyCart);
  assert.equal(ui.messages.at(-1).message, "Order placed.");
  assert.ok(!ui.messages.at(-1).error);
});

for (const detail of ["Menu item is unavailable", "Cart is empty"]) {
  test(`a rejected checkout keeps the cart on screen: ${detail}`, async () => {
    const ui = setup(() => {
      throw new ApiError(detail, { status: 409, detail });
    });
    await ui.controller.load();

    assert.equal(await ui.controller.checkout(), false);
    assert.deepEqual(ui.orders, []);
    // nothing new rendered, so the displayed cart is the one from load()
    assert.deepEqual(ui.rendered, [fullCart]);
    assert.deepEqual(ui.messages.at(-1), {
      message: `Checkout failed: ${detail}. Your cart was not changed.`,
      error: true,
    });

    // the cart still works after, e.g. to remove the bad item
    ui.calls.length = 0;
    assert.equal(await ui.controller.checkout(), false);
    assert.equal(ui.calls.length, 1);
  });
}

test("a too-large total is shown without the 409 wording", async () => {
  const ui = setup(() => {
    throw new ApiError("Cart total is too large", { status: 422, detail: "Cart total is too large" });
  });
  await ui.controller.load();
  assert.equal(await ui.controller.checkout(), false);
  assert.deepEqual(ui.messages.at(-1), { message: "Cart total is too large", error: true });
});

test("a deactivated or signed-out account can't keep checking out", async () => {
  const ui = setup(() => {
    throw new ApiError("This account is not allowed to do that.", { status: 403 });
  });
  await ui.controller.load();

  assert.equal(await ui.controller.checkout(), false);
  assert.equal(ui.isDenied(), true);
  assert.equal(await ui.controller.checkout(), false);
  assert.equal(ui.calls.length, 1);
});

test("a missing cart reloads instead of showing a stale one", async () => {
  // e.g. it was already checked out in another tab
  const ui = setup((path, options, count) => {
    if (count === 1) throw new ApiError("Cart not found", { status: 404, detail: "Cart not found" });
    if (options?.method === "POST") return emptyCart;
    throw new ApiError("Cart not found", { status: 404, detail: "Cart not found" });
  });
  await ui.controller.load();

  assert.equal(await ui.controller.checkout(), false);
  assert.deepEqual(ui.rendered.at(-1), emptyCart);
  assert.deepEqual(ui.orders, []);
});

test("a malformed order isn't shown", async () => {
  const ui = setup((path) => (path.endsWith("/checkout") ? { order_id: 3 } : emptyCart));
  await ui.controller.load();

  assert.equal(await ui.controller.checkout(), false);
  assert.deepEqual(ui.orders, []);
  assert.deepEqual(ui.messages.at(-1), { message: "The server returned an invalid order.", error: true });
});

test("checkout does nothing before the cart has loaded", async () => {
  const ui = setup(() => order);
  assert.equal(await ui.controller.checkout(), false);
  assert.deepEqual(ui.calls, []);
});
