from app.core.config import get_data_dir
from app.repositories.json_store import read_json


def list_all():
    file_path = get_data_dir() / "restaurants.json"
    return read_json(file_path)