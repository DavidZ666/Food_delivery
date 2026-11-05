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

for (const colorScheme of ["light", "dark"]) {
  test(`form boundaries meet non-text contrast in ${colorScheme} mode`, async ({ page, app }) => {
    await page.emulateMedia({ colorScheme });
    for (const path of ["/app/", "/app/create-restaurant.html", "/app/edit-restaurant.html"]) {
      await page.goto(`${app.url}${path}`);
      const controls = await page.locator("input, select, textarea").evaluateAll((elements) => {
        function luminance(color) {
          const [r, g, b] = color.match(/[\d.]+/g).slice(0, 3).map((value) => {
            const channel = Number(value) / 255;
            return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
          });
          return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        }
        function contrast(a, b) {
          const [low, high] = [luminance(a), luminance(b)].sort((x, y) => x - y);
          return (high + 0.05) / (low + 0.05);
        }
        return elements.filter((element) => element.getClientRects().length).map((element) => {
          const style = getComputedStyle(element);
          let parent = element.parentElement;
          while (getComputedStyle(parent).backgroundColor === "rgba(0, 0, 0, 0)") parent = parent.parentElement;
          return {
            id: element.id,
            contrast: Math.min(contrast(style.borderTopColor, style.backgroundColor),
              contrast(style.borderTopColor, getComputedStyle(parent).backgroundColor)),
          };
        });
      });
      expect(controls.length).toBeGreaterThan(0);
      for (const control of controls) expect(control.contrast, `${path} #${control.id}`).toBeGreaterThanOrEqual(3);
    }
  });
}
