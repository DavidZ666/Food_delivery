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
    price: float = Field(gt=0, allow_inf_nan=False)
    category: str = Field(min_length=1)
    image: str = ""
    is_available: bool = True

class MenuItemUpdate(BaseModel):
    name: str = Field(default=None, min_length=1)
    description: str = Field(default=None)
    price: float = Field(default=None, gt=0, allow_inf_nan=False)
    category: str = Field(default=None, min_length=1)
    image: str = Field(default=None)
    is_available: bool = Field(default=None)

class MenuError(BaseModel):
    detail: str
