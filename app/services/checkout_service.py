"""Checkout (#90): revalidate the cart, save an order snapshot, then clear the cart."""
import logging
from threading import Lock

from app.repositories import cart_repo, order_repo
from app.schemas.order import Order, utc_timestamp
from app.services import cart_service, customer_service


logger = logging.getLogger(__name__)


class EmptyCartError(ValueError):
    pass


class MenuItemUnavailableError(ValueError):
    pass


# One checkout at a time in this process, so a cart cannot be ordered twice.
_checkout_lock = Lock()


def _current_item(restaurant_id: int, line: dict) -> dict:
    """Re-read the menu item; it must still exist, belong to the cart's restaurant and be available."""
    try:
        product = cart_service._menu_item(line["product_id"])
    except cart_service.MenuItemNotFoundError:
        raise MenuItemUnavailableError("Menu item is unavailable") from None
    if product["restaurant_id"] != restaurant_id or product["is_available"] is not True:
        raise MenuItemUnavailableError("Menu item is unavailable")
    unit_price = product["price"]
    return {"product_id": product["product_id"], "name": product["name"], "unit_price": unit_price,
            "quantity": line["quantity"], "line_total": round(unit_price * line["quantity"], 2)}


def checkout(customer_id: int) -> Order:
    """Create a placed order from the active cart at current menu prices.

    The order is saved first; the cart is cleared afterwards, and only if it is
    unchanged since the snapshot. A failed order write leaves the cart untouched.
    If clearing fails after the order is saved, the order is still returned.
    """
    with _checkout_lock:
        # A queued checkout must use account state after the preceding checkout.
        customer = customer_service.require_active_customer(customer_id)
        cart = cart_repo.get_by_customer_id(customer_id)
        if cart is None:
            raise cart_service.CartNotFoundError("Cart not found")
        if not cart["items"]:
            raise EmptyCartError("Cart is empty")
        items = [_current_item(cart["restaurant_id"], line) for line in cart["items"]]
        subtotal = round(sum(item["line_total"] for item in items), 2)
        order = order_repo.create({
            "customer_id": customer_id, "restaurant_id": cart["restaurant_id"],
            "delivery_address": customer.delivery_address.model_dump(),
            "items": items, "subtotal": subtotal, "total": subtotal,
            "status": "placed", "created_at": utc_timestamp(),
        })
        try:
            cart_repo.clear_if_unchanged(customer_id, cart["items"])
        except (cart_repo.CartChangedError, cart_repo.CartNotFoundError, OSError, ValueError) as exc:
            # The order is saved; keep the cart rather than lose a concurrent change.
            logger.warning("Cart for customer %s kept after order %s: %s",
                           customer_id, order["order_id"], exc)
    return Order.model_validate(order)
