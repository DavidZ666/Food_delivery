import { test, expect, signInThroughUi, MANAGER_CREDENTIALS } from "./fixtures.mjs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const ADA = { email: "ada@example.com", password: "example-password" };
const DETAILS = {
  name: "Ada Lovelace", phone: "250-555-0101", email: ` ${ADA.email} `, password: ADA.password,
  "delivery_address.address": "2 Main St", "delivery_address.city": "Kelowna",
  "delivery_address.province": "BC", "delivery_address.postal_code": "V1V 1V2",
};

async function register(page, app, details) {
  await page.goto(`${app.url}/app/register.html`);
  for (const [name, value] of Object.entries(details)) await page.locator(`[name="${name}"]`).fill(value);
  await page.getByRole("button", { name: "Create account" }).click();
}

const storedAccount = async (app) =>
  JSON.parse(await readFile(join(app.directory, "customers.json"), "utf8")).find((c) => c.email === ADA.email);

test("register, sign in, update the profile, sign out and deactivate through the UI", async ({ page, app }) => {
  await register(page, app, {});
  await expect(page.locator("#form-status")).toContainText("Please fix");
  await expect(page.locator('[name="email"]')).toHaveAttribute("aria-invalid", "true");
  await register(page, app, { ...DETAILS, password: "short" });
  await expect(page.locator("#error-password")).toHaveText("Use at least 8 characters.");
  expect(await storedAccount(app)).toBeUndefined();

  await register(page, app, DETAILS);
  await expect(page).toHaveURL(/sign-in\.html\?registered=1$/);
  await expect(page.locator("#form-status")).toHaveText("Account created. Sign in to continue.");
  expect(await storedAccount(app)).toMatchObject({ role: "customer", is_active: true });
  expect(JSON.stringify(await storedAccount(app))).not.toContain(ADA.password);

  await register(page, app, DETAILS);
  await expect(page.locator("#error-email")).toHaveText("This email is already registered.");

  await page.goto(`${app.url}/app/sign-in.html`);
  await page.getByLabel("Email").fill(ADA.email);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#form-status")).toHaveText("Email or password is incorrect.");
  await page.getByLabel("Password").fill(ADA.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/account\.html$/);
  await expect(page.locator("#account-email")).toHaveText(ADA.email);
  await expect(page.locator('[name="name"]')).toHaveValue("Ada Lovelace");

  const save = page.getByRole("button", { name: "Save changes" });
  await save.click();
  await expect(page.locator("#form-status")).toHaveText("No changes to save.");
  await page.locator('[name="delivery_address.city"]').fill("");
  await save.click();
  await expect(page.locator("#error-delivery_address\\.city")).toHaveText("This field is required.");
  await page.locator('[name="delivery_address.city"]').fill("Vernon");
  await page.locator('[name="phone"]').fill("250-555-0199");
  await save.click();
  await expect(page.locator("#form-status")).toHaveText("Saved your profile.");
  expect(await storedAccount(app)).toMatchObject({
    phone: "250-555-0199",
    delivery_address: { address: "2 Main St", city: "Vernon", province: "BC", postal_code: "V1V 1V2" },
  });
  await page.reload();
  await expect(page.locator('[name="delivery_address.city"]')).toHaveValue("Vernon");

  // The customer's token is attached to management writes, which refuse the role.
  await page.goto(`${app.url}/app/create-restaurant.html`);
  for (const [name, value] of Object.entries({ name: "Not Mine", cuisine: "Fusion",
    "location.address": "5 Main St", "location.city": "Kelowna",
    "location.province": "BC", "location.postal_code": "V1V 1V1" })) {
    await page.locator(`[name="${name}"]`).fill(value);
  }
  await page.getByRole("button", { name: "Create restaurant", exact: true }).click();
  await expect(page.locator("#form-status")).toHaveText("This account is not allowed to do that.");

  await page.goto(`${app.url}/app/account.html`);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.locator("#form-status")).toHaveText("You are signed out.");
  await page.goto(`${app.url}/app/account.html`);
  await expect(page.getByRole("main").getByRole("link", { name: "Sign in" })).toBeVisible();
  await expect(page.locator("#account")).toBeHidden();

  await signInThroughUi(page, app, ADA);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Deactivate account" }).click();
  expect(await storedAccount(app)).toMatchObject({ is_active: true });
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Deactivate account" }).click();
  await expect(page.locator("#form-status")).toHaveText("Your account was deactivated.");
  expect(await storedAccount(app)).toMatchObject({ is_active: false, phone: "250-555-0199" });
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  await page.getByLabel("Email").fill(ADA.email);
  await page.getByLabel("Password").fill(ADA.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#form-status")).toHaveText("This account has been deactivated.");
});

test("a session the server no longer knows returns the account page to signed out", async ({ page, app }) => {
  await signInThroughUi(page, app, MANAGER_CREDENTIALS);
  await app.restart();
  await page.reload();
  await expect(page.locator("#account-status")).toHaveText("Your session has expired. Sign in again.");
  await expect(page.locator("#account")).toBeHidden();
  await expect(page.getByRole("main").getByRole("link", { name: "Sign in" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
});

test("the account pages report a server that cannot be reached", async ({ page, app }) => {
  await page.goto(`${app.url}/app/sign-in.html`);
  await page.getByLabel("Email").fill(ADA.email);
  await page.getByLabel("Password").fill(ADA.password);
  await page.route("**/auth/login", (route) => route.abort());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#form-status")).toHaveText("Could not reach the server. Check that it is running.");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
});
