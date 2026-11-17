import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  PROFILE_FIELDS,
  customerToValues,
  signInErrorMessage,
  toProfileUpdatePayload,
  toRegistrationPayload,
  toSignInPayload,
  validateProfile,
  validateRegistration,
  validateSignIn,
} from "../../frontend/js/account-form.js";
import { ApiError } from "../../frontend/js/api.js";

// test_frontend.py sends these same payloads to the API
const cases = JSON.parse(readFileSync(new URL("./account-form-cases.json", import.meta.url), "utf8"));
const valid = cases.registration[0].values;

for (const { name, values, payload } of cases.registration) {
  test(`toRegistrationPayload: ${name}`, () => {
    assert.deepEqual(validateRegistration(values), {});
    assert.deepEqual(toRegistrationPayload(values), payload);
  });
}

for (const { name, original, values, payload } of cases.profile) {
  test(`toProfileUpdatePayload: ${name}`, () => {
    assert.deepEqual(validateProfile(values), {});
    assert.deepEqual(toProfileUpdatePayload(original, values), payload);
  });
}

test("customerToValues flattens the address and an unedited form sends nothing", () => {
  const { original } = cases.profile[0];
  const values = customerToValues(original);
  assert.deepEqual(Object.keys(values), PROFILE_FIELDS);
  assert.equal(values["delivery_address.postal_code"], "V1V 1V2");
  assert.deepEqual(toProfileUpdatePayload(original, values), {});
});

test("blank required fields are reported under their input names", () => {
  const required = Object.fromEntries(PROFILE_FIELDS.map((field) => [field, "This field is required."]));
  assert.deepEqual(validateProfile({ name: "  " }), required);
  assert.deepEqual(validateRegistration({}), {
    ...required, email: "This field is required.", password: "This field is required.",
  });
  assert.deepEqual(validateSignIn({ email: " " }), {
    email: "This field is required.", password: "This field is required.",
  });
});

for (const [field, value, message] of [
  ["email", "ada.example.com", "Enter an email address like name@example.com."],
  ["email", "ada@example", "Enter an email address like name@example.com."],
  ["email", "a da@example.com", "Enter an email address like name@example.com."],
  ["password", "1234567", "Use at least 8 characters."],
  ["password", "x".repeat(129), "Use at most 128 characters."],
]) {
  test(`validateRegistration rejects ${field} ${JSON.stringify(value.slice(0, 20))}`, () => {
    assert.deepEqual(validateRegistration({ ...valid, [field]: value }), { [field]: message });
  });
}

test("a whitespace-only password is long enough when it has 8 characters", () => {
  assert.deepEqual(validateRegistration({ ...valid, password: " ".repeat(8) }), {});
  assert.deepEqual(validateSignIn({ email: "ada@example.com", password: " " }), {});
});

test("toSignInPayload trims the email and keeps the password as typed", () => {
  assert.deepEqual(toSignInPayload({ email: " ada@example.com ", password: " secret pw " }), {
    email: "ada@example.com", password: " secret pw ",
  });
});

test("sign-in errors explain wrong credentials and deactivated accounts", () => {
  assert.equal(signInErrorMessage(new ApiError("x", { status: 401 })), "Email or password is incorrect.");
  assert.equal(signInErrorMessage(new ApiError("x", { status: 403 })), "This account has been deactivated.");
  assert.equal(signInErrorMessage(new ApiError("Could not reach the server.")), "Could not reach the server.");
  assert.equal(signInErrorMessage(new ApiError("Some fields are invalid.", { status: 422 })), "Some fields are invalid.");
});
