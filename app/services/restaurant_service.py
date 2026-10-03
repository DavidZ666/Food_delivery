from app.repositories import restaurant_repo


class RestaurantNotFoundError(LookupError):
    """The requested restaurant does not exist in the stored collection."""


def list_restaurants():
    return restaurant_repo.list_all()


def get_restaurant(restaurant_id: int):
    restaurant = restaurant_repo.get_by_id(restaurant_id)
    if restaurant is None:
        raise RestaurantNotFoundError("Restaurant not found")
    return restaurant
