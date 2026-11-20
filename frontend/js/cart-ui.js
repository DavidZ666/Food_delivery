// DOM bindings for the cart panel on restaurant.html. Request and state logic
// lives in the DOM-free cart.js so Node tests can import it directly.

import { createCartController } from "./cart.js";
import { getCustomer, getToken } from "./session.js";

export function mountCart() {
  const section = document.querySelector("#cart-section");
  const status = document.querySelector("#cart-status");
  const signIn = document.querySelector("#cart-sign-in");
  const retry = document.querySelector("#cart-retry");
  const content = document.querySelector("#cart-content");
  const list = document.querySelector("#cart-items");
  const empty = document.querySelector("#cart-empty");
  const clear = document.querySelector("#cart-clear");
  const restaurant = document.querySelector("#cart-restaurant");
  const subtotal = document.querySelector("#cart-subtotal");
  const total = document.querySelector("#cart-total");

  const customer = getCustomer();
  let addButtons = [];
  let busy = false;
  let ready = false;
  let currentCart = null;
  let controller = null;

  // Formatting only: all amounts come from the backend.
  const money = (value) => `$${value.toFixed(2)}`;

  function syncControls() {
    for (const { button, available } of addButtons) {
      button.disabled = busy || !ready || !available;
    }

    for (const control of list.querySelectorAll("input, button")) {
      control.disabled = busy || !ready;
    }

    clear.disabled = busy || !ready || !currentCart?.items.length;
    retry.disabled = busy;
    section.setAttribute("aria-busy", String(busy));
  }

  function showStatus(message, isError = false) {
    status.textContent = message;
    status.dataset.kind = isError ? "error" : "info";
  }

  function render(cart) {
    currentCart = cart;
    content.hidden = false;
    list.replaceChildren();
    empty.hidden = cart.items.length !== 0;

    restaurant.textContent = cart.restaurant_id === null
      ? ""
      : `Cart restaurant: #${cart.restaurant_id}. Items must come from one restaurant.`;

    subtotal.textContent = money(cart.subtotal);
    total.textContent = money(cart.total);

    for (const item of cart.items) {
      const row = document.createElement("li");

      const title = document.createElement("p");
      title.textContent =
        `${item.name} — ${money(item.unit_price)} each` +
        ` — Line total: ${money(item.line_total)}`;

      const form = document.createElement("form");
      const label = document.createElement("label");
      label.textContent = `Quantity for ${item.name}: `;

      const quantity = document.createElement("input");
      quantity.type = "number";
      quantity.min = "1";
      quantity.step = "1";
      quantity.required = true;
      quantity.value = String(item.quantity);
      label.append(quantity);

      const update = document.createElement("button");
      update.type = "submit";
      update.textContent = "Update quantity";

      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${item.name}`);

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (form.reportValidity()) {
          void controller.update(item.product_id, quantity.valueAsNumber);
        }
      });

      remove.addEventListener("click", () => {
        void controller.remove(item.product_id);
      });

      form.append(label, update, remove);
      row.append(title, form);
      list.append(row);
    }
  }

  if (getToken() && customer?.role === "customer") {
    retry.hidden = false;

    controller = createCartController({
      customerId: customer.id,
      render,
      showStatus,
      setBusy(nextBusy, nextReady) {
        busy = nextBusy;
        ready = nextReady;
        syncControls();
      },
      onDenied() {
        currentCart = null;
        content.hidden = true;
        list.replaceChildren();
        signIn.hidden = false;
        retry.hidden = true;
      },
    });

    retry.addEventListener("click", () => void controller.load());
    clear.addEventListener("click", () => void controller.clear());
    void controller.load();
  } else {
    signIn.hidden = false;
    showStatus("A signed-in customer account is required.");
  }

  return {
    // Call whenever the menu list is rebuilt so detached buttons are dropped.
    resetAddButtons() {
      addButtons = [];
    },

    addButton(item) {
      const available = item.is_available === true;
      const button = document.createElement("button");
      button.type = "button";
      // The accessible name starts with the visible text (WCAG 2.5.3).
      button.textContent = available ? "Add to cart" : "Unavailable";
      button.setAttribute(
        "aria-label",
        available ? `Add to cart: ${item.name}` : `Unavailable: ${item.name}`
      );

      addButtons.push({ button, available });

      button.addEventListener("click", () => {
        if (controller) void controller.add(item.product_id);
      });

      syncControls();
      return button;
    },
  };
}
