from fastapi import APIRouter

from app.schemas.restaurant import RestaurantCreate, RestaurantRead
from app.services import restaurant_service

router = APIRouter()


@router.get("/restaurants", response_model=list[RestaurantRead])
def list_restaurants():
    return restaurant_service.list_restaurants()


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
