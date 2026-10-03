from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.schemas.error import ErrorResponse
from app.schemas.restaurant import RestaurantRead
from app.services import restaurant_service

router = APIRouter()


@router.get("/restaurants", response_model=list[RestaurantRead])
def list_restaurants():
    return restaurant_service.list_restaurants()


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
