from fastapi import APIRouter, HTTPException

from app.core.api_contract import STORAGE_FAILURE
from app.repositories.customer_repo import DuplicateEmailError
from app.schemas.customer import CustomerCreate, CustomerRead
from app.schemas.error import ErrorResponse
from app.services import customer_service


router = APIRouter(tags=["Customers"])


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
