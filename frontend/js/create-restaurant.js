// create restaurant form (#50)
import { ApiError, apiRequest } from "./api.js";
import { createFormUi } from "./form-ui.js";
import {
  WEEKDAYS,
  fieldErrorsFromDetail,
  toCreatePayload,
  validateRestaurantForm,
} from "./restaurant-form.js";

const form = document.querySelector("#restaurant-form");
const submitButton = form.querySelector("button[type=submit]");
const created = document.querySelector("#created-restaurant");
const ui = createFormUi(form, document.querySelector("#form-status"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearErrors();
  created.hidden = true;

  const values = Object.fromEntries(new FormData(form));
  const errors = validateRestaurantForm(values);
  if (Object.keys(errors).length > 0) {
    ui.showFieldErrors(errors);
    ui.showStatus("Please fix the highlighted fields.", "error");
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
    ui.showStatus(`Created "${restaurant.name}" with ID ${restaurant.id}.`, "success");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    const unplaced = ui.showFieldErrors(fieldErrorsFromDetail(error.detail));
    ui.showStatus([error.message, ...unplaced].join(" "), "error");
  } finally {
    setPending(false);
  }
});

function setPending(pending) {
  submitButton.disabled = pending;
  submitButton.textContent = pending ? "Saving…" : "Create restaurant";
  if (pending) ui.showStatus("Saving restaurant…", "pending");
}

// show what the API actually saved
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
  created.querySelector("#edit-created").href = `edit-restaurant.html?id=${restaurant.id}`;
  created.hidden = false;
}

function capitalize(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}
