import { test, expect } from "./fixtures.mjs";

const PAGES = [
  "/app/", "/app/restaurant.html?id=1", "/app/menu-item.html?restaurantId=1&productId=1",
  "/app/create-restaurant.html", "/app/edit-restaurant.html",
];

for (const width of [320, 768, 1280]) {
  test(`pages fit a ${width}px viewport without horizontal scrolling`, async ({ page, app }) => {
    await page.setViewportSize({ width, height: 800 });
    for (const path of PAGES) {
      await page.goto(`${app.url}${path}`);
      await expect(page.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, path).toBeLessThanOrEqual(0);
    }
  });
}

test("the skip link becomes visible on keyboard focus and moves to the content", async ({ page, app }) => {
  await page.goto(`${app.url}/app/`);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("the self-hosted typeface loads", async ({ page, app }) => {
  await page.goto(`${app.url}/app/`);
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => document.fonts.check('700 2rem "Bricolage Grotesque"'))).toBe(true);
  expect(await page.evaluate(() => getComputedStyle(document.querySelector("h1")).fontFamily))
    .toContain("Bricolage Grotesque");
});
