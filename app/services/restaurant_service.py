from app.repositories import restaurant_repo
from app.schemas.restaurant import RestaurantCreate, RestaurantRead


def list_restaurants():
    return restaurant_repo.list_all()


def create_restaurant(restaurant: RestaurantCreate) -> RestaurantRead:
    return RestaurantRead.model_validate(
        restaurant_repo.create(restaurant.model_dump(mode="json"))
    )
