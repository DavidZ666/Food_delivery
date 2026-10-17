// Restaurant form logic with no DOM access, so it can be unit tested with
// `node --test`. Form values are keyed by input name, and nested API fields
// use dotted names such as "location.city" or "hours.monday".

export const WEEKDAYS = [
  "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
];

export const REQUIRED_FIELDS = [
  "name",
  "cuisine",
  "location.address",
  "location.city",
  "location.province",
  "location.postal_code",
];

const OPTIONAL_TEXT_FIELDS = ["description", "logo_url"];

// Mirrors the API rule: required text is trimmed and must be nonblank.
export function validateRestaurantForm(values) {
  const errors = {};
  for (const field of REQUIRED_FIELDS) {
    if (!text(values, field)) errors[field] = "This field is required.";
  }
  return errors;
}

// Builds a RestaurantCreate request body. Blank optional fields are omitted.
export function toCreatePayload(values) {
  const payload = {
    name: text(values, "name"),
    cuisine: text(values, "cuisine"),
    location: {
      address: text(values, "location.address"),
      city: text(values, "location.city"),
      province: text(values, "location.province"),
      postal_code: text(values, "location.postal_code"),
    },
  };
  for (const field of OPTIONAL_TEXT_FIELDS) {
    if (text(values, field)) payload[field] = text(values, field);
  }
  const hours = {};
  for (const day of WEEKDAYS) {
    if (text(values, `hours.${day}`)) hours[day] = text(values, `hours.${day}`);
  }
  if (Object.keys(hours).length > 0) payload.hours = hours;
  return payload;
}

// Converts a FastAPI 422 detail list into {"location.city": "message"}.
// Errors about the whole body (no field path) use the "" key.
export function fieldErrorsFromDetail(detail) {
  const errors = {};
  if (!Array.isArray(detail)) return errors;
  for (const error of detail) {
    const path = Array.isArray(error.loc) ? error.loc.slice(1).join(".") : "";
    if (!(path in errors)) errors[path] = error.msg;
  }
  return errors;
}

function text(values, field) {
  return String(values[field] ?? "").trim();
}
