from app.repositories import restaurant_repo


class RestaurantNotFoundError(LookupError):
    """The requested restaurant does not exist in the stored collection."""


def list_restaurants(name: str | None = None):
    restaurants = restaurant_repo.list_all()
    query = name.strip().casefold() if name is not None else ""
    if not query:
        return restaurants
    return [restaurant for restaurant in restaurants
            if query in restaurant["name"].casefold()]
def get_restaurant(restaurant_id: int):
    restaurant = restaurant_repo.get_by_id(restaurant_id)
    if restaurant is None:
        raise RestaurantNotFoundError("Restaurant not found")
    return restaurant
