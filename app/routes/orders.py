from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.api_contract import STORAGE_FAILURE
from app.core.auth import require_customer_owner
from app.schemas.error import ErrorResponse
from app.schemas.order import Order
from app.services import cart_service, checkout_service, customer_service


router = APIRouter(tags=["Orders"])

CustomerId = Annotated[int, Path(description="The signed-in customer's ID.", examples=[1])]
CUSTOMER_OWNER = [Depends(require_customer_owner)]
ORDER_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer credentials."},
    403: {"model": ErrorResponse, "description": "Deactivated account, a role other than customer, or another customer's cart."},
    500: STORAGE_FAILURE,
}


@router.post(
    "/customers/{customer_id}/checkout", response_model=Order, status_code=201,
    dependencies=CUSTOMER_OWNER,
    summary="Check out the active cart",
    description=(
        "Revalidate every cart item against the current menu, save a placed order "
        "snapshot at current names and prices with the customer's delivery address, "
        "and consume the cart in the same atomic write. A failed order write leaves "
        "the cart unchanged. Edits to the same cart wait, then apply to the empty cart."
    ),
    responses={
        **ORDER_ERRORS,
        404: {"model": ErrorResponse, "description": "The customer has no cart."},
        409: {"model": ErrorResponse, "description": "The cart is empty, or an item is no longer on the menu, unavailable, or its restaurant no longer exists."},
    },
)
def checkout(customer_id: CustomerId):
    try:
        return checkout_service.checkout(customer_id)
    except customer_service.InactiveCustomerError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except (cart_service.CartNotFoundError, customer_service.CustomerNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (checkout_service.EmptyCartError, checkout_service.MenuItemUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
