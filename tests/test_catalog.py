"""Shared menu item lookup used by the cart and checkout."""
import json

import pytest

from app.services import catalog


PRODUCTS = [
    {"product_id": 1, "restaurant_id": 101, "name": "Taco", "description": "", "price": 4.5,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 2, "restaurant_id": 101, "name": "Sold out", "description": "", "price": 5.0,
     "category": "Main", "image": "", "is_available": False},
    {"product_id": 3, "restaurant_id": 101, "name": "  ", "description": "", "price": 1.0,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 4, "restaurant_id": 102, "name": "Burger", "description": "", "price": 7.25,
     "category": "Main", "image": "", "is_available": True},
    # restaurant 999 doesn't exist anymore
    {"product_id": 5, "restaurant_id": 999, "name": "Orphan", "description": "", "price": 2.0,
     "category": "Main", "image": "", "is_available": True},
]


@pytest.fixture
def products(data_dir):
    path = data_dir / "products.json"
    path.write_text(json.dumps(PRODUCTS), encoding="utf-8")
    return path


def test_finds_an_item_whose_restaurant_exists(products):
    assert catalog.find_menu_item(1) == PRODUCTS[0]
    # finding it doesn't care if it's available, that's get_orderable_item's job
    assert catalog.find_menu_item(2) == PRODUCTS[1]


@pytest.mark.parametrize("product_id", [99, 5])
def test_unknown_items_and_items_of_deleted_restaurants_are_not_found(products, product_id):
    with pytest.raises(catalog.MenuItemNotFoundError, match="Menu item not found"):
        catalog.find_menu_item(product_id)
    with pytest.raises(catalog.MenuItemNotFoundError):
        catalog.get_orderable_item(product_id)


def test_orderable_item_is_returned(products):
    assert catalog.get_orderable_item(1) == PRODUCTS[0]
    assert catalog.get_orderable_item(4, restaurant_id=102) == PRODUCTS[3]


@pytest.mark.parametrize("product_id", [2, 3])
def test_unavailable_or_blank_named_items_cant_be_ordered(products, product_id):
    with pytest.raises(catalog.MenuItemUnavailableError, match="Menu item is unavailable"):
        catalog.get_orderable_item(product_id)


def test_item_from_a_different_restaurant_cant_be_ordered(products):
    # checkout passes the cart's restaurant so a moved item gets caught
    with pytest.raises(catalog.MenuItemUnavailableError):
        catalog.get_orderable_item(4, restaurant_id=101)


def test_lookups_dont_write_anything(products, data_dir):
    before = [(data_dir / name).read_bytes() for name in ("products.json", "restaurants.json")]
    catalog.get_orderable_item(1)
    with pytest.raises(catalog.MenuItemUnavailableError):
        catalog.get_orderable_item(2)
    assert [(data_dir / name).read_bytes() for name in ("products.json", "restaurants.json")] == before
