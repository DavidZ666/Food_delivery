"""Reusable authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Annotated, get_args

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import customer_auth
from app.repositories import customer_repo
from app.schemas.customer import CustomerRead, Role


_bearer = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CustomerRead:
    """Resolve a bearer session and load the active account's current state."""
    customer_id = customer_auth.resolve_token(credentials.credentials) if credentials else None
    customer = customer_repo.get_by_id(customer_id) if customer_id is not None else None
    if customer is None:
        raise HTTPException(
            status_code=401, detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not customer["is_active"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return CustomerRead.model_validate(customer)


def require_roles(*roles: Role) -> Callable[..., CustomerRead]:
    """Allow only the explicitly listed roles; an empty list denies everyone."""
    unknown = set(roles) - set(get_args(Role))
    if unknown:
        raise ValueError(f"Unknown role(s): {', '.join(sorted(unknown))}")

    def check_role(
        customer: Annotated[CustomerRead, Depends(get_current_customer)],
    ) -> CustomerRead:
        if customer.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return customer

    return check_role


def require_customer_owner(
    customer_id: int,
    customer: Annotated[CustomerRead, Depends(require_roles("customer"))],
) -> CustomerRead:
    """Require a customer accessing their own ID, without an admin bypass."""
    if customer.id != customer_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return customer


def require_account_access(
    customer_id: int,
    account: Annotated[CustomerRead, Depends(get_current_customer)],
) -> CustomerRead:
    """Allow the account itself, or an administrator for any account ID."""
    if account.role != "admin" and account.id != customer_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return account
