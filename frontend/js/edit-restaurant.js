// edit restaurant form (#51)
import { ApiError, apiRequest } from "./api.js";
import { createFormUi } from "./form-ui.js";
import {
  fieldErrorsFromDetail,
  restaurantToValues,
  toUpdatePayload,
  validateRestaurantForm,
} from "./restaurant-form.js";

const picker = document.querySelector("#restaurant-picker");
const pickerStatus = document.querySelector("#picker-status");
const form = document.querySelector("#restaurant-form");
const heading = document.querySelector("#editing-heading");
const submitButton = form.querySelector("button[type=submit]");
const ui = createFormUi(form, document.querySelector("#form-status"));

// last version we got from the API, used to figure out what changed
let original = null;
// so a slow response doesn't overwrite a restaurant picked after it
let latestLoad = 0;

picker.addEventListener("change", () => {
  const id = picker.value;
  history.replaceState(null, "", id ? `?id=${encodeURIComponent(id)}` : location.pathname);
  if (id) {
    loadRestaurant(id);
  } else {
    showPickerStatus("", "");
    hideForm();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearErrors();

  const values = Object.fromEntries(new FormData(form));
  const errors = validateRestaurantForm(values);
  if (Object.keys(errors).length > 0) {
    ui.showFieldErrors(errors);
    ui.showStatus("Please fix the highlighted fields.", "error");
    return;
  }
  const changes = toUpdatePayload(original, values);
  if (Object.keys(changes).length === 0) {
    ui.showStatus("No changes to save.", "info");
    return;
  }

  setPending(true);
  try {
    const updated = await apiRequest(`/restaurants/${original.id}`, {
      method: "PATCH",
      body: changes,
    });
    fillForm(updated);
    renamePickerOption(updated);
    ui.showStatus(`Saved changes to "${updated.name}".`, "success");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 404) {
      ui.showStatus("This restaurant no longer exists, so the changes were not saved.", "error");
    } else {
      const unplaced = ui.showFieldErrors(fieldErrorsFromDetail(error.detail));
      ui.showStatus([error.message, ...unplaced].join(" "), "error");
    }
  } finally {
    setPending(false);
  }
});

loadPicker();

async function loadPicker() {
  const requestedId = new URLSearchParams(location.search).get("id");
  showPickerStatus("Loading restaurants…", "pending");
  try {
    const restaurants = await apiRequest("/restaurants");
    for (const restaurant of restaurants) {
      const option = document.createElement("option");
      option.value = String(restaurant.id);
      option.textContent = optionLabel(restaurant);
      picker.append(option);
    }
    showPickerStatus(restaurants.length === 0 ? "There are no restaurants to edit yet." : "", "info");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    showPickerStatus(`Could not load restaurants. ${error.message}`, "error");
  }
  if (requestedId) {
    picker.value = requestedId;
    await loadRestaurant(requestedId);
  }
}

async function loadRestaurant(id) {
  const load = ++latestLoad;
  hideForm();
  showPickerStatus("Loading restaurant…", "pending");
  try {
    const restaurant = await apiRequest(`/restaurants/${encodeURIComponent(id)}`);
    if (load !== latestLoad) return;
    fillForm(restaurant);
    form.hidden = false;
    showPickerStatus("", "");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (load !== latestLoad) return;
    if (error.status === 404) {
      showPickerStatus(`No restaurant has ID ${id}.`, "error");
    } else if (error.status === 422) {
      showPickerStatus("Restaurant IDs are whole numbers.", "error");
    } else {
      showPickerStatus(`Could not load the restaurant. ${error.message}`, "error");
    }
  }
}

function fillForm(restaurant) {
  original = restaurant;
  for (const [name, value] of Object.entries(restaurantToValues(restaurant))) {
    const input = form.elements.namedItem(name);
    if (input) input.value = value;
  }
  heading.textContent = `Editing ${restaurant.name} (ID ${restaurant.id})`;
}

function hideForm() {
  original = null;
  form.hidden = true;
  ui.clearErrors();
  ui.showStatus("", "");
}

function renamePickerOption(restaurant) {
  const option = picker.querySelector(`option[value="${restaurant.id}"]`);
  if (option) option.textContent = optionLabel(restaurant);
}

function optionLabel(restaurant) {
  return `${restaurant.name} (ID ${restaurant.id})`;
}

function showPickerStatus(message, kind) {
  pickerStatus.textContent = message;
  pickerStatus.dataset.kind = kind;
}

function setPending(pending) {
  submitButton.disabled = pending;
  submitButton.textContent = pending ? "Saving…" : "Save changes";
  if (pending) ui.showStatus("Saving changes…", "pending");
}
