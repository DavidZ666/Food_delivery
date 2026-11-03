from app.core import customer_auth
from app.repositories import customer_repo
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.customer import CustomerCreate, CustomerRead


class InvalidCredentialsError(ValueError):
    pass


class InactiveCustomerError(PermissionError):
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
