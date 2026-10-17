import { apiRequest } from "./api.js";

const restaurantList = document.querySelector("#restaurant-list");
const statusMessage = document.querySelector("#restaurant-status");
const searchForm = document.querySelector("#restaurant-search");
const cuisineSelect = document.querySelector("#cuisine");
const searchButton = searchForm.querySelector('button[type="submit"]');

let latestRequest = 0;
let cuisinesLoaded = false;

function populateCuisines(restaurants) {
  const cuisines = [...new Set(
    restaurants.map((restaurant) => restaurant.cuisine)
  )].sort((a, b) => a.localeCompare(b));

  cuisineSelect.replaceChildren(new Option("All cuisines", ""));

  for (const cuisine of cuisines) {
    cuisineSelect.add(new Option(cuisine, cuisine));
  }
}

function renderRestaurants(restaurants) {
  restaurantList.replaceChildren();

  for (const restaurant of restaurants) {
    const item = document.createElement("li");

    const name = document.createElement("h3");
    const link = document.createElement("a");
    link.href = `restaurant.html?id=${encodeURIComponent(restaurant.id)}`;
    link.textContent = restaurant.name;
    name.append(link);

    const cuisine = document.createElement("p");
    cuisine.textContent = `Cuisine: ${restaurant.cuisine}`;

    const address = document.createElement("p");
    const location = restaurant.location;
    address.textContent =
      `${location.address}, ${location.city}, ` +
      `${location.province} ${location.postal_code}`;

    item.append(name, cuisine, address);
    restaurantList.append(item);
  }
}

async function loadRestaurants() {
  const requestId = ++latestRequest;
  const values = new FormData(searchForm);
  const params = new URLSearchParams();

  const name = String(values.get("name") ?? "").trim();
  const cuisine = String(values.get("cuisine") ?? "").trim();

  if (name) params.set("name", name);
  if (cuisine) params.set("cuisine", cuisine);

  const query = params.toString();
  const path = query ? `/restaurants?${query}` : "/restaurants";

  statusMessage.textContent = "Loading restaurants...";
  restaurantList.replaceChildren();
  searchButton.disabled = true;
  restaurantList.setAttribute("aria-busy", "true");

  try {
    // Retry the full catalogue after an initial failure so cuisine choices
    // remain complete even if the user retries with a name search.
    if (!cuisinesLoaded) {
      const allRestaurants = await apiRequest("/restaurants");
      if (requestId !== latestRequest) return;
      if (!Array.isArray(allRestaurants)) {
        throw new Error("The server returned an invalid restaurant list.");
      }
      populateCuisines(allRestaurants);
      cuisinesLoaded = true;
      if (!query) {
        renderRestaurants(allRestaurants);
        statusMessage.textContent = allRestaurants.length
          ? `${allRestaurants.length} restaurant(s) found.`
          : "No restaurants available.";
        return;
      }
    }
    const restaurants = await apiRequest(path);

    // Ignore an older response if a newer request has started.
    if (requestId !== latestRequest) return;

    if (!Array.isArray(restaurants)) {
      throw new Error("The server returned an invalid restaurant list.");
    }

    renderRestaurants(restaurants);

    if (restaurants.length === 0) {
      statusMessage.textContent = query
        ? "No restaurants match your search."
        : "No restaurants available.";
    } else {
      statusMessage.textContent =
        `${restaurants.length} restaurant(s) found.`;
    }
  } catch (error) {
    if (requestId !== latestRequest) return;
    restaurantList.replaceChildren();
    statusMessage.textContent = error.message;
  } finally {
    if (requestId === latestRequest) {
      searchButton.disabled = false;
      restaurantList.setAttribute("aria-busy", "false");
    }
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadRestaurants();
});

loadRestaurants();
