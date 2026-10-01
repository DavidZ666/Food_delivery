from pydantic import BaseModel


class MenuItemRead(BaseModel):
    product_id: int
    restaurant_id: int
    name: str
    description: str
    price: float
    category: str
    image: str
    is_available: bool


class MenuError(BaseModel):
    detail: str
