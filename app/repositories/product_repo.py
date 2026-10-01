from app.core.config import get_data_dir
from app.repositories.json_store import read_json


def list_all():
    return read_json(get_data_dir() / "products.json")
