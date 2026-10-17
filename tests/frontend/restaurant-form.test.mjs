import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  REQUIRED_FIELDS,
  WEEKDAYS,
  fieldErrorsFromDetail,
  restaurantToValues,
  toCreatePayload,
  toUpdatePayload,
  validateRestaurantForm,
} from "../../frontend/js/restaurant-form.js";

// test_frontend.py sends these same payloads to the API
const readCases = (file) =>
  JSON.parse(readFileSync(new URL(file, import.meta.url), "utf8"));
const cases = readCases("./create-form-cases.json");
const updateCases = readCases("./update-form-cases.json");

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

for (const { name, original, values, payload } of updateCases) {
  test(`toUpdatePayload: ${name}`, () => {
    assert.deepEqual(toUpdatePayload(original, values), payload);
  });
}

test("toUpdatePayload sends nothing for an unedited form", () => {
  for (const { original } of updateCases) {
    assert.deepEqual(toUpdatePayload(original, restaurantToValues(original)), {});
  }
});

test("restaurantToValues flattens nested fields and blanks missing ones", () => {
  const values = restaurantToValues({
    id: 7,
    name: "Taco Spot",
    cuisine: "Mexican",
    location: { address: "10 Main St", city: "Kelowna", province: "BC", postal_code: "V1V 1V4" },
    description: null,
    hours: { monday: "09:00-17:00", tuesday: null },
  });
  assert.equal(values.name, "Taco Spot");
  assert.equal(values["location.city"], "Kelowna");
  assert.equal(values.description, "");
  assert.equal(values.logo_url, "");
  assert.equal(values["hours.monday"], "09:00-17:00");
  assert.equal(values["hours.tuesday"], "");
  assert.equal("id" in values, false);
  assert.equal(Object.keys(values).length, REQUIRED_FIELDS.length + 2 + WEEKDAYS.length);
});
