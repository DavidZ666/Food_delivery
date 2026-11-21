"""Tests for cart service architecture and repository interactions."""

from unittest.mock import Mock

from app.repositories import cart_repo, product_repo
from app.schemas.cart import CartItemAdd, CartRead
from app.services import cart_service, customer_service, menu_service


def test_add_item_uses_product_repository_lookup_and_menu_values(monkeypatch):
    customer_id = 7
    product_id = 1
    restaurant_id = 101

    product = {
        "product_id": product_id,
        "restaurant_id": restaurant_id,
        "name": "Taco",
        "price": 4.5,
        "is_available": True,
    }

    existing_cart = {
        "cart_id": 10,
        "customer_id": customer_id,
        "restaurant_id": None,
        "items": [],
    }

    updated_cart = {
        "cart_id": 10,
        "customer_id": customer_id,
        "restaurant_id": restaurant_id,
        "items": [
            {
                "product_id": product_id,
                "name": "Taco",
                "unit_price": 4.5,
                "quantity": 2,
            }
        ],
    }

    require_active = Mock()
    get_cart = Mock(return_value=existing_cart)
    get_product = Mock(return_value=product)
    get_menu_item = Mock(return_value=product)
    add_cart_item = Mock(return_value=updated_cart)
    list_products = Mock()

    monkeypatch.setattr(
        customer_service, "require_active_customer", require_active
    )
    monkeypatch.setattr(cart_repo, "get_by_customer_id", get_cart)
    monkeypatch.setattr(product_repo, "get_by_id", get_product)
    monkeypatch.setattr(product_repo, "list_all", list_products)
    monkeypatch.setattr(menu_service, "get_menu_item", get_menu_item)
    monkeypatch.setattr(cart_repo, "add_item", add_cart_item)

    result = cart_service.add_item(
        customer_id,
        CartItemAdd(product_id=product_id, quantity=2),
    )

    # Check that the returned cart is valid and has the correct totals.
    assert isinstance(result, CartRead)
    assert result.items[0].name == "Taco"
    assert result.items[0].unit_price == 4.5
    assert result.items[0].quantity == 2
    assert result.subtotal == 9.0
    assert result.total == 9.0

    # Check that the service uses the repository to retrieve the product.
    require_active.assert_called_once_with(customer_id)
    get_cart.assert_called_once_with(customer_id)
    get_product.assert_called_once_with(product_id)

    # Check that menu validation receives the correct restaurant and product.
    get_menu_item.assert_called_once_with(restaurant_id, product_id)

    # Check that the cart repository receives the menu's values.
    add_cart_item.assert_called_once_with(
        customer_id,
        restaurant_id,
        {
            "product_id": product_id,
            "name": "Taco",
            "unit_price": 4.5,
            "quantity": 2,
        },
    )

    # The cart service should not directly load the entire product list.
    list_products.assert_not_called()
