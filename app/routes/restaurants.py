from fastapi import APIRouter

from app.schemas.restaurant import RestaurantRead
from app.services import restaurant_service

router = APIRouter()


@router.get("/restaurants", response_model=list[RestaurantRead])
def list_restaurants():
    return restaurant_service.list_restaurants()