// registration form (#95)
import { ApiError, apiRequest } from "./api.js";
import { toRegistrationPayload, validateRegistration } from "./account-form.js";
import { createFormUi } from "./form-ui.js";
import { fieldErrorsFromDetail } from "./restaurant-form.js";

const form = document.querySelector("#register-form");
const submitButton = form.querySelector("button[type=submit]");
const ui = createFormUi(form, document.querySelector("#form-status"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearErrors();

  const values = Object.fromEntries(new FormData(form));
  const errors = validateRegistration(values);
  if (Object.keys(errors).length > 0) {
    ui.showFieldErrors(errors);
    ui.showStatus("Please fix the highlighted fields.", "error");
    return;
  }

  submitButton.disabled = true;
  ui.showStatus("Creating account…", "pending");
  try {
    await apiRequest("/customers", { method: "POST", body: toRegistrationPayload(values) });
    location.href = "sign-in.html?registered=1";
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (error.status === 409) {
      ui.showFieldErrors({ email: "This email is already registered." });
      ui.showStatus("Please fix the highlighted fields.", "error");
    } else {
      const unplaced = ui.showFieldErrors(fieldErrorsFromDetail(error.detail));
      ui.showStatus([error.message, ...unplaced].join(" "), "error");
    }
    submitButton.disabled = false;
  }
});
