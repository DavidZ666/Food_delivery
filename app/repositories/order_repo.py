from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json_array, update_json
from app.schemas.order import Order, OrderRecord


def _path():
    return get_data_dir() / "orders.json"


def _validate_records(records) -> None:
    """Reject malformed storage before reads or writes rely on it."""
    validated = TypeAdapter(list[OrderRecord]).validate_python(records, strict=True)
    order_ids = [order.order_id for order in validated]
    if len(set(order_ids)) != len(order_ids):
        raise ValueError("Stored order IDs must be unique")


def list_all() -> list[dict]:
    records = read_json_array(_path())
    _validate_records(records)
    return records


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

    def append(records):
        _validate_records(records)
        order_id = max((record["order_id"] for record in records), default=0) + 1
        created = Order.model_validate({**fields, "order_id": order_id}, strict=True).model_dump()
        return [*records, created], created

    return update_json(_path(), append)
