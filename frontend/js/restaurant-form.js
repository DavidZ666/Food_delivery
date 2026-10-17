// form logic for the restaurant forms. no DOM stuff in here so we can test it with node
// values use the input names, e.g. "location.city" or "hours.monday"

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

// same rule as the API, required text can't be blank
export function validateRestaurantForm(values) {
  const errors = {};
  for (const field of REQUIRED_FIELDS) {
    if (!text(values, field)) errors[field] = "This field is required.";
  }
  return errors;
}

// body for POST /restaurants, leaves out empty optional fields
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

const LOCATION_FIELDS = ["address", "city", "province", "postal_code"];

// turns a restaurant from the API into form values
export function restaurantToValues(restaurant) {
  const values = {
    name: restaurant.name ?? "",
    cuisine: restaurant.cuisine ?? "",
  };
  for (const field of OPTIONAL_TEXT_FIELDS) values[field] = restaurant[field] ?? "";
  for (const field of LOCATION_FIELDS) {
    values[`location.${field}`] = restaurant.location?.[field] ?? "";
  }
  for (const day of WEEKDAYS) values[`hours.${day}`] = restaurant.hours?.[day] ?? "";
  return values;
}

// body for PATCH, only includes what changed
// clearing an optional field sends null so the API removes it
// returns {} if nothing changed
export function toUpdatePayload(original, values) {
  const before = restaurantToValues(original);
  const changed = (field) => text(values, field) !== text(before, field);
  const payload = {};

  for (const field of ["name", "cuisine"]) {
    if (changed(field)) payload[field] = text(values, field);
  }
  for (const field of OPTIONAL_TEXT_FIELDS) {
    if (changed(field)) payload[field] = text(values, field) || null;
  }
  const location = {};
  for (const field of LOCATION_FIELDS) {
    if (changed(`location.${field}`)) location[field] = text(values, `location.${field}`);
  }
  if (Object.keys(location).length > 0) payload.location = location;
  const hours = {};
  for (const day of WEEKDAYS) {
    if (changed(`hours.${day}`)) hours[day] = text(values, `hours.${day}`) || null;
  }
  if (Object.keys(hours).length > 0) payload.hours = hours;
  return payload;
}

// turns FastAPI 422 errors into {"location.city": "message"}
// errors that aren't for a specific field go under ""
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
