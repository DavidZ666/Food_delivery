from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.error import ErrorResponse
from app.schemas.restaurant import RestaurantCreate, RestaurantRead
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
