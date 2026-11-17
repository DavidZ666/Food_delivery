// profile, delivery address, sign out and deactivation (#95)
import { ApiError, apiRequest } from "./api.js";
import { customerToValues, toProfileUpdatePayload, validateProfile } from "./account-form.js";
import { createFormUi } from "./form-ui.js";
import { fieldErrorsFromDetail } from "./restaurant-form.js";
import { clearSession, getCustomer, getToken, saveCustomer } from "./session.js";

const signedOut = document.querySelector("#signed-out");
const account = document.querySelector("#account");
const pageStatus = document.querySelector("#account-status");
const form = document.querySelector("#profile-form");
const saveButton = form.querySelector("button[type=submit]");
const deactivateButton = document.querySelector("#deactivate");
const ui = createFormUi(form, document.querySelector("#form-status"));

// last version we got from the API, used to figure out what changed
let original = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!original || saveButton.disabled) return;
  ui.clearErrors();

  const values = Object.fromEntries(new FormData(form));
  const errors = validateProfile(values);
  if (Object.keys(errors).length > 0) {
    ui.showFieldErrors(errors);
    ui.showStatus("Please fix the highlighted fields.", "error");
    return;
  }
  const changes = toProfileUpdatePayload(original, values);
  if (Object.keys(changes).length === 0) {
    ui.showStatus("No changes to save.", "info");
    return;
  }

  saveButton.disabled = true;
  ui.showStatus("Saving…", "pending");
  try {
    showCustomer(await apiRequest(`/customers/${original.id}`, { method: "PATCH", body: changes }));
    ui.showStatus("Saved your profile.", "success");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (!showSignedOutIfRejected(error)) {
      const unplaced = ui.showFieldErrors(fieldErrorsFromDetail(error.detail));
      ui.showStatus([error.message, ...unplaced].join(" "), "error");
    }
  } finally {
    saveButton.disabled = false;
  }
});

document.querySelector("#sign-out").addEventListener("click", () => {
  clearSession();
  location.href = "sign-in.html?signed-out=1";
});

deactivateButton.addEventListener("click", async () => {
  if (!original) return;
  if (!confirm("Deactivate your account? You will not be able to sign in again.")) return;
  deactivateButton.disabled = true;
  try {
    await apiRequest(`/customers/${original.id}/deactivate`, { method: "POST" });
    clearSession();
    location.href = "sign-in.html?deactivated=1";
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (!showSignedOutIfRejected(error)) ui.showStatus(error.message, "error");
    deactivateButton.disabled = false;
  }
});

load();

async function load() {
  const session = getToken() ? getCustomer() : null;
  if (!session) {
    showSignedOut("");
    return;
  }
  showStatus("Loading your account…", "pending");
  try {
    showCustomer(await apiRequest(`/customers/${session.id}`));
    showStatus("", "");
    account.hidden = false;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (!showSignedOutIfRejected(error)) showStatus(error.message, "error");
  }
}

function showCustomer(customer) {
  original = customer;
  saveCustomer(customer);
  document.querySelector("#account-email").textContent = customer.email;
  for (const [name, value] of Object.entries(customerToValues(customer))) {
    form.elements.namedItem(name).value = value;
  }
}

// 401 and 403 mean this session can no longer use the account
function showSignedOutIfRejected(error) {
  if (error.status !== 401 && error.status !== 403) return false;
  clearSession();
  showSignedOut(error.message);
  return true;
}

function showSignedOut(message) {
  original = null;
  account.hidden = true;
  signedOut.hidden = false;
  showStatus(message, message ? "error" : "");
}

function showStatus(message, kind) {
  pageStatus.textContent = message;
  pageStatus.dataset.kind = kind;
}
