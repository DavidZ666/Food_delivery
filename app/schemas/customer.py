from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.restaurant import PartialUpdate, RequiredText


Role = Literal["customer", "restaurant_owner", "admin"]

# Login identifier. Trimmed and lowercased so uniqueness is case-insensitive.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class DeliveryAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: RequiredText
    city: RequiredText
    province: RequiredText
    postal_code: RequiredText


class DeliveryAddressUpdate(PartialUpdate):
    address: RequiredText = Field(default=None)
    city: RequiredText = Field(default=None)
    province: RequiredText = Field(default=None)
    postal_code: RequiredText = Field(default=None)


class CustomerCreate(BaseModel):
    """Registration body. Role and account state are assigned by the server."""

    model_config = ConfigDict(extra="forbid")

    name: RequiredText
    email: Email
    password: Password
    phone: RequiredText
    delivery_address: DeliveryAddress


class CustomerUpdate(PartialUpdate):
    """Profile update. Email, password, role and state are not editable here."""

    name: RequiredText = Field(default=None)
    phone: RequiredText = Field(default=None)
    delivery_address: DeliveryAddressUpdate = Field(default=None)


class CustomerRead(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    delivery_address: DeliveryAddress
    role: Role
    is_active: bool


class CustomerRecord(CustomerRead):
    """Stored account. Never returned by the API."""

    id: Annotated[int, Field(gt=0)]
    name: RequiredText
    email: Email
    phone: RequiredText
    password_hash: RequiredText
