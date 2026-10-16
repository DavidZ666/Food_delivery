from app.repositories import restaurant_repo
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)

class RestaurantNotFoundError(LookupError):
    """The requested restaurant does not exist in the stored collection."""


def list_restaurants(name: str | None = None):
    restaurants = restaurant_repo.list_all()
    query = name.strip().casefold() if name is not None else ""
    if not query:
        return restaurants
    return [
        restaurant for restaurant in restaurants
        if query in restaurant["name"].casefold()
    ]


def create_restaurant(restaurant: RestaurantCreate) -> RestaurantRead:
    return RestaurantRead.model_validate(
        restaurant_repo.create(restaurant.model_dump(mode="json"))
    )


def get_restaurant(restaurant_id: int):
    restaurant = restaurant_repo.get_by_id(restaurant_id)
    if restaurant is None:
        raise RestaurantNotFoundError("Restaurant not found")
    return restaurant

def update_restaurant(
    restaurant_id: int,
    restaurant: RestaurantUpdate,
) -> dict:

    changes = restaurant.model_dump(
        mode="json",
        exclude_unset=True,
    )

    try:
        return restaurant_repo.update_by_id(
            restaurant_id,
            changes,
        )
    except restaurant_repo.RestaurantRecordNotFoundError as exc:
        raise RestaurantNotFoundError(
            "Restaurant not found"
        ) from exc
