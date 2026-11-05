from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.core.api_contract import STORAGE_FAILURE
from app.core.auth import require_customer_owner
from app.schemas.cart import CartRead
from app.schemas.error import ErrorResponse
from app.services import cart_service, customer_service


router = APIRouter(tags=["Cart"])

CustomerId = Annotated[int, Path(description="The signed-in customer's ID.", examples=[1])]
CART_OWNER = [Depends(require_customer_owner)]
CART_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer credentials."},
    403: {"model": ErrorResponse, "description": "Deactivated account, a role other than customer, or another customer's cart."},
    404: {"model": ErrorResponse, "description": "The customer has no cart (GET), or the customer no longer exists."},
    500: STORAGE_FAILURE,
}


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, customer_service.InactiveCustomerError):
        return HTTPException(status_code=403, detail="Forbidden")
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
