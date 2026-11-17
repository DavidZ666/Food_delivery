// form logic for the account pages (#95). no DOM stuff in here so we can test it with node
// values use the input names, e.g. "delivery_address.city"

import { ApiError } from "./api.js";

const ADDRESS_FIELDS = ["address", "city", "province", "postal_code"];
export const PROFILE_FIELDS = ["name", "phone", ...ADDRESS_FIELDS.map((field) => `delivery_address.${field}`)];

// same rules as the API's CustomerCreate
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MIN_PASSWORD = 8;
const MAX_PASSWORD = 128;

export function validateProfile(values) {
  const errors = {};
  for (const field of PROFILE_FIELDS) {
    if (!text(values, field)) errors[field] = "This field is required.";
  }
  return errors;
}

export function validateRegistration(values) {
  const errors = validateProfile(values);
  const password = String(values.password ?? "");
  if (!text(values, "email")) errors.email = "This field is required.";
  else if (!EMAIL.test(text(values, "email"))) errors.email = "Enter an email address like name@example.com.";
  if (!password) errors.password = "This field is required.";
  else if (password.length < MIN_PASSWORD) errors.password = `Use at least ${MIN_PASSWORD} characters.`;
  else if (password.length > MAX_PASSWORD) errors.password = `Use at most ${MAX_PASSWORD} characters.`;
  return errors;
}

export function validateSignIn(values) {
  const errors = {};
  if (!text(values, "email")) errors.email = "This field is required.";
  if (!values.password) errors.password = "This field is required.";
  return errors;
}

// body for POST /customers. the password is sent exactly as typed
export function toRegistrationPayload(values) {
  return {
    name: text(values, "name"),
    email: text(values, "email"),
    password: String(values.password ?? ""),
    phone: text(values, "phone"),
    delivery_address: Object.fromEntries(
      ADDRESS_FIELDS.map((field) => [field, text(values, `delivery_address.${field}`)]),
    ),
  };
}

// body for POST /auth/login
export function toSignInPayload(values) {
  return { email: text(values, "email"), password: String(values.password ?? "") };
}

// turns a customer from the API into form values
export function customerToValues(customer) {
  const values = { name: customer.name ?? "", phone: customer.phone ?? "" };
  for (const field of ADDRESS_FIELDS) {
    values[`delivery_address.${field}`] = customer.delivery_address?.[field] ?? "";
  }
  return values;
}

// body for PATCH /customers/{id}, only includes what changed
// returns {} if nothing changed (the API rejects empty updates)
export function toProfileUpdatePayload(original, values) {
  const before = customerToValues(original);
  const changed = (field) => text(values, field) !== text(before, field);
  const payload = {};
  for (const field of ["name", "phone"]) {
    if (changed(field)) payload[field] = text(values, field);
  }
  const address = {};
  for (const field of ADDRESS_FIELDS) {
    if (changed(`delivery_address.${field}`)) address[field] = text(values, `delivery_address.${field}`);
  }
  if (Object.keys(address).length > 0) payload.delivery_address = address;
  return payload;
}

// sign-in answers 401 for wrong credentials and 403 for a deactivated account
export function signInErrorMessage(error) {
  if (error instanceof ApiError && error.status === 401) return "Email or password is incorrect.";
  if (error instanceof ApiError && error.status === 403) return "This account has been deactivated.";
  return error.message;
}

function text(values, field) {
  return String(values[field] ?? "").trim();
}
