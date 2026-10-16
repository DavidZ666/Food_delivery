from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

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


class PartialUpdate(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"minProperties": 1},
    )

    @model_validator(mode="after")
    def require_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class LocationUpdate(PartialUpdate):

    # default=None 允许省略字段。
    # 类型本身不含 None，因此显式传入 null 会被拒绝。
    # 提取更新内容时必须使用 exclude_unset=True。
    address: RequiredText = Field(default=None)
    city: RequiredText = Field(default=None)
    province: RequiredText = Field(default=None)
    postal_code: RequiredText = Field(default=None)


class HoursUpdate(PartialUpdate):

    monday: str | None = None
    tuesday: str | None = None
    wednesday: str | None = None
    thursday: str | None = None
    friday: str | None = None
    saturday: str | None = None
    sunday: str | None = None


class RestaurantUpdate(PartialUpdate):

    name: RequiredText = Field(default=None)
    cuisine: RequiredText = Field(default=None)
    location: LocationUpdate = Field(default=None)

    description: str | None = None
    logo_url: str | None = None
    hours: HoursUpdate | None = None