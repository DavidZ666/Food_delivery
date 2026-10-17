from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, Response, status

from app.core.api_contract import (
    ITEM_CREATE, ITEM_READ, ITEM_PATCH, STORAGE_FAILURE,
    json_response, resource_error, validation_example,
)
from app.schemas.menu import MenuError, MenuItemRead, MenuItemCreate, MenuItemUpdate
from app.services import menu_service

router = APIRouter(responses={500: STORAGE_FAILURE})
RestaurantId = Annotated[int, Path(description="Stored integer restaurant ID; unknown integers return 404.", examples=[1])]
ProductId = Annotated[int, Path(description="Stored product ID belonging to this restaurant; unknown or wrong-owner items return 404.", examples=[1])]


@router.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=list[MenuItemRead],
    summary="Browse a restaurant menu",
    description="Return the restaurant's stored menu items in storage order, "
                "including unavailable items. An existing restaurant with no "
                "items returns an empty list.",
    responses={200: json_response([ITEM_READ], "Menu in storage order, including unavailable items; [] for an empty menu."),
               404: resource_error(MenuError)},
    openapi_extra=validation_example(),
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
    responses={200: json_response(ITEM_READ), 404: resource_error(MenuError, item=True)},
    openapi_extra=validation_example(),
)
def get_menu_item(restaurant_id: RestaurantId, product_id: ProductId):
    try:
        return menu_service.get_menu_item(restaurant_id, product_id)
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None
    except menu_service.MenuItemNotFound:
        raise HTTPException(status_code=404, detail="Menu item not found") from None

@router.post(
    "/restaurants/{restaurant_id}/menu",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a menu item",
    description="Create an item with a generated ID under an existing restaurant. "
                "Name and category are nonempty; price must be positive and finite. "
                "Unknown fields and supplied IDs are ignored. "
                "ID allocation and append use one serialized storage transaction. "
                "Invalid stored product fields or IDs and storage failures return 500.",
    responses={201: json_response(ITEM_READ, "Created item with generated ID and restaurant ownership."),
               404: resource_error(MenuError)},
    openapi_extra=validation_example(body=True),
)
def create_menu_item(restaurant_id: RestaurantId, body: Annotated[MenuItemCreate, Body(
    openapi_examples={"create": {"summary": "Create a menu item", "value": ITEM_CREATE}}
)]):
    try:
        return menu_service.create_menu_item(restaurant_id, body.model_dump())
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None


@router.patch(
    "/restaurants/{restaurant_id}/menu/{product_id}",
    response_model=MenuItemRead,
    summary="Update a menu item",
    description="Update supplied fields of an item belonging to this restaurant. "
                "Omitted fields are preserved; explicit nulls are rejected. "
                "Empty or unknown-only objects are no-ops; IDs cannot be changed. "
                "Price must be positive and finite. Storage failures return 500.",
    responses={200: json_response({**ITEM_READ, **ITEM_PATCH}), 404: resource_error(MenuError, item=True)},
    openapi_extra=validation_example(),
)
def update_menu_item(restaurant_id: RestaurantId, product_id: ProductId, body: Annotated[MenuItemUpdate, Body(
    openapi_examples={"partial": {"summary": "Change price and availability", "value": ITEM_PATCH},
                      "noop": {"summary": "Keep all values unchanged", "value": {}}}
)]):
    changes = body.model_dump(exclude_unset=True)
    try:
        return menu_service.update_menu_item(restaurant_id, product_id, changes)
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None
    except menu_service.MenuItemNotFound:
        raise HTTPException(status_code=404, detail="Menu item not found") from None


@router.delete(
    "/restaurants/{restaurant_id}/menu/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a menu item",
    description="Remove an item owned by this restaurant. Return 204 with no body; "
                "unknown resources return 404 and storage failures return 500.",
    responses={204: {"description": "Removed successfully. Empty response body."},
               404: resource_error(MenuError, item=True)},
    openapi_extra=validation_example(),
)
def delete_menu_item(restaurant_id: RestaurantId, product_id: ProductId):
    try:
        menu_service.delete_menu_item(restaurant_id, product_id)
    except menu_service.RestaurantNotFound:
        raise HTTPException(status_code=404, detail="Restaurant not found") from None
    except menu_service.MenuItemNotFound:
        raise HTTPException(status_code=404, detail="Menu item not found") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
