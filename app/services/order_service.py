"""Order history and single-order reads (#92). Orders are stored snapshots, never recalculated."""
from app.repositories import order_repo
from app.schemas.order import Order, OrderRecord
from app.services import customer_service


class OrderNotFoundError(LookupError):
    pass


def _snapshot(record: dict) -> Order:
    # Stored records may carry extra metadata; return only the published fields.
    return Order.model_validate(OrderRecord.model_validate(record).model_dump())


def list_orders(customer_id: int) -> list[Order]:
    """Return the customer's orders in creation order; [] when there are none."""
    customer_service.get_customer(customer_id)
    records = sorted(order_repo.list_by_customer(customer_id), key=lambda record: record["order_id"])
    return [_snapshot(record) for record in records]


def get_order(customer_id: int, order_id: int) -> Order:
    """Return one of the customer's orders; another customer's order is not found."""
    customer_service.get_customer(customer_id)
    record = order_repo.get_by_id(order_id)
    if record is None or record["customer_id"] != customer_id:
        raise OrderNotFoundError("Order not found")
    return _snapshot(record)
