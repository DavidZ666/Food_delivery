from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.api_contract import STORAGE_FAILURE
from app.core.auth import require_account_access, require_customer_owner
from app.schemas.error import ErrorResponse
from app.schemas.order import Order
from app.services import cart_service, checkout_service, customer_service, order_service


router = APIRouter(tags=["Orders"])

CustomerId = Annotated[int, Path(description="The signed-in customer's ID.", examples=[1])]
CUSTOMER_OWNER = [Depends(require_customer_owner)]
ACCOUNT_ACCESS = [Depends(require_account_access)]
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
        "then clear the cart. Any failure before the order is saved leaves the cart "
        "unchanged; the cart is cleared only if it did not change during checkout."
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


OrderId = Annotated[int, Path(gt=0, description="Stored order ID belonging to this customer.", examples=[1])]
ReadCustomerId = Annotated[int, Path(gt=0, description="Customer whose orders are read.", examples=[1])]
ORDER_READ_ERRORS = {
    401: ORDER_ERRORS[401],
    403: {"model": ErrorResponse, "description": "Deactivated account, or another account without the admin role."},
    404: {"model": ErrorResponse, "description": "Order not found for this customer, or (administrators) customer not found."},
    500: STORAGE_FAILURE,
}


@router.get(
    "/customers/{customer_id}/orders", response_model=list[Order], dependencies=ACCOUNT_ACCESS,
    summary="List a customer's orders",
    description=(
        "Return the customer's stored order snapshots in creation order (ascending "
        "order_id); [] when there are none. Snapshots are never recalculated from the "
        "current menu. The signed-in account may read its own orders; administrators "
        "may read any customer's orders, including a deactivated customer's."
    ),
    responses=ORDER_READ_ERRORS,
)
def list_orders(customer_id: ReadCustomerId):
    try:
        return order_service.list_orders(customer_id)
    except customer_service.CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/customers/{customer_id}/orders/{order_id}", response_model=Order, dependencies=ACCOUNT_ACCESS,
    summary="Retrieve one order",
    description=(
        "Return one stored order snapshot. An unknown order, or an order belonging to "
        "another customer, returns 404 Order not found without revealing whether it exists."
    ),
    responses=ORDER_READ_ERRORS,
)
def get_order(customer_id: ReadCustomerId, order_id: OrderId):
    try:
        return order_service.get_order(customer_id, order_id)
    except (customer_service.CustomerNotFoundError, order_service.OrderNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
