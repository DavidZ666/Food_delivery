from math import isfinite
from threading import Lock, RLock

from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories import order_repo
from app.repositories.json_store import read_json_array, storage_lock, update_json
from app.schemas.cart import CartRead, CartRecord


class CartNotFoundError(LookupError):
    pass


class ActiveCartExistsError(ValueError):
    pass


_MUTABLE_FIELDS = {"restaurant_id", "items"}
_cart_locks: dict[int, RLock] = {}
_cart_locks_guard = Lock()


def cart_lock(customer_id: int) -> RLock:
    """The lock that orders checkout and item mutations of one customer's cart.

    Lock order is cart lock, then the storage lock; storage transactions never
    take a cart lock, so the two cannot deadlock. One application process.
    """
    with _cart_locks_guard:
        return _cart_locks.setdefault(customer_id, RLock())


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
    for record in records:
        generation = record.get("checkout_generation", 0)
        if type(generation) is not int or generation < 0:
            raise ValueError("Stored cart generation must be a non-negative integer")


def _effective(record: dict, consumed: set) -> dict:
    """An order receipt consumes a generation even before carts.json is rewritten."""
    key = (record["customer_id"], record["cart_id"], record.get("checkout_generation", 0))
    if key in consumed:
        return {**record, "restaurant_id": None, "items": []}
    return record


def _editable(record: dict) -> dict:
    effective = _effective(record, order_repo.consumed_cart_generations())
    if effective is not record:
        return {**effective, "checkout_generation": record.get("checkout_generation", 0) + 1}
    return record


def list_all() -> list[dict]:
    with storage_lock():
        records = read_json_array(_path())
        _validate_records(records)
        consumed = order_repo.consumed_cart_generations()
        return [_effective(record, consumed) for record in records]


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
    current = get_by_id(cart_id)
    if current is None:
        raise CartNotFoundError("Cart not found")

    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["cart_id"] == cart_id:
                record = _editable(record)
                validated = CartRecord.model_validate({**record, **changes}, strict=True).model_dump()
                updated = {**record, **{field: validated[field] for field in changes}}
                return [*records[:index], updated, *records[index + 1:]], updated
        raise CartNotFoundError("Cart not found")

    with cart_lock(current["customer_id"]):
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


class CartItemNotFoundError(LookupError):
    pass


def _change_items(customer_id: int, change) -> dict:
    """Apply change(record) -> (restaurant_id, items) to the stored cart in one transaction.

    Rules run against the current stored cart, so concurrent requests cannot bypass them.
    The cart lock makes the change wait for an in-progress checkout of the same cart.
    """
    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["customer_id"] != customer_id:
                continue
            record = _editable(record)
            restaurant_id, items = change(record, [dict(item) for item in record["items"]])
            validated = CartRecord.model_validate(
                {**record, "restaurant_id": restaurant_id if items else None, "items": items}, strict=True,
            ).model_dump()
            _validate_totals(validated)
            updated = {**record, "restaurant_id": validated["restaurant_id"], "items": validated["items"]}
            return [*records[:index], updated, *records[index + 1:]], updated
        raise CartNotFoundError("Cart not found")

    with cart_lock(customer_id):
        return update_json(_path(), apply)


def _find(items: list[dict], product_id: int) -> dict:
    item = next((item for item in items if item["product_id"] == product_id), None)
    if item is None:
        raise CartItemNotFoundError("Cart item not found")
    return item


def add_item(customer_id: int, restaurant_id: int, line: dict) -> dict:
    """Add a priced line; a repeated product adds its quantity and takes the current name and price."""
    def change(record, items):
        if items and record["restaurant_id"] != restaurant_id:
            raise RestaurantConflictError("Cart contains items from another restaurant")
        existing = next((item for item in items if item["product_id"] == line["product_id"]), None)
        if existing is None:
            items.append(dict(line))
        else:
            existing.update(line, quantity=existing["quantity"] + line["quantity"])
        return restaurant_id, items

    return _change_items(customer_id, change)


def set_quantity(customer_id: int, product_id: int, quantity: int) -> dict:
    """Set a line's quantity, keeping its stored name and unit price."""
    def change(record, items):
        _find(items, product_id)["quantity"] = quantity
        return record["restaurant_id"], items

    return _change_items(customer_id, change)


def remove_item(customer_id: int, product_id: int) -> dict:
    """Remove a line; an emptied cart is no longer bound to a restaurant."""
    def change(record, items):
        removed = _find(items, product_id)
        return record["restaurant_id"], [item for item in items if item is not removed]

    return _change_items(customer_id, change)


def clear(customer_id: int) -> dict:
    """Empty the cart, keeping its cart_id."""
    return _change_items(customer_id, lambda record, items: (None, []))


class CartChangedError(RuntimeError):
    pass


def clear_if_unchanged(customer_id: int, expected_items: list[dict]) -> dict:
    """Empty the cart only if its items still equal expected_items (checkout, #90).

    A cart changed since the checkout snapshot raises CartChangedError and is left
    as it is, so a concurrent change is not silently discarded.
    """
    def change(record, items):
        if items != expected_items:
            raise CartChangedError("Cart changed during checkout")
        return None, []

    return _change_items(customer_id, change)
