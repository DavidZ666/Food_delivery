import test from "node:test";
import assert from "node:assert/strict";
import { createCartController } from "../../frontend/js/cart.js";

const emptyCart = {
  cart_id: 1,
  customer_id: 7,
  restaurant_id: null,
  items: [],
  subtotal: 0,
  total: 0,
};

function setup(request) {
  const rendered = [];
  const messages = [];
  const locks = [];
  let denied = false;

  const controller = createCartController({
    customerId: 7,
    request,
    render: (cart) => rendered.push(cart),
    showStatus: (message, error) => messages.push({ message, error }),
    setBusy: (busy, ready) => locks.push({ busy, ready }),
    onDenied: () => { denied = true; },
  });

  return {
    controller,
    rendered,
    messages,
    locks,
    isDenied: () => denied,
  };
}

test("creates a cart only after an explicit cart-not-found response", async () => {
  const calls = [];
  const ui = setup(async (path, options) => {
    calls.push({ path, options });
    if (calls.length === 1) {
      throw Object.assign(new Error("Cart not found"), {
        status: 404,
        detail: "Cart not found",
      });
    }
    return emptyCart;
  });

  assert.equal(await ui.controller.load(), true);
  assert.deepEqual(calls, [
    { path: "/customers/7/cart", options: undefined },
    { path: "/customers/7/cart", options: { method: "POST" } },
  ]);
  assert.deepEqual(ui.rendered, [emptyCart]);
});

test("does not create a cart after a network error", async () => {
  let requests = 0;
  const ui = setup(async () => {
    requests++;
    throw new Error("Could not reach the server.");
  });

  assert.equal(await ui.controller.load(), false);
  assert.equal(requests, 1);
  assert.equal(ui.rendered.length, 0);
});

test("sends correct mutation requests and preserves backend totals", async () => {
  const calls = [];
  const returnedCart = {
    ...emptyCart,
    subtotal: 12.34,
    total: 15.67,
  };

  const ui = setup(async (path, options) => {
    calls.push({ path, options });
    return returnedCart;
  });

  await ui.controller.load();
  await ui.controller.add(11);
  await ui.controller.update(11, 3);
  await ui.controller.remove(11);
  await ui.controller.clear();

  assert.deepEqual(calls.slice(1), [
    {
      path: "/customers/7/cart/items",
      options: { method: "POST", body: { product_id: 11, quantity: 1 } },
    },
    {
      path: "/customers/7/cart/items/11",
      options: { method: "PATCH", body: { quantity: 3 } },
    },
    {
      path: "/customers/7/cart/items/11",
      options: { method: "DELETE" },
    },
    {
      path: "/customers/7/cart/items",
      options: { method: "DELETE" },
    },
  ]);

  assert.equal(ui.rendered.at(-1).subtotal, 12.34);
  assert.equal(ui.rendered.at(-1).total, 15.67);
});

for (const message of [
  "Menu item is unavailable",
  "Cart contains items from another restaurant",
]) {
  test(`preserves the displayed cart on conflict: ${message}`, async () => {
    let requests = 0;
    const ui = setup(async () => {
      if (++requests === 1) return emptyCart;
      throw Object.assign(new Error(message), { status: 409 });
    });

    await ui.controller.load();

    assert.equal(await ui.controller.add(11), false);
    assert.deepEqual(ui.rendered, [emptyCart]);
    assert.equal(ui.messages.at(-1).message, message);
    assert.equal(ui.messages.at(-1).error, true);
    assert.deepEqual(ui.locks.at(-1), { busy: false, ready: true });
  });
}

test("rejects invalid quantities without sending a request", async () => {
  let requests = 0;
  const ui = setup(async () => {
    requests++;
    return emptyCart;
  });

  await ui.controller.load();

  for (const quantity of [0, -1, 1.5, NaN]) {
    assert.equal(await ui.controller.update(11, quantity), false);
  }

  assert.equal(requests, 1);
});

test("disables further operations after authentication expires", async () => {
  let requests = 0;
  const ui = setup(async () => {
    if (++requests === 1) return emptyCart;
    throw Object.assign(new Error("Your session has expired."), {
      status: 401,
    });
  });

  await ui.controller.load();
  await ui.controller.add(11);
  await ui.controller.add(11);

  assert.equal(ui.isDenied(), true);
  assert.equal(requests, 2);
  assert.deepEqual(ui.locks.at(-1), { busy: false, ready: false });
});