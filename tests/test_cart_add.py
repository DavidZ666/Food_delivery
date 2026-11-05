"""Add menu items to the active cart (#84)."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.core import customer_auth
from app.main import app
from app.repositories import cart_repo, customer_repo
from app.schemas.cart import CartItemAdd
from app.services import cart_service, customer_service


PASSWORD = "cart-add-password"
PASSWORD_HASH = customer_auth.hash_password(PASSWORD)
ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
PRODUCTS = [
    {"product_id": 1, "restaurant_id": 101, "name": "Taco", "description": "", "price": 4.5,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 2, "restaurant_id": 101, "name": "Mint", "description": "", "price": 0.1,
     "category": "Extra", "image": "", "is_available": True},
    {"product_id": 3, "restaurant_id": 101, "name": "Sold out", "description": "", "price": 5.0,
     "category": "Main", "image": "", "is_available": False},
    {"product_id": 4, "restaurant_id": 102, "name": "Burger", "description": "", "price": 7.25,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 5, "restaurant_id": 999, "name": "Orphan", "description": "", "price": 2.0,
     "category": "Main", "image": "", "is_available": True},
]
PATH = "/customers/{id}/cart/items"


@pytest.fixture
def accounts(data_dir, monkeypatch):
    (data_dir / "customers.json").write_text("[]", encoding="utf-8")
    (data_dir / "carts.json").write_text("[]", encoding="utf-8")
    (data_dir / "products.json").write_text(json.dumps(PRODUCTS), encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    accounts = {
        name: customer_repo.create({
            "name": name.title(), "email": f"{name}@example.com", "phone": "250-555-0100",
            "delivery_address": ADDRESS, "password_hash": PASSWORD_HASH,
            "role": "customer", "is_active": True,
        })
        for name in ("ada", "bob", "cartless")
    }
    for name in ("ada", "bob"):
        cart_repo.create(accounts[name]["id"])
    return accounts


@pytest.fixture
def http(accounts):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def carts(data_dir):
    return (data_dir / "carts.json").read_bytes()


def add(customer_id, product_id, quantity=1):
    return cart_service.add_item(customer_id, CartItemAdd(product_id=product_id, quantity=quantity))


def line(product, quantity):
    return {"product_id": product["product_id"], "name": product["name"],
            "unit_price": product["price"], "quantity": quantity,
            "line_total": round(product["price"] * quantity, 2)}


# Service

def test_add_sets_restaurant_and_backend_totals(accounts):
    ada = accounts["ada"]["id"]
    cart = add(ada, 1, 2).model_dump()
    assert cart["restaurant_id"] == 101
    assert cart["items"] == [line(PRODUCTS[0], 2)]
    assert cart["subtotal"] == cart["total"] == 9.0
    cart = add(ada, 2, 3).model_dump()
    assert cart["items"] == [line(PRODUCTS[0], 2), line(PRODUCTS[1], 3)]
    assert cart["items"][1]["line_total"] == 0.3
    assert cart["subtotal"] == cart["total"] == 9.3


def test_repeat_add_aggregates_quantity_and_refreshes_menu_values(accounts, data_dir):
    ada = accounts["ada"]["id"]
    add(ada, 1, 2)
    products = [{**PRODUCTS[0], "name": "Taco Supreme", "price": 5.0}, *PRODUCTS[1:]]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    cart = add(ada, 1, 3).model_dump()
    assert cart["items"] == [{"product_id": 1, "name": "Taco Supreme", "unit_price": 5.0,
                              "quantity": 5, "line_total": 25.0}]


@pytest.mark.parametrize("customer,product,error", [
    ("cartless", 1, cart_service.CartNotFoundError),
    ("ada", 99, cart_service.MenuItemNotFoundError),
    ("ada", 5, cart_service.MenuItemNotFoundError),
    ("ada", 3, cart_service.MenuItemUnavailableError),
])
def test_service_rejections_leave_carts_unchanged(accounts, data_dir, customer, product, error):
    before = carts(data_dir)
    with pytest.raises(error):
        add(accounts[customer]["id"], product)
    assert carts(data_dir) == before


def test_cross_restaurant_item_is_rejected_until_cart_is_empty(accounts, data_dir):
    ada = accounts["ada"]["id"]
    add(ada, 1)
    before = carts(data_dir)
    with pytest.raises(cart_service.RestaurantConflictError):
        add(ada, 4)
    assert carts(data_dir) == before
    assert add(accounts["bob"]["id"], 4).restaurant_id == 102


def test_inactive_customer_is_rejected(accounts, data_dir):
    ada = accounts["ada"]["id"]
    customer_service.deactivate_customer(ada)
    before = carts(data_dir)
    with pytest.raises(customer_service.InactiveCustomerError):
        add(ada, 1)
    assert carts(data_dir) == before


def test_concurrent_adds_keep_every_quantity(accounts):
    ada = accounts["ada"]["id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: add(ada, 1), range(20)))
    assert cart_repo.get_by_customer_id(ada)["items"][0]["quantity"] == 20


def test_concurrent_adds_from_two_restaurants_keep_one_restaurant(accounts):
    ada = accounts["ada"]["id"]

    def attempt(product_id):
        try:
            return add(ada, product_id).restaurant_id
        except cart_service.RestaurantConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, [1, 4] * 10))
    stored = cart_repo.get_by_customer_id(ada)
    winners = {result for result in results if result != "conflict"}
    assert winners == {stored["restaurant_id"]}
    assert len(stored["items"]) == 1 and stored["items"][0]["quantity"] == 10
    assert results.count("conflict") == 10


# API

def test_add_item_endpoint_returns_cart(http, accounts, data_dir):
    ada = accounts["ada"]
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 1}, headers=bearer(ada))
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [line(PRODUCTS[0], 1)] and body["total"] == 4.5
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 1, "quantity": 2},
                         headers=bearer(ada))
    assert response.json()["items"][0]["quantity"] == 3
    assert http.get(f"/customers/{ada['id']}/cart", headers=bearer(ada)).json() == response.json()


@pytest.mark.parametrize("customer,body,status,detail", [
    ("cartless", {"product_id": 1}, 404, "Cart not found"),
    ("ada", {"product_id": 99}, 404, "Menu item not found"),
    ("ada", {"product_id": 5}, 404, "Menu item not found"),
    ("ada", {"product_id": 3}, 409, "Menu item is unavailable"),
])
def test_api_rejections(http, accounts, data_dir, customer, body, status, detail):
    before = carts(data_dir)
    response = http.post(PATH.format(id=accounts[customer]["id"]), json=body,
                         headers=bearer(accounts[customer]))
    assert response.status_code == status and response.json() == {"detail": detail}
    assert carts(data_dir) == before


def test_api_cross_restaurant_conflict(http, accounts, data_dir):
    ada = accounts["ada"]
    http.post(PATH.format(id=ada["id"]), json={"product_id": 1}, headers=bearer(ada))
    before = carts(data_dir)
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 4}, headers=bearer(ada))
    assert response.status_code == 409
    assert response.json() == {"detail": "Cart contains items from another restaurant"}
    assert carts(data_dir) == before


@pytest.mark.parametrize("body", [
    {"product_id": 1, "quantity": 0}, {"product_id": 1, "quantity": -1},
    {"product_id": 1, "quantity": "2"}, {"product_id": 1, "quantity": 1.5},
    {"product_id": 1, "quantity": True}, {"quantity": 1}, {"product_id": 0},
    {"product_id": 1, "price": 0.01}, {}, None,
])
def test_invalid_bodies_are_422(http, accounts, data_dir, body):
    before = carts(data_dir)
    ada = accounts["ada"]
    response = http.post(PATH.format(id=ada["id"]), json=body, headers=bearer(ada))
    assert response.status_code == 422
    assert carts(data_dir) == before


@pytest.mark.parametrize("price,quantity", [(4.5, 10 ** 400), (1e308, 2)],
                         ids=["integer-overflow", "float-overflow"])
def test_unrepresentable_total_is_rejected_before_writing(http, accounts, data_dir, price, quantity):
    products = [{**PRODUCTS[0], "price": price}, *PRODUCTS[1:]]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    ada = accounts["ada"]
    before = carts(data_dir)
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 1, "quantity": quantity},
                         headers=bearer(ada))
    assert response.status_code == 422
    assert response.json() == {"detail": "Cart total is too large"}
    assert carts(data_dir) == before
    read = http.get(f"/customers/{ada['id']}/cart", headers=bearer(ada))
    assert read.status_code == 200 and read.json()["items"] == []


@pytest.mark.parametrize("second_product", [1, 2])
def test_aggregated_total_is_checked_inside_transaction(http, accounts, data_dir, second_product):
    products = [{**product, "price": 1e308} for product in PRODUCTS]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    ada = accounts["ada"]
    first = http.post(PATH.format(id=ada["id"]), json={"product_id": 1}, headers=bearer(ada))
    assert first.status_code == 200 and first.json()["total"] == 1e308
    before = carts(data_dir)
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": second_product},
                         headers=bearer(ada))
    assert response.status_code == 422
    assert response.json() == {"detail": "Cart total is too large"}
    assert carts(data_dir) == before
    assert http.get(f"/customers/{ada['id']}/cart", headers=bearer(ada)).json() == first.json()


@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_missing_or_invalid_credentials_are_401(http, accounts, data_dir, authorization):
    before = carts(data_dir)
    headers = {} if authorization is None else {"Authorization": authorization}
    response = http.post(PATH.format(id=accounts["ada"]["id"]), json={"product_id": 1}, headers=headers)
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"
    assert carts(data_dir) == before


def test_cross_customer_and_deactivated_are_403(http, accounts, data_dir):
    ada, bob = accounts["ada"], accounts["bob"]
    before = carts(data_dir)
    response = http.post(PATH.format(id=bob["id"]), json={"product_id": 1}, headers=bearer(ada))
    assert response.status_code == 403
    headers = bearer(ada)
    customer_service.deactivate_customer(ada["id"])
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 1}, headers=headers)
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert carts(data_dir) == before


@pytest.mark.parametrize("filename,content", [
    ("carts.json", "{bad"), ("carts.json", '[{"cart_id": 1}]'), ("products.json", "{}"),
])
def test_malformed_storage_is_500_without_rewrite(http, accounts, data_dir, filename, content):
    path = data_dir / filename
    path.write_text(content, encoding="utf-8")
    before = carts(data_dir)
    ada = accounts["ada"]
    response = http.post(PATH.format(id=ada["id"]), json={"product_id": 1}, headers=bearer(ada))
    assert response.status_code == 500
    assert path.read_text(encoding="utf-8") == content and carts(data_dir) == before


def test_added_items_survive_restart(http, accounts, data_dir):
    ada = accounts["ada"]
    added = http.post(PATH.format(id=ada["id"]), json={"product_id": 2, "quantity": 3},
                      headers=bearer(ada)).json()
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': sys.argv[1], 'password': sys.argv[2]}).json()
    cart = client.get(f"/customers/{login['customer']['id']}/cart",
                      headers={'Authorization': f"Bearer {login['access_token']}"})
    print(json.dumps(cart.json()))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, ada["email"], PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    assert json.loads(result.stdout) == added


def test_openapi_documents_add_item(http):
    document = http.get("/openapi.json").json()
    operation = document["paths"]["/customers/{customer_id}/cart/items"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "403", "404", "409", "422", "500"} <= set(operation["responses"])
    assert operation["summary"] and operation["description"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/CartItemAdd")
    variants = operation["responses"]["422"]["content"]["application/json"]["schema"]["anyOf"]
    assert variants == [{"$ref": "#/components/schemas/HTTPValidationError"},
                        {"$ref": "#/components/schemas/ErrorResponse"}]
    schemas = document["components"]["schemas"]
    assert schemas["HTTPValidationError"]["properties"]["detail"]["type"] == "array"
    assert schemas["ErrorResponse"]["properties"]["detail"]["type"] == "string"
