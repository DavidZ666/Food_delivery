from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json_array, update_json
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
    return read_json_array(get_data_dir() / "products.json")


def _highest_referenced_product_id() -> int:
    """Preserve identities still known to legacy carts and order snapshots."""
    highest = 0
    for filename in ("carts.json", "orders.json"):
        try:
            records = read_json_array(get_data_dir() / filename)
        except FileNotFoundError:
            continue
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("items"), list):
                raise ValueError(f"Stored items in {filename} must be an array")
            for item in record["items"]:
                identifier = item.get("product_id") if isinstance(item, dict) else None
                if type(identifier) is not int or identifier <= 0:
                    raise ValueError(f"Stored product references in {filename} must be positive integers")
                highest = max(highest, identifier)
    return highest


def _advance_sequence(records: list, allocate: bool) -> int:
    """Record the highest product ID ever issued in product_ids.json; optionally issue the next.

    Called inside a products transaction. The sequence is written before the
    products file, so it never falls behind a stored ID and deleted IDs are never
    reissued, even after deleting the highest or every product and restarting.
    A missing sequence starts from products and existing cart/order references.
    """
    highest = max((record["product_id"] for record in records), default=0)
    missing = object()

    def advance(document):
        if document is missing:
            document = {"last_product_id": _highest_referenced_product_id()}
        last = document.get("last_product_id") if isinstance(document, dict) else None
        if type(last) is not int or last < 0:
            raise ValueError("Stored product ID sequence must be a non-negative integer")
        last = max(last, highest) + (1 if allocate else 0)
        return {**document, "last_product_id": last}, last

    return update_json(get_data_dir() / "product_ids.json", advance, default=missing)


def create(restaurant_id: int, fields: dict) -> dict:
    """Validate products, allocate an ID and append in one transaction."""
    fields = MenuItemCreate.model_validate(fields, strict=True).model_dump()

    def append(records):
        _validate_records(records)
        created = {**fields, "product_id": _advance_sequence(records, allocate=True),
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
                _advance_sequence(records, allocate=False)
                return [*records[:index], *records[index + 1:]], None
        raise ProductRecordNotFoundError

    update_json(get_data_dir() / "products.json", remove)
