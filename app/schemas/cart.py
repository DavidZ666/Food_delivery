from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.schemas.restaurant import RequiredText


PositiveId = Annotated[int, Field(gt=0)]
Quantity = Annotated[int, Field(ge=1, strict=True)]


class CartItemAdd(BaseModel):
    """Add-to-cart body. Name, price and restaurant come from the menu item."""

    model_config = ConfigDict(extra="forbid")

    product_id: PositiveId
    quantity: Quantity = 1


class CartItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Quantity


class CartItemRecord(BaseModel):
    """Stored line with the menu item's name and unit price when last set."""

    product_id: PositiveId
    name: RequiredText
    unit_price: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    quantity: Quantity


class CartItemRead(CartItemRecord):
    @computed_field
    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)


class CartRecord(BaseModel):
    """Stored cart. Totals are derived on read, never stored."""

    cart_id: PositiveId
    customer_id: PositiveId
    restaurant_id: PositiveId | None
    items: list[CartItemRecord]

    @model_validator(mode="after")
    def check_items(self):
        if (self.restaurant_id is None) != (not self.items):
            raise ValueError("restaurant_id is set exactly when the cart has items")
        product_ids = [item.product_id for item in self.items]
        if len(set(product_ids)) != len(product_ids):
            raise ValueError("Cart items must have unique product IDs")
        return self


class CartRead(CartRecord):
    items: list[CartItemRead]

    @computed_field
    @property
    def subtotal(self) -> float:
        return round(sum(item.line_total for item in self.items), 2)

    @computed_field
    @property
    def total(self) -> float:
        # No tax, fees or delivery charge in M2.
        return self.subtotal
