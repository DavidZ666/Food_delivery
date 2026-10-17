import { test, expect } from "./fixtures.mjs";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

test("non-array restaurant storage shows a server error, not no matches or not found", async ({ page, app }) => {
  await writeFile(join(app.directory, "restaurants.json"), "{}");
  await page.goto(`${app.url}/app/?name=missing`);
  await expect(page.locator("#restaurant-status")).toContainText("The server could not complete the request");
  await expect(page.locator("#restaurant-list li")).toHaveCount(0);
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  await expect(page.locator("#restaurant-status")).toContainText("The server could not complete the request");
  await expect(page.locator("#menu-section")).toBeHidden();
});

test("non-array product storage shows a menu error and recovers after repair", async ({ page, app }) => {
  await writeFile(join(app.directory, "products.json"), "{}");
  await page.goto(`${app.url}/app/restaurant.html?id=1`);
  await expect(page.locator("#restaurant-name")).toHaveText("McDonalds");
  await expect(page.locator("#menu-status")).toContainText("The server could not complete the request");
  await writeFile(join(app.directory, "products.json"), "[]");
  await page.getByRole("button", { name: "Retry menu" }).click();
  await expect(page.locator("#menu-status")).toHaveText("No menu items available.");
  await writeFile(join(app.directory, "products.json"), "{}");
  await page.goto(`${app.url}/app/menu-item.html?restaurantId=1&productId=1`);
  await expect(page.locator("#item-status")).toContainText("The server could not complete the request");
});
