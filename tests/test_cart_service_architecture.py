"""Product lookup by ID, and adding to the cart through it, against real temp data."""
import json

import pytest

from app.core import customer_auth
from app.repositories import cart_repo, customer_repo, product_repo
from app.schemas.cart import CartItemAdd, CartRead
from app.services import cart_service


ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
PRODUCTS = [
    {"product_id": 1, "restaurant_id": 101, "name": "Taco", "description": "", "price": 4.5,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 2, "restaurant_id": 101, "name": "Sold out", "description": "", "price": 5.0,
     "category": "Main", "image": "", "is_available": False},
    {"product_id": 7, "restaurant_id": 102, "name": "Burger", "description": "", "price": 7.25,
     "category": "Main", "image": "", "is_available": True},
]


@pytest.fixture
def products(data_dir):
    path = data_dir / "products.json"
    path.write_text(json.dumps(PRODUCTS), encoding="utf-8")
    return path


@pytest.fixture
def customer(products, data_dir):
    (data_dir / "carts.json").write_text("[]", encoding="utf-8")
    created = customer_repo.create({
        "name": "Ada", "email": "ada@example.com", "phone": "250-555-0100",
        "delivery_address": ADDRESS, "password_hash": customer_auth.hash_password("cart-lookup-password"),
        "role": "customer", "is_active": True,
    })
    cart_repo.create(created["id"])
    return created


def stored_cart(data_dir, customer_id):
    carts = json.loads((data_dir / "carts.json").read_text(encoding="utf-8"))
    return next(cart for cart in carts if cart["customer_id"] == customer_id)


@pytest.mark.parametrize("product_id", [1, 2, 7])
def test_get_by_id_returns_the_stored_product(products, product_id):
    expected = next(p for p in PRODUCTS if p["product_id"] == product_id)
    assert product_repo.get_by_id(product_id) == expected


@pytest.mark.parametrize("product_id", [3, 99])
def test_get_by_id_returns_none_for_missing_ids(products, product_id):
    # 3 sits between stored IDs, 99 is past them
    assert product_repo.get_by_id(product_id) is None


def test_get_by_id_does_not_write(products):
    before = products.read_bytes()
    product_repo.get_by_id(1)
    product_repo.get_by_id(99)
    assert products.read_bytes() == before


def test_add_item_looks_up_the_product_by_id_and_stores_menu_values(customer, data_dir, monkeypatch):
    looked_up = []
    real_get_by_id = product_repo.get_by_id

    def spy(product_id):
        looked_up.append(product_id)
        return real_get_by_id(product_id)

    monkeypatch.setattr(product_repo, "get_by_id", spy)

    result = cart_service.add_item(customer["id"], CartItemAdd(product_id=1, quantity=2))

    assert looked_up == [1]
    assert isinstance(result, CartRead)
    assert (result.restaurant_id, result.subtotal, result.total) == (101, 9.0, 9.0)
    # name and price come from the stored menu, and the cart on disk matches
    cart = stored_cart(data_dir, customer["id"])
    assert cart["restaurant_id"] == 101
    assert cart["items"] == [{"product_id": 1, "name": "Taco", "unit_price": 4.5, "quantity": 2}]


@pytest.mark.parametrize("product_id,error,detail", [
    (99, LookupError, "Menu item not found"),
    (2, ValueError, "Menu item is unavailable"),
])
def test_add_item_rejects_missing_or_unavailable_items_without_writing(
        customer, data_dir, product_id, error, detail):
    before = (data_dir / "carts.json").read_bytes()
    with pytest.raises(error, match=detail):
        cart_service.add_item(customer["id"], CartItemAdd(product_id=product_id, quantity=1))
    assert (data_dir / "carts.json").read_bytes() == before
