from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json, update_json, write_json
from app.schemas.menu import MenuItemCreate, MenuItemRead


def list_all():
    return read_json(get_data_dir() / "products.json")


def create(restaurant_id: int, fields: dict) -> dict:
    """Validate products, allocate an ID and append in one transaction."""
    fields = MenuItemCreate.model_validate(fields, strict=True).model_dump()

    def append(records):
        TypeAdapter(list[MenuItemRead]).validate_python(records, strict=True)
        for record in records:
            MenuItemCreate.model_validate(record, strict=True)
        ids = [record["product_id"] for record in records]
        if any(identifier <= 0 for identifier in ids):
            raise ValueError("Stored product IDs must be positive integers")
        if len(set(ids)) != len(ids):
            raise ValueError("Stored product IDs must be unique")
        created = {**fields, "product_id": max(ids, default=0) + 1,
                   "restaurant_id": restaurant_id}
        MenuItemRead.model_validate(created, strict=True)
        return [*records, created], created

    return update_json(get_data_dir() / "products.json", append)


def save_all(products):
    write_json(get_data_dir() / "products.json", products)
