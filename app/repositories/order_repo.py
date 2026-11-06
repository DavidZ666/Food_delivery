from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json_array, update_json
from app.schemas.order import CartConsumption, Order, OrderRecord


def _path():
    return get_data_dir() / "orders.json"


def _validate_records(records) -> None:
    """Reject malformed storage before reads or writes rely on it."""
    validated = TypeAdapter(list[OrderRecord]).validate_python(records, strict=True)
    order_ids = [order.order_id for order in validated]
    if len(set(order_ids)) != len(order_ids):
        raise ValueError("Stored order IDs must be unique")
    receipts = [(order.customer_id, order.cart_consumption.cart_id, order.cart_consumption.generation)
                for order in validated if order.cart_consumption is not None]
    if len(set(receipts)) != len(receipts):
        raise ValueError("A cart generation may only be consumed once")


def _records() -> list[dict]:
    records = read_json_array(_path())
    _validate_records(records)
    return records


def _public(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "cart_consumption"}


def list_all() -> list[dict]:
    return [_public(record) for record in _records()]


def consumed_cart_generations() -> set[tuple[int, int, int]]:
    """Read receipts without requiring an orders file in legacy cart-only stores."""
    try:
        records = _records()
    except FileNotFoundError:
        return set()
    return {(record["customer_id"], receipt["cart_id"], receipt["generation"])
            for record in records if (receipt := record.get("cart_consumption")) is not None}


def get_by_id(order_id: int) -> dict | None:
    return next((r for r in list_all() if r["order_id"] == order_id), None)


def list_by_customer(customer_id: int) -> list[dict]:
    """The customer's orders in storage (creation) order."""
    return [r for r in list_all() if r["customer_id"] == customer_id]


def create(fields: dict) -> dict:
    """Validate a snapshot, allocate the next order ID and append in one transaction.

    Orders are append-only; IDs are never reused.
    """
    if "order_id" in fields:
        raise ValueError("order_id is assigned by the repository")
    fields = dict(fields)
    receipt = fields.pop("cart_consumption", None)
    if receipt is not None:
        receipt = CartConsumption.model_validate(receipt, strict=True).model_dump()

    def append(records):
        _validate_records(records)
        order_id = max((record["order_id"] for record in records), default=0) + 1
        created = Order.model_validate({**fields, "order_id": order_id}, strict=True).model_dump()
        stored = {**created, "cart_consumption": receipt} if receipt is not None else created
        updated = [*records, stored]
        _validate_records(updated)
        return updated, created

    return update_json(_path(), append)
