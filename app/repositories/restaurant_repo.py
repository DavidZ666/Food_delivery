from app.core.config import get_data_dir
from app.repositories.json_store import read_json


def list_all():
    file_path = get_data_dir() / "restaurants.json"
    return read_json(file_path)


def get_by_id(restaurant_id: int):
    """Read a stored restaurant, or return None when its ID is absent."""
    return next(
        (restaurant for restaurant in list_all() if restaurant["id"] == restaurant_id),
        None,
    )
