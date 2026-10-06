from app.core.config import get_data_dir
from pydantic import TypeAdapter

from app.repositories.json_store import read_json, update_json
from app.schemas.restaurant import RestaurantRead


def list_all():
    file_path = get_data_dir() / "restaurants.json"
    return read_json(file_path)


def create(fields: dict) -> dict:
    """Allocate an ID and append a record in one storage transaction."""
    def append(records):
        TypeAdapter(list[RestaurantRead]).validate_python(records)
        ids = [record["id"] for record in records]
        if any(type(identifier) is not int or identifier <= 0 for identifier in ids):
            raise ValueError("Stored restaurant IDs must be positive integers")
        if len(set(ids)) != len(ids):
            raise ValueError("Stored restaurant IDs must be unique")
        created = {**fields, "id": max(ids, default=0) + 1}
        RestaurantRead.model_validate(created)
        return [*records, created], created

    return update_json(get_data_dir() / "restaurants.json", append)

def get_by_id(restaurant_id: int):
    """Read a stored restaurant, or return None when its ID is absent."""
    return next(
        (restaurant for restaurant in list_all() if restaurant["id"] == restaurant_id),
        None,
    )
