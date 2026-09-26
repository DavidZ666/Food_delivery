from pydantic import BaseModel

class Location(BaseModel):
    address: str
    city: str
    province: str
    postal_code: str


class Hours(BaseModel):
    monday: str | None = None
    tuesday: str | None = None
    wednesday: str | None = None
    thursday: str | None = None
    friday: str | None = None
    saturday: str | None = None
    sunday: str | None = None

class RestaurantRead(BaseModel):
    id: int
    name: str
    cuisine: str
    location: Location
    description: str | None = None
    logo_url: str | None = None
    hours: Hours | None = None