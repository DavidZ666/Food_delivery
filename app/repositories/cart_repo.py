from math import isfinite

from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json_array, update_json
from app.schemas.cart import CartRead, CartRecord


class CartNotFoundError(LookupError):
    pass


class ActiveCartExistsError(ValueError):
    pass


_MUTABLE_FIELDS = {"restaurant_id", "items"}


def _path():
    return get_data_dir() / "carts.json"


def _validate_records(records) -> None:
    """Reject malformed storage before reads or writes rely on it."""
    validated = TypeAdapter(list[CartRecord]).validate_python(records, strict=True)
    cart_ids = [cart.cart_id for cart in validated]
    if len(set(cart_ids)) != len(cart_ids):
        raise ValueError("Stored cart IDs must be unique")
    customer_ids = [cart.customer_id for cart in validated]
    if len(set(customer_ids)) != len(customer_ids):
        raise ValueError("Each customer may have at most one active cart")


def list_all() -> list[dict]:
    records = read_json_array(_path())
    _validate_records(records)
    return records


def get_by_id(cart_id: int) -> dict | None:
    return next((r for r in list_all() if r["cart_id"] == cart_id), None)


def get_by_customer_id(customer_id: int) -> dict | None:
    return next((r for r in list_all() if r["customer_id"] == customer_id), None)


def create(customer_id: int) -> dict:
    """Check the one-cart rule, allocate an ID and append in one transaction."""
    def append(records):
        _validate_records(records)
        if any(record["customer_id"] == customer_id for record in records):
            raise ActiveCartExistsError("Customer already has an active cart")
        cart_id = max((record["cart_id"] for record in records), default=0) + 1
        created = CartRecord.model_validate(
            {"cart_id": cart_id, "customer_id": customer_id, "restaurant_id": None, "items": []},
            strict=True,
        ).model_dump()
        return [*records, created], created

    return update_json(_path(), append)


def update_by_id(cart_id: int, changes: dict) -> dict:
    """Replace restaurant_id and/or items, preserving other stored fields."""
    if not changes or changes.keys() - _MUTABLE_FIELDS:
        raise ValueError("Only restaurant_id and items may be updated")

    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["cart_id"] == cart_id:
                validated = CartRecord.model_validate({**record, **changes}, strict=True).model_dump()
                updated = {**record, **{field: validated[field] for field in changes}}
                return [*records[:index], updated, *records[index + 1:]], updated
        raise CartNotFoundError("Cart not found")

    return update_json(_path(), apply)


class RestaurantConflictError(ValueError):
    pass


class CartTotalError(ValueError):
    pass


def _validate_totals(record: dict) -> None:
    """Reject totals that cannot be returned as JSON numbers before committing."""
    try:
        total = CartRead.model_validate(record).total
    except OverflowError:
        raise CartTotalError("Cart total is too large") from None
    if not isfinite(total):
        raise CartTotalError("Cart total is too large")


def add_item(customer_id: int, restaurant_id: int, line: dict) -> dict:
    """Add a priced line to the customer's cart in one transaction.

    The single-restaurant rule and quantity aggregation are checked against the
    stored cart inside the transaction, so concurrent adds cannot bypass them.
    A repeated product adds its quantity and takes the current name and price.
    """
    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["customer_id"] != customer_id:
                continue
            if record["items"] and record["restaurant_id"] != restaurant_id:
                raise RestaurantConflictError("Cart contains items from another restaurant")
            items = [dict(item) for item in record["items"]]
            existing = next((item for item in items if item["product_id"] == line["product_id"]), None)
            if existing is None:
                items.append(dict(line))
            else:
                existing.update(line, quantity=existing["quantity"] + line["quantity"])
            validated = CartRecord.model_validate(
                {**record, "restaurant_id": restaurant_id, "items": items}, strict=True,
            ).model_dump()
            _validate_totals(validated)
            updated = {**record, "restaurant_id": validated["restaurant_id"], "items": validated["items"]}
            return [*records[:index], updated, *records[index + 1:]], updated
        raise CartNotFoundError("Cart not found")

    return update_json(_path(), apply)
