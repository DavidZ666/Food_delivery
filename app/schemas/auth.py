from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.customer import Email, CustomerRead


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    customer: CustomerRead
