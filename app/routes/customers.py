from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.api_contract import STORAGE_FAILURE
from app.core.auth import require_account_access
from app.repositories.customer_repo import DuplicateEmailError
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.schemas.error import ErrorResponse
from app.services import customer_service


router = APIRouter(tags=["Customers"])

CustomerId = Annotated[int, Path(description="Stored customer ID.", examples=[1])]
ACCOUNT_ACCESS = [Depends(require_account_access)]
ACCOUNT_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired bearer credentials."},
    403: {"model": ErrorResponse, "description": "Deactivated account, or another account without the admin role."},
    404: {"model": ErrorResponse, "description": "Customer not found (administrators only)."},
    500: STORAGE_FAILURE,
}


@router.post(
    "/customers", status_code=201, response_model=CustomerRead,
    summary="Register a customer",
    description="Persist an active customer account with a server-assigned ID and customer role. Passwords are stored as salted hashes.",
    responses={
        409: {"model": ErrorResponse, "description": "Email is already registered."},
        500: STORAGE_FAILURE,
    },
)
def register_customer(customer: CustomerCreate):
    try:
        return customer_service.register_customer(customer)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _not_found(exc: customer_service.CustomerNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/customers/{customer_id}", response_model=CustomerRead, dependencies=ACCOUNT_ACCESS,
    summary="Retrieve a customer profile",
    description="Return the signed-in account's profile; administrators may read any account. Never includes the password hash.",
    responses=ACCOUNT_ERRORS,
)
def get_customer(customer_id: CustomerId):
    try:
        return customer_service.get_customer(customer_id)
    except customer_service.CustomerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch(
    "/customers/{customer_id}", response_model=CustomerRead, dependencies=ACCOUNT_ACCESS,
    summary="Update a customer profile",
    description=(
        "Update supplied name, phone and delivery-address fields in one transaction; "
        "the address merges by subfield. Email, password, role and account state "
        "cannot be changed here. Empty objects, nulls and unknown fields return 422."
    ),
    responses=ACCOUNT_ERRORS,
)
def update_customer(customer_id: CustomerId, update: CustomerUpdate):
    try:
        return customer_service.update_customer(customer_id, update)
    except customer_service.CustomerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/customers/{customer_id}/deactivate", response_model=CustomerRead, dependencies=ACCOUNT_ACCESS,
    summary="Deactivate a customer account",
    description=(
        "Persist is_active: false. The record and its ID are kept for cart and order "
        "references; the account can no longer sign in or use protected operations."
    ),
    responses=ACCOUNT_ERRORS,
)
def deactivate_customer(customer_id: CustomerId):
    try:
        return customer_service.deactivate_customer(customer_id)
    except customer_service.CustomerNotFoundError as exc:
        raise _not_found(exc) from exc
