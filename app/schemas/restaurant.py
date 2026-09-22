from pydantic import BaseModel


class RestaurantRead(BaseModel):
    id: str
    name: str
    cuisine: str