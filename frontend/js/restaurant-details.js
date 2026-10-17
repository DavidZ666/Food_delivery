import { apiRequest } from "./api.js";

const heading = document.querySelector("#restaurant-name");
const statusMessage = document.querySelector("#restaurant-status");
const details = document.querySelector("#restaurant-details");
const restaurantId = new URLSearchParams(window.location.search).get("id");

function addDetail(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  details.append(term, description);
}

async function loadRestaurant() {
  if (!restaurantId || !/^[1-9]\d*$/.test(restaurantId)) {
    statusMessage.textContent = "Invalid or missing restaurant ID.";
    return;
  }

  statusMessage.textContent = "Loading restaurant...";
  details.setAttribute("aria-busy", "true");
  try {
    const restaurant = await apiRequest(
      `/restaurants/${encodeURIComponent(restaurantId)}`
    );
    if (!restaurant || typeof restaurant.name !== "string" || !restaurant.location) {
      throw new Error("The server returned invalid restaurant details.");
    }
    heading.textContent = restaurant.name;
    const editLink = document.querySelector("#edit-link");
    editLink.href = `edit-restaurant.html?id=${encodeURIComponent(restaurantId)}`;
    editLink.hidden = false;
    document.title = `${restaurant.name} — ByteBites`;
    addDetail("Cuisine", restaurant.cuisine);
    addDetail("Description", restaurant.description || "Not provided");
    const location = restaurant.location;
    addDetail("Address", `${location.address}, ${location.city}, ` +
      `${location.province} ${location.postal_code}`);
    const days = ["monday", "tuesday", "wednesday", "thursday",
      "friday", "saturday", "sunday"];
    for (const day of days) {
      const label = day.charAt(0).toUpperCase() + day.slice(1);
      addDetail(label, restaurant.hours?.[day] || "Not provided");
    }
    statusMessage.textContent = "";
    await loadMenu();
  } catch (error) {
    details.replaceChildren();
    statusMessage.textContent = error.message;
  } finally {
    details.setAttribute("aria-busy", "false");
  }
}

async function loadMenu() {
  const section = document.querySelector("#menu-section");
  const status = document.querySelector("#menu-status");
  const list = document.querySelector("#menu-list");
  const retry = document.querySelector("#retry-menu");
  retry.hidden = true;
  section.hidden = false;
  list.replaceChildren();
  list.setAttribute("aria-busy", "true");
  status.textContent = "Loading menu...";
  try {
    const items = await apiRequest(`/restaurants/${encodeURIComponent(restaurantId)}/menu`);
    if (!Array.isArray(items)) throw new Error("The server returned an invalid menu.");
    for (const item of items) {
      const row = document.createElement("li");
      const title = document.createElement("h3");
      const link = document.createElement("a");
      const params = new URLSearchParams({ restaurantId, productId: item.product_id });
      link.href = `menu-item.html?${params}`;
      link.textContent = item.name;
      title.append(link);
      const summary = document.createElement("p");
      summary.textContent = `${item.category} · $${item.price.toFixed(2)} · ` +
        (item.is_available ? "Available" : "Unavailable");
      row.append(title, summary);
      list.append(row);
    }
    status.textContent = items.length ? `${items.length} menu item(s).` : "No menu items available.";
  } catch (error) {
    list.replaceChildren();
    status.textContent = error.message;
    retry.hidden = false;
  } finally {
    list.setAttribute("aria-busy", "false");
  }
}

document.querySelector("#retry-menu").addEventListener("click", loadMenu);
loadRestaurant();
