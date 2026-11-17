// sign-in form (#95)
import { ApiError, apiRequest } from "./api.js";
import { signInErrorMessage, toSignInPayload, validateSignIn } from "./account-form.js";
import { createFormUi } from "./form-ui.js";
import { saveSession } from "./session.js";

const NOTICES = {
  registered: "Account created. Sign in to continue.",
  deactivated: "Your account was deactivated.",
  "signed-out": "You are signed out.",
};

const form = document.querySelector("#sign-in-form");
const submitButton = form.querySelector("button[type=submit]");
const ui = createFormUi(form, document.querySelector("#form-status"));

for (const [name, message] of Object.entries(NOTICES)) {
  if (new URLSearchParams(location.search).has(name)) ui.showStatus(message, "success");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  ui.clearErrors();

  const values = Object.fromEntries(new FormData(form));
  const errors = validateSignIn(values);
  if (Object.keys(errors).length > 0) {
    ui.showFieldErrors(errors);
    ui.showStatus("Please fix the highlighted fields.", "error");
    return;
  }

  submitButton.disabled = true;
  ui.showStatus("Signing in…", "pending");
  try {
    const session = await apiRequest("/auth/login", { method: "POST", body: toSignInPayload(values) });
    if (saveSession(session)) {
      location.href = "account.html";
      return;
    }
    ui.showStatus("Could not keep you signed in. Allow site storage in this browser and try again.", "error");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    ui.showStatus(signInErrorMessage(error), "error");
  }
  submitButton.disabled = false;
});
