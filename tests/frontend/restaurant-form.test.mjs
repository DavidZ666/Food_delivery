import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  REQUIRED_FIELDS,
  fieldErrorsFromDetail,
  toCreatePayload,
  validateRestaurantForm,
} from "../../frontend/js/restaurant-form.js";

// Shared with tests/test_frontend.py, which posts each payload to the API.
const cases = JSON.parse(
  readFileSync(new URL("./create-form-cases.json", import.meta.url), "utf8"),
);

for (const { name, values, payload } of cases) {
  test(`toCreatePayload: ${name}`, () => {
    assert.deepEqual(toCreatePayload(values), payload);
  });

  test(`validateRestaurantForm accepts: ${name}`, () => {
    assert.deepEqual(validateRestaurantForm(values), {});
  });
}

test("validateRestaurantForm reports every missing or blank required field", () => {
  const errors = validateRestaurantForm({ name: "   ", cuisine: "Thai" });
  assert.deepEqual(
    Object.keys(errors).sort(),
    REQUIRED_FIELDS.filter((field) => field !== "cuisine").sort(),
  );
  assert.equal(errors.name, "This field is required.");
});

test("fieldErrorsFromDetail maps FastAPI 422 locations to input names", () => {
  const detail = [
    { loc: ["body", "name"], msg: "String should have at least 1 character" },
    { loc: ["body", "location", "city"], msg: "City problem" },
    { loc: ["body", "location", "city"], msg: "Second city problem" },
    { loc: ["body"], msg: "Field required" },
  ];
  assert.deepEqual(fieldErrorsFromDetail(detail), {
    name: "String should have at least 1 character",
    "location.city": "City problem",
    "": "Field required",
  });
});

test("fieldErrorsFromDetail ignores non-validation details", () => {
  assert.deepEqual(fieldErrorsFromDetail("Restaurant not found"), {});
  assert.deepEqual(fieldErrorsFromDetail(null), {});
});
