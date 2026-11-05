"""Active cart retrieval and initialization for active customers (#82)."""

from app.repositories import cart_repo
from app.schemas.cart import CartRead
from app.services import customer_service


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
