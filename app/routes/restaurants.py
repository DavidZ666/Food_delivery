from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
    Path,
    Query,
)

from app.schemas.error import ErrorResponse
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)
from app.services import restaurant_service

router = APIRouter()


@router.get(
    "/restaurants",
    response_model=list[RestaurantRead],
    summary="List or search restaurants",
    description="Return stored restaurants in storage order. Optionally search by "
                "a case-insensitive literal substring of the name. Surrounding "
                "query whitespace is ignored; omitted or blank queries return "
                "all restaurants. No matches return HTTP 200 with an empty list.",
)
def list_restaurants(
    name: str | None = Query(
        default=None,
        description="Case-insensitive name substring; surrounding whitespace is "
                    "ignored. Omitted or blank values return all restaurants.",
    ),
):
    return restaurant_service.list_restaurants(name=name)


@router.post(
    "/restaurants",
    response_model=RestaurantRead,
    status_code=201,
    summary="Create a restaurant",
    description=(
        "Create and persist a restaurant with a server-generated positive ID. "
        "Required text is trimmed and must be nonblank. Unknown fields, including "
        "a supplied ID, are rejected with 422. Storage failures return 500."
    ),
    response_description="The persisted restaurant, including its generated ID.",
    responses={500: {"description": "Invalid stored data or storage failure."}},
)
def create_restaurant(restaurant: RestaurantCreate):
    return restaurant_service.create_restaurant(restaurant)

@router.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantRead,
    summary="Retrieve restaurant details",
    description=(
        "Read a restaurant by its stable integer ID from persisted JSON data. "
        "Non-integer IDs return HTTP 422 validation errors."
    ),
    responses={
        200: {"description": "The requested restaurant, including optional fields."},
        404: {
            "model": ErrorResponse,
            "description": "No restaurant has the requested ID.",
            "content": {
                "application/json": {"example": {"detail": "Restaurant not found"}}
            },
        },
    },
)
def get_restaurant(
    restaurant_id: Annotated[int, Path(description="Stable ID of the restaurant")],
):
    try:
        return restaurant_service.get_restaurant(restaurant_id)
    except restaurant_service.RestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.patch(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantRead,
    summary="Update restaurant information",
    description=(
        "Update supplied fields and preserve omitted fields. "
        "Location and hours objects merge by subfield. "
        "Required text is trimmed and must be nonblank. "
        "Name, cuisine and location cannot be null; "
        "description, logo_url and hours can be cleared with null. "
        "Weekdays can also be cleared with null. "
        "Empty objects, unknown fields and supplied IDs return 422. "
        "Restaurant IDs and menu relationships remain unchanged. "
        "Updates persist across restarts within the "
        "single-process storage model."
    ),
    response_description="The complete persisted restaurant.",
    responses={
        404: {
            "model": ErrorResponse,
            "description": (
                "No restaurant has the requested integer ID."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Restaurant not found"
                    }
                }
            },
        },
        500: {
            "description": (
                "Invalid persisted data or storage failure."
            ),
            "content": {
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "Internal Server Error",
                }
            },
        },
    },
)
def update_restaurant(
    restaurant_id: Annotated[
        int,
        Path(description="Stable ID of the restaurant"),
    ],
    restaurant: Annotated[
        RestaurantUpdate,
        Body(
            openapi_examples={
                "partial": {
                    "summary": (
                        "Change name and city; clear description"
                    ),
                    "value": {
                        "name": "Downtown Café",
                        "location": {
                            "city": "Vancouver"
                        },
                        "description": None,
                    },
                }
            }
        ),
    ],
):
    try:
        return restaurant_service.update_restaurant(
            restaurant_id,
            restaurant,
        )
    except restaurant_service.RestaurantNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
