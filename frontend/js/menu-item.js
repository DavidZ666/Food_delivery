import { apiRequest } from "./api.js";

const heading = document.querySelector("#item-name");
const status = document.querySelector("#item-status");
const details = document.querySelector("#item-details");
const image = document.querySelector("#item-image");
const backLink = document.querySelector("#back-link");
const params = new URLSearchParams(window.location.search);
const restaurantId = params.get("restaurantId");
const productId = params.get("productId");
const validId = (value) => /^[1-9]\d*$/.test(value ?? "");

function addDetail(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  details.append(term, description);
}

async function loadItem() {
  if (validId(restaurantId)) {
    backLink.href = `restaurant.html?id=${encodeURIComponent(restaurantId)}`;
    backLink.textContent = "Back to restaurant menu";
  }
  if (!validId(restaurantId) || !validId(productId)) {
    status.textContent = "Invalid or missing restaurant or menu item ID.";
    return;
  }
  status.textContent = "Loading menu item...";
  details.setAttribute("aria-busy", "true");
  try {
    const item = await apiRequest(
      `/restaurants/${encodeURIComponent(restaurantId)}/menu/${encodeURIComponent(productId)}`
    );
    if (!item || typeof item.name !== "string" || !Number.isFinite(item.price) ||
        String(item.restaurant_id) !== restaurantId || String(item.product_id) !== productId) {
      throw new Error("The server returned invalid menu item details.");
    }
    heading.textContent = item.name;
    document.title = `${item.name} — ByteBites`;
    addDetail("Description", item.description || "Not provided");
    addDetail("Category", item.category);
    addDetail("Price", `$${item.price.toFixed(2)}`);
    addDetail("Availability", item.is_available ? "Available" : "Unavailable");
    // An optional image must not prevent the item's text from being shown.
    if (item.image) {
      try {
        const url = new URL(item.image, window.location.href);
        if (["http:", "https:"].includes(url.protocol)) {
          image.alt = item.name;
          image.addEventListener("error", () => { image.hidden = true; });
          image.hidden = false;
          image.src = url.href;
        }
      } catch { /* Leave malformed image URLs hidden. */ }
    }
    status.textContent = "";
  } catch (error) {
    details.replaceChildren();
    image.hidden = true;
    status.textContent = error.message;
  } finally {
    details.setAttribute("aria-busy", "false");
  }
}

loadItem();
