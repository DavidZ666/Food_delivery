// status/error display used by both restaurant forms
// error elements use the id "error-<input name>" e.g. "error-location.city"

export function createFormUi(form, statusMessage) {
  function showStatus(message, kind) {
    statusMessage.textContent = message;
    statusMessage.dataset.kind = kind;
  }

  // returns any errors that don't belong to an input on the page
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

  return { showStatus, showFieldErrors, clearErrors };
}
