import { ApiError, apiRequest } from "./api.js";
import { INVALID_ORDER, isOrder } from "./orders.js";

const INVALID_CART = "The server returned an invalid cart.";
const GENERIC_FAILURE = "Could not update the cart.";

const isAmount = (value) => typeof value === "number" && Number.isFinite(value);

function isCartItem(item) {
  return item !== null && typeof item === "object" &&
    Number.isSafeInteger(item.product_id) &&
    typeof item.name === "string" &&
    Number.isSafeInteger(item.quantity) &&
    isAmount(item.unit_price) &&
    isAmount(item.line_total);
}

// Check the response before rendering so a malformed body cannot leave a
// half-drawn cart on the page.
export function isCart(cart) {
  return cart !== null && typeof cart === "object" &&
    (cart.restaurant_id === null || Number.isSafeInteger(cart.restaurant_id)) &&
    Array.isArray(cart.items) && cart.items.every(isCartItem) &&
    isAmount(cart.subtotal) &&
    isAmount(cart.total);
}

// Request/state logic. Dependencies are injectable for Node tests.
export function createCartController({
  customerId,
  request = apiRequest,
  render,
  showStatus,
  setBusy,
  onDenied = () => {},
  onOrder = () => {},
}) {
  const base = `/customers/${customerId}/cart`;
  let busy = false;
  let ready = false;
  let denied = false;

  async function fetchCart() {
    let cart;
    try {
      cart = await request(base);
    } catch (error) {
      // Only create when the API explicitly says the cart is missing.
      if (error.status !== 404 || error.detail !== "Cart not found") {
        throw error;
      }
      cart = await request(base, { method: "POST" });
    }
    return checked(cart);
  }

  function checked(cart) {
    if (!isCart(cart)) throw new ApiError(INVALID_CART);
    return cart;
  }

  function deny() {
    denied = true;
    ready = false;
    onDenied();
  }

  // A 404 on a mutation means the displayed cart no longer matches the server
  // (for example, it was checked out in another tab), so redraw it from a
  // fresh read. If that read also fails, require an explicit reload.
  async function resync() {
    try {
      render(await fetchCart());
    } catch (error) {
      ready = false;
      if (error.status === 401 || error.status === 403) deny();
    }
  }

  async function run(operation, message, { resyncOnNotFound = true } = {}) {
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
        deny();
      } else if (error.status === 404 && resyncOnNotFound) {
        await resync();
      } else if (!(error instanceof ApiError)) {
        ready = false;
      }

      showStatus(
        error instanceof ApiError && error.message ? error.message : GENERIC_FAILURE,
        true
      );
      return false;
    } finally {
      busy = false;
      setBusy(false, ready && !denied);
    }
  }

  function mutate(path, options, message) {
    if (!ready) return Promise.resolve(false);
    return run(async () => checked(await request(path, options)), message);
  }

  return {
    load() {
      return run(fetchCart, "", { resyncOnNotFound: false });
    },

    add(productId) {
      return mutate(
        `${base}/items`,
        { method: "POST", body: { product_id: productId, quantity: 1 } },
        "Item added to your cart."
      );
    },

    update(productId, quantity) {
      if (!ready) return Promise.resolve(false);

      if (!Number.isSafeInteger(quantity) || quantity < 1) {
        showStatus("Quantity must be a positive whole number.", true);
        return Promise.resolve(false);
      }

      return mutate(
        `${base}/items/${productId}`,
        { method: "PATCH", body: { quantity } },
        "Quantity updated."
      );
    },

    remove(productId) {
      return mutate(`${base}/items/${productId}`, { method: "DELETE" }, "Item removed.");
    },

    clear() {
      return mutate(`${base}/items`, { method: "DELETE" }, "Cart cleared.");
    },

    // checkout (#97): the backend rechecks the menu and saves the order, then
    // we show the order and reload the cart (it's empty after a checkout)
    checkout() {
      if (!ready) return Promise.resolve(false);
      return run(async () => {
        let order;
        try {
          order = await request(`/customers/${customerId}/checkout`, { method: "POST" });
        } catch (error) {
          // 409 means the cart didn't pass the recheck (item unavailable, empty
          // cart). nothing was saved, so the cart on screen is still right
          if (error.status === 409) {
            throw new ApiError(`Checkout failed: ${error.message}. Your cart was not changed.`,
              { status: 409, detail: error.detail });
          }
          throw error;
        }
        if (!isOrder(order)) throw new ApiError(INVALID_ORDER);
        onOrder(order);
        try {
          return await fetchCart();
        } catch (error) {
          // the order is saved, only the refresh failed. say so, and stop the
          // old cart on screen from being used until Reload cart works
          ready = false;
          throw new ApiError(
            `Order #${order.order_id} placed, but the cart could not be reloaded. Reload the cart to continue.`,
            { status: error.status ?? null, detail: error.detail ?? null });
        }
      }, "Order placed.");
    },
  };
}
