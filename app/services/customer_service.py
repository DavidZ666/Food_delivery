from app.core import customer_auth
from app.repositories import customer_repo
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate


class InvalidCredentialsError(ValueError):
    pass


class InactiveCustomerError(PermissionError):
    pass


class CustomerNotFoundError(LookupError):
    pass


# Perform the same password work for unknown accounts to limit timing leakage.
_DUMMY_HASH = customer_auth.hash_password("unused-dummy-password")


def register_customer(customer: CustomerCreate) -> CustomerRead:
    fields = customer.model_dump(exclude={"password"})
    fields.update(
        password_hash=customer_auth.hash_password(customer.password),
        role="customer", is_active=True,
    )
    return CustomerRead.model_validate(customer_repo.create(fields))


def sign_in(credentials: LoginRequest) -> TokenResponse:
    customer = customer_repo.get_by_email(credentials.email)
    valid = customer_auth.verify_password(
        credentials.password, customer["password_hash"] if customer else _DUMMY_HASH,
    )
    if customer is None or not valid:
        raise InvalidCredentialsError("Invalid credentials")
    if not customer["is_active"]:
        raise InactiveCustomerError("Forbidden")
    return TokenResponse(
        access_token=customer_auth.issue_token(customer["id"]),
        customer=CustomerRead.model_validate(customer),
    )


def get_customer(customer_id: int) -> CustomerRead:
    customer = customer_repo.get_by_id(customer_id)
    if customer is None:
        raise CustomerNotFoundError("Customer not found")
    return CustomerRead.model_validate(customer)


def require_active_customer(customer_id: int) -> CustomerRead:
    """Shared check for Cart and Checkout: the customer exists and is active."""
    customer = get_customer(customer_id)
    if not customer.is_active:
        raise InactiveCustomerError("Forbidden")
    return customer


def _update(customer_id: int, changes: dict) -> CustomerRead:
    try:
        return CustomerRead.model_validate(customer_repo.update_by_id(customer_id, changes))
    except customer_repo.CustomerRecordNotFoundError as exc:
        raise CustomerNotFoundError("Customer not found") from exc


def update_customer(customer_id: int, update: CustomerUpdate) -> CustomerRead:
    """Persist supplied profile fields; the delivery address merges by subfield."""
    return _update(customer_id, update.model_dump(exclude_unset=True))


def deactivate_customer(customer_id: int) -> CustomerRead:
    """Mark the account inactive; the record and its ID are kept."""
    return _update(customer_id, {"is_active": False})
