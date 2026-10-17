from pydantic import BaseModel, Field

class MenuItemRead(BaseModel):
    product_id: int
    restaurant_id: int
    name: str
    description: str
    price: float
    category: str
    image: str
    is_available: bool

class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    price: float = Field(gt=0)
    category: str = Field(min_length=1)
    image: str = ""
    is_available: bool = True

class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, min_length=1)
    image: str | None = None
    is_available: bool | None = None

class MenuError(BaseModel):
    detail: str
