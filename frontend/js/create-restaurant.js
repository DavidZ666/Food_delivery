// Wires the restaurant creation form (#50) to POST /restaurants.
import { ApiError, apiRequest } from "./api.js";
import {
  WEEKDAYS,
  fieldErrorsFromDetail,
  toCreatePayload,
  validateRestaurantForm,
} from "./restaurant-form.js";

const form = document.querySelector("#restaurant-form");
const submitButton = form.querySelector("button[type=submit]");
const statusMessage = document.querySelector("#form-status");
const created = document.querySelector("#created-restaurant");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  created.hidden = true;

  const values = Object.fromEntries(new FormData(form));
  const errors = validateRestaurantForm(values);
  if (Object.keys(errors).length > 0) {
    showFieldErrors(errors);
    showStatus("Please fix the highlighted fields.", "error");
    return;
  }

  setPending(true);
  try {
    const restaurant = await apiRequest("/restaurants", {
      method: "POST",
      body: toCreatePayload(values),
    });
    showCreated(restaurant);
    form.reset();
    showStatus(`Created "${restaurant.name}" with ID ${restaurant.id}.`, "success");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    const unplaced = showFieldErrors(fieldErrorsFromDetail(error.detail));
    showStatus([error.message, ...unplaced].join(" "), "error");
  } finally {
    setPending(false);
  }
});

function setPending(pending) {
  submitButton.disabled = pending;
  submitButton.textContent = pending ? "Saving…" : "Create restaurant";
  if (pending) showStatus("Saving restaurant…", "pending");
}

function showStatus(message, kind) {
  statusMessage.textContent = message;
  statusMessage.dataset.kind = kind;
}

// Shows each error next to its input. Returns messages with no matching input.
function showFieldErrors(errors) {
  const unplaced = [];
  for (const [field, message] of Object.entries(errors)) {
    const input = field ? form.elements.namedItem(field) : null;
    const errorElement = document.getElementById(`error-${field}`);
    if (input && errorElement) {
      input.setAttribute("aria-invalid", "true");
      errorElement.textContent = message;
    } else {
      unplaced.push(field ? `${field}: ${message}` : message);
    }
  }
  return unplaced;
}

function clearErrors() {
  for (const input of form.querySelectorAll("[aria-invalid]")) {
    input.removeAttribute("aria-invalid");
  }
  for (const element of form.querySelectorAll(".field-error")) {
    element.textContent = "";
  }
}

// Renders the restaurant returned by the API, not the submitted form values.
function showCreated(restaurant) {
  const location = restaurant.location;
  const rows = [
    ["ID", restaurant.id],
    ["Name", restaurant.name],
    ["Cuisine", restaurant.cuisine],
    ["Address", `${location.address}, ${location.city}, ${location.province} ${location.postal_code}`],
    ["Description", restaurant.description ?? "—"],
    ["Logo URL", restaurant.logo_url ?? "—"],
  ];
  for (const day of WEEKDAYS) {
    if (restaurant.hours?.[day]) rows.push([capitalize(day), restaurant.hours[day]]);
  }

  const list = created.querySelector("dl");
  list.replaceChildren();
  for (const [label, value] of rows) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = String(value);
    list.append(term, description);
  }
  created.hidden = false;
}

function capitalize(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}
