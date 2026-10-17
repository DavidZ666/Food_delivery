from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json, update_json
from app.schemas.menu import MenuItemCreate, MenuItemRead, MenuItemUpdate


class ProductRecordNotFoundError(LookupError):
    pass


def _validate_records(records):
    TypeAdapter(list[MenuItemRead]).validate_python(records, strict=True)
    for record in records:
        MenuItemCreate.model_validate(record, strict=True)
    ids = [record["product_id"] for record in records]
    if any(identifier <= 0 for identifier in ids):
        raise ValueError("Stored product IDs must be positive integers")
    if len(set(ids)) != len(ids):
        raise ValueError("Stored product IDs must be unique")


def list_all():
    return read_json(get_data_dir() / "products.json")


def create(restaurant_id: int, fields: dict) -> dict:
    """Validate products, allocate an ID and append in one transaction."""
    fields = MenuItemCreate.model_validate(fields, strict=True).model_dump()

    def append(records):
        _validate_records(records)
        ids = [record["product_id"] for record in records]
        created = {**fields, "product_id": max(ids, default=0) + 1,
                   "restaurant_id": restaurant_id}
        MenuItemRead.model_validate(created, strict=True)
        return [*records, created], created

    return update_json(get_data_dir() / "products.json", append)


def update_by_id(restaurant_id: int, product_id: int, changes: dict) -> dict:
    """Preserve ownership and omitted fields in one storage transaction."""
    changes = MenuItemUpdate.model_validate(changes, strict=True).model_dump(exclude_unset=True)

    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["product_id"] == product_id and record["restaurant_id"] == restaurant_id:
                updated = {**record, **changes}
                MenuItemCreate.model_validate(updated, strict=True)
                return [*records[:index], updated, *records[index + 1:]], updated
        raise ProductRecordNotFoundError

    return update_json(get_data_dir() / "products.json", apply)


def delete_by_id(restaurant_id: int, product_id: int) -> None:
    """Remove the owned item without overwriting concurrent menu changes."""
    def remove(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["product_id"] == product_id and record["restaurant_id"] == restaurant_id:
                return [*records[:index], *records[index + 1:]], None
        raise ProductRecordNotFoundError

    update_json(get_data_dir() / "products.json", remove)
