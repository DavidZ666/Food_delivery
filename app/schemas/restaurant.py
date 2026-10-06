from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

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


RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: RequiredText
    city: RequiredText
    province: RequiredText
    postal_code: RequiredText


class HoursCreate(Hours):
    model_config = ConfigDict(extra="forbid")


class RestaurantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredText
    cuisine: RequiredText
    location: LocationCreate
    description: str | None = None
    logo_url: str | None = None
    hours: HoursCreate | None = None
