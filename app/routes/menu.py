from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.schemas.menu import MenuError, MenuItemRead
from app.services import menu_service

router = APIRouter()
RestaurantId = Annotated[int, Path(description="Stored restaurant ID.")]
ProductId = Annotated[int, Path(description="Stored product ID belonging to this restaurant.")]


@router.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=list[MenuItemRead],
    summary="Browse a restaurant menu",
    description="Return the restaurant's stored menu items in storage order, "
                "including unavailable items. An existing restaurant with no "
                "items returns an empty list.",
    responses={404: {"model": MenuError, "description": "Restaurant not found."}},
)
def list_menu(restaurant_id: RestaurantId):
    try:
        return menu_service.list_menu(restaurant_id)
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None


@router.get(
    "/restaurants/{restaurant_id}/menu/{product_id}",
    response_model=MenuItemRead,
    summary="Retrieve a restaurant menu item",
    description="Return a stored item belonging to the selected restaurant. "
                "Unknown items and items belonging to another restaurant "
                "return Menu item not found. Restaurant existence is checked first.",
    responses={404: {"model": MenuError, "description":
                    "Restaurant not found, or Menu item not found."}},
)
def get_menu_item(restaurant_id: RestaurantId, product_id: ProductId):
    try:
        return menu_service.get_menu_item(restaurant_id, product_id)
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None
    except menu_service.MenuItemNotFound:
        raise HTTPException(status_code=404, detail="Menu item not found") from None
