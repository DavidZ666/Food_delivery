"""Checkout (#90): atomically save an order snapshot and its cart consumption."""
from threading import Lock

from app.repositories import cart_repo, order_repo
from app.schemas.order import Order, utc_timestamp
from app.services import cart_service, customer_service


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

    Item mutations of the same cart wait while checkout holds its cart lock, so
    the order buys exactly the items read. The order and cart consumption receipt
    share one atomic write; a failed write leaves the cart untouched.
    """
    with _checkout_lock, cart_repo.cart_lock(customer_id):
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
            "cart_consumption": {"cart_id": cart["cart_id"],
                                 "generation": cart.get("checkout_generation", 0)},
        })
    return Order.model_validate(order)
