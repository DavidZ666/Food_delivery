from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
    Path,
    Query,
)

from app.core.api_contract import (
    RESTAURANT_CREATE, RESTAURANT_READ, RESTAURANT_UPDATED, STORAGE_FAILURE,
    json_response, validation_example,
)
from app.schemas.error import ErrorResponse
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantRead,
    RestaurantUpdate,
)
from app.services import restaurant_service

router = APIRouter(responses={500: STORAGE_FAILURE})


@router.get(
    "/restaurants",
    response_model=list[RestaurantRead],
    summary="List, search or filter restaurants",
    description=(
        "Return stored restaurants in storage order. "
        "Name search uses a case-insensitive literal substring. "
        "Cuisine filtering uses a case-insensitive exact match. "
        "Surrounding query whitespace is ignored. "
        "Omitted or blank parameters impose no restriction. "
        "When both parameters are supplied, both must match. "
        "No matches return HTTP 200 with an empty list. "
        "Reads do not modify stored data. "
        "Storage failures remain server errors."
    ),
    response_description="The matching restaurants.",
    responses={
        200: json_response([RESTAURANT_READ], "Stored-order results; [] when empty or unmatched."),
        500: {
            "description": "Stored data could not be read or processed.",
            "content": {
                "text/plain": {
                    "schema": {"type": "string"},
                    "example": "Internal Server Error",
                }
            },
        },
    },
)
def list_restaurants(
    name: str | None = Query(
        default=None,
        examples=["café"],
        description=(
            "Case-insensitive literal name substring. "
            "Surrounding whitespace is ignored. "
            "Omitted or blank values do not restrict names."
        ),
    ),
    cuisine: str | None = Query(
        default=None,
        examples=["Fusion"],
        description=(
            "Case-insensitive exact cuisine match. "
            "Surrounding whitespace is ignored. "
            "Omitted or blank values do not restrict cuisine."
        ),
    ),
):
    return restaurant_service.list_restaurants(
        name=name,
        cuisine=cuisine,
    )


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
    responses={201: json_response(RESTAURANT_READ, "Created restaurant with generated ID.")},
    openapi_extra=validation_example(body=True, path=False),
)
def create_restaurant(restaurant: Annotated[RestaurantCreate, Body(
    openapi_examples={"create": {"summary": "Create a restaurant", "value": RESTAURANT_CREATE}}
)]):
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
        200: json_response(RESTAURANT_READ, "The requested restaurant, including optional fields."),
        404: {
            "model": ErrorResponse,
            "description": "No restaurant has the requested ID.",
            "content": {
                "application/json": {"example": {"detail": "Restaurant not found"}}
            },
        },
    },
    openapi_extra=validation_example(),
)
def get_restaurant(
    restaurant_id: Annotated[int, Path(description="Stored integer restaurant ID; an unknown integer returns 404.", examples=[1])],
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
        200: json_response(RESTAURANT_UPDATED, "Complete restaurant after the partial-update example."),
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
    openapi_extra=validation_example(),
)
def update_restaurant(
    restaurant_id: Annotated[
        int,
        Path(description="Stored integer restaurant ID; an unknown integer returns 404.", examples=[1]),
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
