"""Order snapshots (#89). An order records checkout as it happened; it is never recalculated."""
import re
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.schemas.cart import PositiveId, Quantity
from app.schemas.customer import DeliveryAddress
from app.schemas.restaurant import RequiredText


# Only the initial status exists in M2; later lifecycle states extend this.
OrderStatus = Literal["placed"]
Money = Annotated[float, Field(ge=0, allow_inf_nan=False)]
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z")


def _check_utc_timestamp(value: str) -> str:
    if not _UTC_TIMESTAMP.fullmatch(value):
        raise ValueError("created_at must be a UTC ISO 8601 timestamp ending in Z")
    datetime.fromisoformat(value)  # rejects impossible dates such as month 13
    return value


UtcTimestamp = Annotated[str, AfterValidator(_check_utc_timestamp)]


def utc_timestamp(now: datetime | None = None) -> str:
    """Format an aware time (default: now) as the stored created_at value."""
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None:
        raise ValueError("created_at requires a timezone-aware time")
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: PositiveId
    name: RequiredText
    unit_price: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    quantity: Quantity
    line_total: Money

    @model_validator(mode="after")
    def check_line_total(self):
        if self.line_total != round(self.unit_price * self.quantity, 2):
            raise ValueError("line_total must equal unit_price x quantity, rounded to cents")
        return self


class Order(BaseModel):
    """Stored and returned order. Totals are stored, unlike a cart's derived totals."""

    model_config = ConfigDict(extra="forbid")

    order_id: PositiveId
    customer_id: PositiveId
    restaurant_id: PositiveId
    delivery_address: DeliveryAddress
    items: Annotated[list[OrderItem], Field(min_length=1)]
    subtotal: Money
    total: Money
    status: OrderStatus
    created_at: UtcTimestamp

    @model_validator(mode="after")
    def check_items_and_totals(self):
        product_ids = [item.product_id for item in self.items]
        if len(set(product_ids)) != len(product_ids):
            raise ValueError("Order items must have unique product IDs")
        if self.subtotal != round(sum(item.line_total for item in self.items), 2):
            raise ValueError("subtotal must equal the sum of line totals")
        if self.total != self.subtotal:
            # No tax, fees or delivery charge in M2.
            raise ValueError("total must equal subtotal")
        return self


class OrderRecord(Order):
    """Stored order; extra metadata on existing records is preserved, not rejected."""

    model_config = ConfigDict(extra="ignore")
