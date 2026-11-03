from fastapi import APIRouter, HTTPException

from app.core.api_contract import STORAGE_FAILURE
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.error import ErrorResponse
from app.services import customer_service


router = APIRouter(tags=["Authentication"])


@router.post(
    "/auth/login", response_model=TokenResponse,
    summary="Sign in as a customer",
    description="Verify credentials and return an opaque bearer token valid for one hour in this application process. Restarting the server invalidates sessions.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials."},
        403: {"model": ErrorResponse, "description": "Forbidden: account is deactivated."},
        500: STORAGE_FAILURE,
    },
)
def sign_in(credentials: LoginRequest):
    try:
        return customer_service.sign_in(credentials)
    except customer_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
    except customer_service.InactiveCustomerError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
