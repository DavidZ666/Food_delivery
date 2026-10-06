from app.repositories import restaurant_repo
from app.schemas.restaurant import RestaurantCreate, RestaurantRead


class RestaurantNotFoundError(LookupError):
    """The requested restaurant does not exist in the stored collection."""


def list_restaurants():
    return restaurant_repo.list_all()


def create_restaurant(restaurant: RestaurantCreate) -> RestaurantRead:
    return RestaurantRead.model_validate(
        restaurant_repo.create(restaurant.model_dump(mode="json"))
    )

def get_restaurant(restaurant_id: int):
    restaurant = restaurant_repo.get_by_id(restaurant_id)
    if restaurant is None:
        raise RestaurantNotFoundError("Restaurant not found")
    return restaurant
