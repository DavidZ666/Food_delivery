import {
  test,
  expect,
  signInThroughUi,
} from "./fixtures.mjs";

const CUSTOMER = {
  email: "workflow@example.com",
  password: "workflow-password",
};

const REGISTRATION = {
  name: "Workflow Customer",
  phone: "250-555-0198",
  email: CUSTOMER.email,
  password: CUSTOMER.password,
  "delivery_address.address": "98 Test Street",
  "delivery_address.city": "Kelowna",
  "delivery_address.province": "BC",
  "delivery_address.postal_code": "V1V 1V1",
};

const money = (amount) => `$${amount.toFixed(2)}`;

// Management API calls only prepare test data.
// All customer actions below run through the browser UI.
async function seedMenu(app, request) {
  const token = await app.signIn();
  const headers = { Authorization: `Bearer ${token}` };

  async function createRestaurant(name) {
    const response = await request.post(`${app.url}/restaurants`, {
      headers,
      data: {
        name,
        cuisine: "Test",
        location: {
          address: "1 Test Street",
          city: "Kelowna",
          province: "BC",
          postal_code: "V1V 1V1",
        },
      },
    });

    expect(response.status()).toBe(201);
    return response.json();
  }

  async function createItem(restaurant, name, price, available = true) {
    const response = await request.post(
      `${app.url}/restaurants/${restaurant.id}/menu`,
      {
        headers,
        data: {
          name,
          category: "Main",
          price,
          is_available: available,
        },
      }
    );

    expect(response.status()).toBe(201);
    return response.json();
  }

  const restaurant = await createRestaurant("Workflow Kitchen");
  const otherRestaurant = await createRestaurant("Workflow Other Kitchen");

  const rice = await createItem(restaurant, "Workflow Rice", 10);
  const soup = await createItem(restaurant, "Workflow Soup", 4);
  const unavailable = await createItem(
    restaurant,
    "Workflow Unavailable",
    3,
    false
  );
  const otherItem = await createItem(
    otherRestaurant,
    "Workflow Other Rice",
    8
  );

  return {
    restaurant,
    otherRestaurant,
    rice,
    soup,
    unavailable,
    otherItem,
    headers,
  };
}

async function registerAndSignIn(page, app) {
  await page.goto(`${app.url}/app/register.html`);

  for (const [name, value] of Object.entries(REGISTRATION)) {
    await page.locator(`[name="${name}"]`).fill(value);
  }

  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/sign-in\.html\?registered=1$/);

  await signInThroughUi(page, app, CUSTOMER);
}

async function openRestaurant(page, app, restaurant) {
  await page.goto(`${app.url}/app/restaurant.html?id=${restaurant.id}`);
  await expect(page.locator("#restaurant-name")).toHaveText(restaurant.name);
}

function addButton(page, item) {
  return page.getByRole("button", {
    name: `Add to cart: ${item.name}`,
    exact: true,
  });
}

// Register the listener before clicking, so fast API responses aren't missed.
// Returns the actual backend response, not mocked data.
async function responseFor(page, method, pathname, action) {
  const pending = page.waitForResponse((response) => {
    return response.request().method() === method &&
      pathname.test(new URL(response.url()).pathname);
  });

  await action();
  return pending;
}

async function expectCart(page, cart) {
  await expect(page.locator("#cart-subtotal")).toHaveText(money(cart.subtotal));
  await expect(page.locator("#cart-total")).toHaveText(money(cart.total));
  await expect(page.locator("#cart-items > li")).toHaveCount(cart.items.length);

  for (const item of cart.items) {
    await expect(
      page.getByRole("spinbutton", {
        name: `Quantity for ${item.name}:`,
        exact: true,
      })
    ).toHaveValue(String(item.quantity));
  }
}

async function addItem(page, item) {
  const response = await responseFor(
    page,
    "POST",
    /\/customers\/\d+\/cart\/items$/,
    () => addButton(page, item).click()
  );

  expect(response.status()).toBe(200);

  const cart = await response.json();
  await expectCart(page, cart);
  return cart;
}

async function changeMenuItem(app, request, seed, item, changes) {
  const response = await request.patch(
    `${app.url}/restaurants/${item.restaurant_id}/menu/${item.product_id}`,
    { headers: seed.headers, data: changes }
  );

  expect(response.status()).toBe(200);
}

async function expectOrderSnapshot(container, order) {
  await expect(container).toBeVisible();
  await expect(container).toContainText(`#${order.order_id}`);
  await expect(container).toContainText(order.delivery_address.address);

  for (const item of order.items) {
    const row = container.locator("tbody tr").filter({
      has: container.page().getByRole("rowheader", {
        name: item.name,
        exact: true,
      }),
    });

    await expect(row.locator("td")).toHaveText([
      money(item.unit_price),
      String(item.quantity),
      money(item.line_total),
    ]);
  }

  await expect(container.locator("tfoot tr").last().locator("td"))
    .toHaveText(money(order.total));
}

test("customer workflow persists its order across a server restart", async ({
  page,
  app,
  request,
}) => {
  const seed = await seedMenu(app, request);
  await registerAndSignIn(page, app);

  // Browse the real restaurant list and navigate into its menu.
  await page.goto(`${app.url}/app/`);
  await page.locator("#restaurant-list").getByRole("link", {
    name: seed.restaurant.name,
    exact: true,
  }).click();

  await expect(page.locator("#restaurant-name"))
    .toHaveText(seed.restaurant.name);

  await addItem(page, seed.rice);
  await addItem(page, seed.soup);

  // Update quantity.
  const riceRow = page.locator("#cart-items > li").filter({
    has: page.getByRole("spinbutton", {
      name: `Quantity for ${seed.rice.name}:`,
      exact: true,
    }),
  });

  await riceRow.getByRole("spinbutton").fill("3");

  const updatedResponse = await responseFor(
    page,
    "PATCH",
    new RegExp(`/cart/items/${seed.rice.product_id}$`),
    () => riceRow.getByRole("button", { name: "Update quantity" }).click()
  );

  expect(updatedResponse.status()).toBe(200);
  await expectCart(page, await updatedResponse.json());

  // Remove one line.
  const removedResponse = await responseFor(
    page,
    "DELETE",
    new RegExp(`/cart/items/${seed.soup.product_id}$`),
    () => page.getByRole("button", {
      name: `Remove ${seed.soup.name}`,
      exact: true,
    }).click()
  );

  expect(removedResponse.status()).toBe(200);
  await expectCart(page, await removedResponse.json());

  // Clear and rebuild the cart.
  const clearedResponse = await responseFor(
    page,
    "DELETE",
    /\/cart\/items$/,
    () => page.locator("#cart-clear").click()
  );

  expect(clearedResponse.status()).toBe(200);
  await expectCart(page, await clearedResponse.json());
  await expect(page.locator("#cart-empty")).toBeVisible();
  await expect(page.locator("#cart-checkout")).toBeDisabled();

  const cart = await addItem(page, seed.rice);

  // Checkout must use the latest backend price, not the old cart price.
  await changeMenuItem(app, request, seed, seed.rice, { price: 12.5 });

  const checkoutResponse = await responseFor(
    page,
    "POST",
    /\/customers\/\d+\/checkout$/,
    () => page.locator("#cart-checkout").click()
  );

  expect(checkoutResponse.status()).toBe(201);
  const order = await checkoutResponse.json();

  expect(order.customer_id).toBe(cart.customer_id);
  expect(order.total).toBe(12.5);
  expect(order.items[0].unit_price).toBe(12.5);

  await expectOrderSnapshot(
    page.locator("#order-confirmation-details"),
    order
  );
  await expect(page.locator("#cart-empty")).toBeVisible();
  await expect(page.locator("#cart-total")).toHaveText("$0.00");
  await expect(page.locator("#cart-checkout")).toBeDisabled();

  await page.locator("#order-confirmation-link").click();
  await expectOrderSnapshot(page.locator("#order-detail"), order);

  // Later menu edits must not change the saved order.
  await changeMenuItem(app, request, seed, seed.rice, { price: 99 });

  await app.restart();

  // Sessions are intentionally invalidated by a server restart.
  await signInThroughUi(page, app, CUSTOMER);

  await page.goto(`${app.url}/app/orders.html`);
  await page.locator("#orders-list").getByRole("link", {
    name: `Order #${order.order_id}`,
    exact: true,
  }).click();

  await expectOrderSnapshot(page.locator("#order-detail"), order);

  // The consumed cart also remains empty after restart.
  await openRestaurant(page, app, seed.restaurant);
  await expect(page.locator("#cart-empty")).toBeVisible();
  await expect(page.locator("#cart-items > li")).toHaveCount(0);
});

test("cross-restaurant additions are rejected without losing the cart", async ({
  page,
  app,
  request,
}) => {
  const seed = await seedMenu(app, request);
  await registerAndSignIn(page, app);
  await openRestaurant(page, app, seed.restaurant);

  const originalCart = await addItem(page, seed.rice);

  await openRestaurant(page, app, seed.otherRestaurant);

  const response = await responseFor(
    page,
    "POST",
    /\/cart\/items$/,
    () => addButton(page, seed.otherItem).click()
  );

  expect(response.status()).toBe(409);
  const error = await response.json();

  await expect(page.locator("#cart-status")).toHaveText(error.detail);
  await expectCart(page, originalCart);

  // The failed addition also leaves persisted data unchanged.
  await page.reload();
  await expectCart(page, originalCart);
});

test("unavailable items and failed checkout preserve the existing cart", async ({
  page,
  app,
  request,
}) => {
  const seed = await seedMenu(app, request);
  await registerAndSignIn(page, app);
  await openRestaurant(page, app, seed.restaurant);

  await expect(page.getByRole("button", {
    name: `Unavailable: ${seed.unavailable.name}`,
    exact: true,
  })).toBeDisabled();

  const originalCart = await addItem(page, seed.rice);

  // Menu changes after the page was loaded: stale UI must still be rejected.
  await changeMenuItem(app, request, seed, seed.soup, {
    is_available: false,
  });

  const addResponse = await responseFor(
    page,
    "POST",
    /\/cart\/items$/,
    () => addButton(page, seed.soup).click()
  );

  expect(addResponse.status()).toBe(409);
  const addError = await addResponse.json();
  await expect(page.locator("#cart-status")).toHaveText(addError.detail);
  await expectCart(page, originalCart);

  // An existing cart item becomes unavailable before checkout.
  await changeMenuItem(app, request, seed, seed.rice, {
    is_available: false,
  });

  const checkoutResponse = await responseFor(
    page,
    "POST",
    /\/checkout$/,
    () => page.locator("#cart-checkout").click()
  );

  expect(checkoutResponse.status()).toBe(409);
  const checkoutError = await checkoutResponse.json();

  const status = page.locator("#cart-status");

await expect(status).toContainText(checkoutError.detail);
await expect(status).toContainText("Your cart was not changed.");
await expect(status).toHaveAttribute("data-kind", "error");

  await expect(page.locator("#order-confirmation")).toBeHidden();
  await expectCart(page, originalCart);

  await page.reload();
  await expectCart(page, originalCart);

  await page.goto(`${app.url}/app/orders.html`);
  await expect(page.locator("#orders-empty")).toBeVisible();
});

test("signed-out and expired sessions cannot use protected UI operations", async ({
  page,
  app,
  request,
}) => {
  const seed = await seedMenu(app, request);

  await openRestaurant(page, app, seed.restaurant);
  await expect(page.locator("#cart-sign-in")).toBeVisible();
  await expect(addButton(page, seed.rice)).toBeDisabled();

  await page.goto(`${app.url}/app/orders.html`);
  await expect(page.locator("#orders-sign-in")).toBeVisible();
  await expect(page.locator("#orders-list")).toBeHidden();

  await registerAndSignIn(page, app);
  await openRestaurant(page, app, seed.restaurant);
  await addItem(page, seed.rice);

  // The page retains its old token, while the restarted server rejects it.
  await app.restart();

  const response = await responseFor(
    page,
    "POST",
    /\/checkout$/,
    () => page.locator("#cart-checkout").click()
  );

  expect(response.status()).toBe(401);
  await expect(page.locator("#cart-sign-in")).toBeVisible();
  await expect(page.locator("#cart-content")).toBeHidden();
  await expect(addButton(page, seed.rice)).toBeDisabled();

  await page.goto(`${app.url}/app/orders.html`);
  await expect(page.locator("#orders-sign-in")).toBeVisible();
});