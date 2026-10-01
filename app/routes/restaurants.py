from fastapi import APIRouter, Query

from app.schemas.restaurant import RestaurantRead
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
