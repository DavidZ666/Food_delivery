"""Active cart retrieval and initialization for active customers (#82)."""

from app.repositories import cart_repo, product_repo
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartRead
from app.services import customer_service, menu_service


class CartNotFoundError(LookupError):
    pass


def get_cart(customer_id: int) -> CartRead:
    """Return the active customer's cart with backend-calculated totals."""
    customer_service.require_active_customer(customer_id)
    cart = cart_repo.get_by_customer_id(customer_id)
    if cart is None:
        raise CartNotFoundError("Cart not found")
    return CartRead.model_validate(cart)


def get_or_create_cart(customer_id: int) -> tuple[CartRead, bool]:
    """Return (cart, created); a customer never gets a second active cart."""
    customer_service.require_active_customer(customer_id)
    cart = cart_repo.get_by_customer_id(customer_id)
    if cart is not None:
        return CartRead.model_validate(cart), False
    try:
        return CartRead.model_validate(cart_repo.create(customer_id)), True
    except cart_repo.ActiveCartExistsError:
        # A concurrent request created it between the read and the transaction.
        return CartRead.model_validate(cart_repo.get_by_customer_id(customer_id)), False


class MenuItemNotFoundError(LookupError):
    pass


class MenuItemUnavailableError(ValueError):
    pass


RestaurantConflictError = cart_repo.RestaurantConflictError


def _menu_item(product_id: int) -> dict:
    """Find the product and confirm, via the menu service, that its restaurant exists."""
    product = next((p for p in product_repo.list_all() if p["product_id"] == product_id), None)
    if product is None:
        raise MenuItemNotFoundError("Menu item not found")
    try:
        return menu_service.get_menu_item(product["restaurant_id"], product_id)
    except (menu_service.RestaurantNotFound, menu_service.MenuItemNotFound):
        # An item whose restaurant no longer exists cannot be ordered.
        raise MenuItemNotFoundError("Menu item not found") from None


def add_item(customer_id: int, item: CartItemAdd) -> CartRead:
    """Add an available menu item; name, price and restaurant come from the menu."""
    customer_service.require_active_customer(customer_id)
    if cart_repo.get_by_customer_id(customer_id) is None:
        raise CartNotFoundError("Cart not found")
    product = _menu_item(item.product_id)
    if product["is_available"] is not True:
        raise MenuItemUnavailableError("Menu item is unavailable")
    line = {"product_id": product["product_id"], "name": product["name"],
            "unit_price": product["price"], "quantity": item.quantity}
    try:
        cart = cart_repo.add_item(customer_id, product["restaurant_id"], line)
    except cart_repo.CartNotFoundError:
        raise CartNotFoundError("Cart not found") from None
    return CartRead.model_validate(cart)


class CartItemNotFoundError(LookupError):
    pass


def _edit(customer_id: int, operation, *args) -> CartRead:
    customer_service.require_active_customer(customer_id)
    try:
        return CartRead.model_validate(operation(customer_id, *args))
    except cart_repo.CartNotFoundError:
        raise CartNotFoundError("Cart not found") from None
    except cart_repo.CartItemNotFoundError:
        raise CartItemNotFoundError("Cart item not found") from None


def update_item(customer_id: int, product_id: int, update: CartItemUpdate) -> CartRead:
    """Set an item's quantity; totals are recalculated from stored unit prices."""
    return _edit(customer_id, cart_repo.set_quantity, product_id, update.quantity)


def remove_item(customer_id: int, product_id: int) -> CartRead:
    """Remove an item; removing the last one clears the restaurant binding."""
    return _edit(customer_id, cart_repo.remove_item, product_id)


def clear_cart(customer_id: int) -> CartRead:
    """Empty the cart (idempotent), keeping its cart_id."""
    return _edit(customer_id, cart_repo.clear)
