"""Shared menu item lookups for the cart and checkout.

Cart and checkout both need to know if a menu item can be ordered. Before this
checkout called cart_service's private _menu_item helper, and each service had
its own MenuItemUnavailableError and its own copy of the availability check.
Now the rule lives here once and both services use it.
"""
from app.repositories import product_repo, restaurant_repo


class MenuItemNotFoundError(LookupError):
    pass


class MenuItemUnavailableError(ValueError):
    pass


def find_menu_item(product_id: int) -> dict:
    """Return the stored menu item, as long as its restaurant still exists."""
    product = product_repo.get_by_id(product_id)
    # an item whose restaurant was deleted can't be ordered, so treat it as missing
    if product is None or restaurant_repo.get_by_id(product["restaurant_id"]) is None:
        raise MenuItemNotFoundError("Menu item not found")
    return product


def get_orderable_item(product_id: int, restaurant_id: int | None = None) -> dict:
    """Return the menu item if a customer can order it right now.

    It has to be available and have a name (the menu schema still allows a blank
    one). If restaurant_id is given the item also has to belong to that
    restaurant, which is how checkout catches an item moved to another restaurant.
    """
    product = find_menu_item(product_id)
    if product["is_available"] is not True or not product["name"].strip():
        raise MenuItemUnavailableError("Menu item is unavailable")
    if restaurant_id is not None and product["restaurant_id"] != restaurant_id:
        raise MenuItemUnavailableError("Menu item is unavailable")
    return product
