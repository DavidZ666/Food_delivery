import { test, expect } from "./fixtures.mjs";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

test("real API: list, search, combined filter, details, menu, item and back", async ({ page, app }) => {
  await page.goto(`${app.url}/app/`);
  await expect(page.locator("#restaurant-list li")).toHaveCount(2);
  await page.getByLabel("Restaurant name").fill("mc");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator("#restaurant-list li")).toHaveCount(1);
  await page.getByLabel("Cuisine", { exact: true }).selectOption("Fried Chicken");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("No restaurants match your search.");
  await page.getByLabel("Restaurant name").fill("");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator("#restaurant-list li")).toHaveCount(1);
  await expect(page.locator("#restaurant-list")).toContainText("KFC");
  await page.getByLabel("Restaurant name").fill("mc");
  await page.getByLabel("Cuisine", { exact: true }).selectOption("Fast Food");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("link", { name: "McDonalds", exact: true }).click();
  await expect(page).toHaveURL(/restaurant.html\?id=1$/);
  await expect(page.getByRole("heading", { name: "McDonalds" })).toBeVisible();
  await expect(page.locator("#menu-list li")).toHaveCount(2);
  await page.getByRole("link", { name: "Big Mac", exact: true }).click();
  await expect(page).toHaveURL(/restaurantId=1&productId=1$/);
  await expect(page.locator("#item-details")).toContainText("$6.99");
  await page.getByRole("link", { name: "Back to restaurant menu" }).click();
  await expect(page.getByRole("heading", { name: "McDonalds" })).toBeVisible();
  await page.getByRole("link", { name: "Back to restaurants" }).click();
  await expect(page.locator("#restaurant-list li")).toHaveCount(2);
});

test("failed detail and item requests show errors instead of misleading content", async ({ page, app }) => {
  await page.route("**/restaurants/1", (route) => route.abort());
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  await expect(page.locator("#restaurant-status")).toContainText("Could not reach the server");
  await expect(page.locator("#menu-section")).toBeHidden();
  await expect(page.locator("#restaurant-details")).toBeEmpty();
  await page.route("**/restaurants/1/menu/1", (route) => route.fulfill({
    status: 500, contentType: "text/plain", body: "Internal Server Error",
  }));
  await page.goto(`${app.url}/app/menu-item.html?restaurantId=1&productId=1`);
  await expect(page.locator("#item-status")).toContainText("The server could not complete the request");
  await expect(page.locator("#item-details")).toBeEmpty();
  await page.unroute("**/restaurants/1/menu/1");
  await page.route("**/restaurants/1/menu/1", (route) => route.abort());
  await page.reload();
  await expect(page.locator("#item-status")).toContainText("Could not reach the server");
});

test("a slow old search cannot overwrite newer search results", async ({ page, app }) => {
  await page.goto(`${app.url}/app/`);
  await expect(page.locator("#restaurant-list li")).toHaveCount(2);
  let release;
  const pending = new Promise((done) => { release = done; });
  await page.route("**/restaurants?name=slow", async (route) => {
    await pending;
    await route.fulfill({ json: [] });
  });
  try {
    await page.getByLabel("Restaurant name").fill("slow");
    await page.locator("#restaurant-search").dispatchEvent("submit");
    await expect(page.getByRole("status")).toHaveText("Loading restaurants...");
    await page.getByLabel("Restaurant name").fill("mc");
    await page.locator("#restaurant-search").dispatchEvent("submit");
    await expect(page.locator("#restaurant-list")).toContainText("McDonalds");
    const response = page.waitForResponse((res) => res.url().endsWith("?name=slow"));
    release();
    await response;
    await expect(page.getByRole("status")).toHaveText("1 restaurant(s) found.");
    await expect(page.locator("#restaurant-list")).toContainText("McDonalds");
  } finally { release(); }
});

test("empty store and empty menu are explicit", async ({ page, app }) => {
  await writeFile(join(app.directory, "products.json"), "[]");
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  await expect(page.locator("#menu-status")).toHaveText("No menu items available.");
  await writeFile(join(app.directory, "restaurants.json"), "[]");
  await page.goto(`${app.url}/app/`);
  await expect(page.getByRole("status")).toHaveText("No restaurants available.");
});

test("unknown IDs, wrong ownership and invalid IDs have clear errors", async ({ page, app }) => {
  for (const [path, selector, message] of [
    ["restaurant.html?id=9999", "#restaurant-status", "Restaurant not found"],
    ["restaurant.html?id=abc", "#restaurant-status", "Invalid or missing restaurant ID."],
    ["restaurant.html", "#restaurant-status", "Invalid or missing restaurant ID."],
    ["menu-item.html?restaurantId=1&productId=3", "#item-status", "Menu item not found"],
    ["menu-item.html?restaurantId=9999&productId=1", "#item-status", "Restaurant not found"],
    ["menu-item.html?restaurantId=1&productId=9999", "#item-status", "Menu item not found"],
    ["menu-item.html?restaurantId=1&productId=abc", "#item-status", "Invalid or missing restaurant or menu item ID."],
  ]) {
    await page.goto(`${app.url}/app/${path}`);
    await expect(page.locator(selector)).toHaveText(message);
  }
});

test("loading and network failure clear stale list; retry restores cuisine options", async ({ page, app }) => {
  let release;
  const pending = new Promise((done) => { release = done; });
  await page.route("**/restaurants", async (route) => { await pending; await route.abort(); });
  await page.goto(`${app.url}/app/`);
  await expect(page.getByRole("status")).toHaveText("Loading restaurants...");
  release();
  await expect(page.getByRole("status")).toContainText("Could not reach the server");
  await page.unroute("**/restaurants");
  await page.getByLabel("Restaurant name").fill("mc");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator("#restaurant-list li")).toHaveCount(1);
  await expect(page.locator("#cuisine option")).toHaveCount(3);
  await page.route("**/restaurants?*", (route) => route.abort());
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Could not reach the server");
  await expect(page.locator("#restaurant-list li")).toHaveCount(0);
});

test("real storage failures retain restaurant details and allow menu retry", async ({ page, app }) => {
  await writeFile(join(app.directory, "products.json"), "{broken");
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  await expect(page.getByRole("heading", { name: "McDonalds" })).toBeVisible();
  await expect(page.locator("#menu-status")).toContainText("The server could not complete the request");
  await writeFile(join(app.directory, "products.json"), "[]");
  await page.getByRole("button", { name: "Retry menu" }).click();
  await expect(page.locator("#menu-status")).toHaveText("No menu items available.");
  await writeFile(join(app.directory, "restaurants.json"), "{broken");
  await page.goto(`${app.url}/app/`);
  await expect(page.getByRole("status")).toContainText("The server could not complete the request");
  await expect(page.locator("#restaurant-list li")).toHaveCount(0);
});

test("unavailable items stay visible; API-created and updated items survive restart", async ({ page, request, app }) => {
  const response = await request.post(`${app.url}/restaurants/1/menu`, { data: {
    name: "Browser Test Soup", category: "Soup", price: 4.25, description: "Fresh soup",
  } });
  expect(response.status()).toBe(201);
  const item = await response.json();
  const updated = await request.patch(`${app.url}/restaurants/1/menu/${item.product_id}`,
    { data: { is_available: false, price: 5.5 } });
  expect(updated.status()).toBe(200);
  await app.restart();
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  const row = page.locator("#menu-list li").filter({ hasText: "Browser Test Soup" });
  await expect(row).toContainText("Unavailable");
  await row.getByRole("link").click();
  await expect(page.locator("#item-details")).toContainText("$5.50");
  await expect(page.locator("#item-details")).toContainText("Unavailable");
});

test("UI restaurant creation and editing persist across an actual server restart", async ({ page, app }) => {
  await page.goto(`${app.url}/app/create-restaurant.html`);
  await page.getByRole("button", { name: "Create restaurant", exact: true }).click();
  await expect(page.locator("#form-status")).toContainText("Please fix");
  for (const [name, value] of Object.entries({ name: "Browser Café", cuisine: "Fusion",
    "location.address": "5 Main St", "location.city": "Kelowna",
    "location.province": "BC", "location.postal_code": "V1V 1V1" })) {
    await page.locator(`[name="${name}"]`).fill(value);
  }
  await page.getByRole("button", { name: "Create restaurant", exact: true }).click();
  await expect(page.locator("#form-status")).toContainText('Created "Browser Café"');
  await page.getByRole("link", { name: "Edit this restaurant" }).click();
  await expect(page.locator('[name="name"]')).toHaveValue("Browser Café");
  await page.locator('[name="name"]').fill("Updated Browser Café");
  await page.locator('[name="location.city"]').fill("Vancouver");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("#form-status")).toHaveAttribute("data-kind", "success");
  await app.restart();
  await page.reload();
  await expect(page.locator('[name="name"]')).toHaveValue("Updated Browser Café");
  await expect(page.locator('[name="location.city"]')).toHaveValue("Vancouver");
  await page.goto(`${app.url}/app/`);
  await page.getByRole("link", { name: "Updated Browser Café", exact: true }).click();
  await expect(page.locator("#restaurant-details")).toContainText("Vancouver");
  await expect(page.locator("#menu-status")).toHaveText("No menu items available.");
});
