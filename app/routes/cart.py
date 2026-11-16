from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.core.api_contract import STORAGE_FAILURE
from app.core.auth import require_customer_owner
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartRead
from app.schemas.error import ErrorResponse
from app.services import cart_service, customer_service


router = APIRouter(tags=["Cart"])

CustomerId = Annotated[int, Path(description="The signed-in customer's ID.", examples=[1])]
ProductId = Annotated[int, Path(gt=0, description="Product ID of an item in the cart.", examples=[1])]
CART_OWNER = [Depends(require_customer_owner)]
CART_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer credentials."},
    403: {"model": ErrorResponse, "description": "Deactivated account, a role other than customer, or another customer's cart."},
    404: {"model": ErrorResponse, "description": "The customer has no cart (GET), or the customer no longer exists."},
    500: STORAGE_FAILURE,
}
CART_TOTAL_RESPONSE = {
    "description": "Invalid request data, or the resulting cart total exceeds the finite numeric range.",
    "content": {"application/json": {"schema": {"anyOf": [
        {"$ref": "#/components/schemas/HTTPValidationError"},
        {"$ref": "#/components/schemas/ErrorResponse"},
    ]}}},
}


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, cart_service.CartTotalError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, customer_service.InactiveCustomerError):
        return HTTPException(status_code=403, detail="Forbidden")
    if isinstance(exc, (cart_service.MenuItemUnavailableError, cart_service.RestaurantConflictError)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/customers/{customer_id}/cart", response_model=CartRead, dependencies=CART_OWNER,
    summary="Retrieve the active cart",
    description=(
        "Return the customer's single active cart with items, unit prices and "
        "backend-calculated line totals, subtotal and total. A customer without "
        "a cart receives 404; create it with POST."
    ),
    responses=CART_ERRORS,
)
def get_cart(customer_id: CustomerId):
    try:
        return cart_service.get_cart(customer_id)
    except (cart_service.CartNotFoundError, customer_service.CustomerNotFoundError,
            customer_service.InactiveCustomerError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/customers/{customer_id}/cart", response_model=CartRead, status_code=201, dependencies=CART_OWNER,
    summary="Initialize or retrieve the active cart",
    description=(
        "Create an empty active cart (201) or return the existing one unchanged "
        "(200). A customer never has more than one active cart. Totals are "
        "calculated by the backend."
    ),
    responses={200: {"model": CartRead, "description": "The existing active cart; nothing was created."},
               **CART_ERRORS},
)
def create_cart(customer_id: CustomerId, response: Response):
    try:
        cart, created = cart_service.get_or_create_cart(customer_id)
    except (customer_service.CustomerNotFoundError, customer_service.InactiveCustomerError) as exc:
        raise _http_error(exc) from exc
    if not created:
        response.status_code = 200
    return cart


@router.post(
    "/customers/{customer_id}/cart/items", response_model=CartRead, dependencies=CART_OWNER,
    summary="Add a menu item to the cart",
    description=(
        "Add an available menu item. Name, unit price and restaurant come from the "
        "stored menu item; adding a product again increases its quantity. A cart holds "
        "items from one restaurant. Totals are calculated by the backend. Rejected "
        "requests leave the cart unchanged."
    ),
    responses={
        **CART_ERRORS,
        404: {"model": ErrorResponse, "description": "Cart not found, or menu item not found (including an item whose restaurant no longer exists)."},
        409: {"model": ErrorResponse, "description": "Menu item is unavailable, or the cart contains items from another restaurant."},
        422: CART_TOTAL_RESPONSE,
    },
)
def add_cart_item(customer_id: CustomerId, item: CartItemAdd):
    try:
        return cart_service.add_item(customer_id, item)
    except (cart_service.CartNotFoundError, cart_service.MenuItemNotFoundError,
            cart_service.MenuItemUnavailableError, cart_service.RestaurantConflictError, cart_service.CartTotalError,
            customer_service.CustomerNotFoundError, customer_service.InactiveCustomerError) as exc:
        raise _http_error(exc) from exc


EDIT_ERRORS = {
    **CART_ERRORS,
    404: {"model": ErrorResponse, "description": "Cart not found, or the cart has no item with this product ID."},
}
EDIT_FAILURES = (cart_service.CartNotFoundError, cart_service.CartItemNotFoundError,
                 cart_service.CartTotalError, customer_service.CustomerNotFoundError,
                 customer_service.InactiveCustomerError)


@router.patch(
    "/customers/{customer_id}/cart/items/{product_id}", response_model=CartRead, dependencies=CART_OWNER,
    summary="Update a cart item quantity",
    description=(
        "Set the quantity (a JSON integer of at least 1) of an item already in the cart. "
        "The stored name and unit price are kept; totals are recalculated by the backend. "
        "Rejected requests leave the cart unchanged."
    ),
    responses={**EDIT_ERRORS, 422: CART_TOTAL_RESPONSE},
)
def update_cart_item(customer_id: CustomerId, product_id: ProductId, update: CartItemUpdate):
    try:
        return cart_service.update_item(customer_id, product_id, update)
    except EDIT_FAILURES as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/customers/{customer_id}/cart/items/{product_id}", response_model=CartRead, dependencies=CART_OWNER,
    summary="Remove an item from the cart",
    description=(
        "Remove an item and return the updated cart. Removing the last item empties the "
        "cart and clears its restaurant, so items from any restaurant can be added next."
    ),
    responses=EDIT_ERRORS,
)
def remove_cart_item(customer_id: CustomerId, product_id: ProductId):
    try:
        return cart_service.remove_item(customer_id, product_id)
    except EDIT_FAILURES as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/customers/{customer_id}/cart/items", response_model=CartRead, dependencies=CART_OWNER,
    summary="Clear the cart",
    description=(
        "Remove every item, clear the restaurant and return the empty cart with zero totals. "
        "The cart ID is kept; clearing an empty cart succeeds."
    ),
    responses={**CART_ERRORS, 404: {"model": ErrorResponse, "description": "Cart not found."}},
)
def clear_cart(customer_id: CustomerId):
    try:
        return cart_service.clear_cart(customer_id)
    except EDIT_FAILURES as exc:
        raise _http_error(exc) from exc
