import { apiRequest } from "./api.js";
import { getCustomer, getToken } from "./session.js";

// Request/state logic. Dependencies are injectable for Node tests.
export function createCartController({
  customerId,
  request = apiRequest,
  render,
  showStatus,
  setBusy,
  onDenied = () => {},
}) {
  const base = `/customers/${customerId}/cart`;
  let busy = false;
  let ready = false;
  let denied = false;

  async function run(operation, message) {
    if (busy || denied) return false;

    busy = true;
    setBusy(true, ready);
    showStatus("Updating cart...");

    try {
      const cart = await operation();
      render(cart);
      ready = true;
      showStatus(message);
      return true;
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        denied = true;
        ready = false;
        onDenied();
      }

      showStatus(error.message || "Could not update the cart.", true);
      return false;
    } finally {
      busy = false;
      setBusy(false, ready && !denied);
    }
  }

  return {
    load() {
      return run(async () => {
        try {
          return await request(base);
        } catch (error) {
          // Only create when the API explicitly says the cart is missing.
          if (error.status !== 404 || error.detail !== "Cart not found") {
            throw error;
          }
          return request(base, { method: "POST" });
        }
      }, "");
    },

    add(productId) {
      if (!ready) return Promise.resolve(false);
      return run(
        () => request(`${base}/items`, {
          method: "POST",
          body: { product_id: productId, quantity: 1 },
        }),
        "Item added to your cart."
      );
    },

    update(productId, quantity) {
      if (!ready) return Promise.resolve(false);

      if (!Number.isSafeInteger(quantity) || quantity < 1) {
        showStatus("Quantity must be a positive whole number.", true);
        return Promise.resolve(false);
      }

      return run(
        () => request(`${base}/items/${productId}`, {
          method: "PATCH",
          body: { quantity },
        }),
        "Quantity updated."
      );
    },

    remove(productId) {
      if (!ready) return Promise.resolve(false);
      return run(
        () => request(`${base}/items/${productId}`, { method: "DELETE" }),
        "Item removed."
      );
    },

    clear() {
      if (!ready) return Promise.resolve(false);
      return run(
        () => request(`${base}/items`, { method: "DELETE" }),
        "Cart cleared."
      );
    },
  };
}

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
  const addButtons = [];
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
    addButton(item) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.is_available ? "Add to cart" : "Unavailable";
      button.setAttribute("aria-label", `Add ${item.name} to cart`);

      addButtons.push({
        button,
        available: item.is_available === true,
      });

      button.addEventListener("click", () => {
        if (controller) void controller.add(item.product_id);
      });

      syncControls();
      return button;
    },
  };
}