"""Update quantities, remove items and clear the active cart (#86)."""
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
from app.schemas.cart import CartItemAdd, CartItemUpdate
from app.services import cart_service, customer_service


PASSWORD = "cart-edit-password"
PASSWORD_HASH = customer_auth.hash_password(PASSWORD)
ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
PRODUCTS = [
    {"product_id": 1, "restaurant_id": 101, "name": "Taco", "description": "", "price": 4.5,
     "category": "Main", "image": "", "is_available": True},
    {"product_id": 2, "restaurant_id": 101, "name": "Mint", "description": "", "price": 0.1,
     "category": "Extra", "image": "", "is_available": True},
    {"product_id": 4, "restaurant_id": 102, "name": "Burger", "description": "", "price": 7.25,
     "category": "Main", "image": "", "is_available": True},
]
OPERATIONS = [
    ("patch", "/customers/{id}/cart/items/1", {"quantity": 5}),
    ("delete", "/customers/{id}/cart/items/1", None),
    ("delete", "/customers/{id}/cart/items", None),
]


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
        add(accounts[name]["id"], 1, 2)
        add(accounts[name]["id"], 2, 3)
    return accounts


@pytest.fixture
def http(accounts):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def carts(data_dir):
    return (data_dir / "carts.json").read_bytes()


@pytest.mark.parametrize("quantity", [10 ** 400, 10 ** 308], ids=["integer-overflow", "float-overflow"])
def test_update_rejects_unrepresentable_total_without_writing(http, accounts, data_dir, quantity):
    ada = accounts["ada"]
    before = carts(data_dir)
    response = http.patch(f"/customers/{ada['id']}/cart/items/1", json={"quantity": quantity},
                          headers=bearer(ada))
    assert response.status_code == 422
    assert response.json() == {"detail": "Cart total is too large"}
    assert carts(data_dir) == before
    read = http.get(f"/customers/{ada['id']}/cart", headers=bearer(ada))
    assert read.status_code == 200 and read.json()["total"] == 9.3


def add(customer_id, product_id, quantity=1):
    return cart_service.add_item(customer_id, CartItemAdd(product_id=product_id, quantity=quantity))


def call(http, method, path, account, body=None, headers=None):
    return http.request(method, path.format(id=account["id"]), json=body,
                        headers=bearer(account) if headers is None else headers)


# Service

def test_update_sets_quantity_and_recalculates(accounts):
    ada = accounts["ada"]["id"]
    cart = cart_service.update_item(ada, 1, CartItemUpdate(quantity=5))
    assert [(item.product_id, item.quantity, item.line_total) for item in cart.items] == [(1, 5, 22.5), (2, 3, 0.3)]
    assert cart.subtotal == cart.total == 22.8
    assert cart.items[0].name == "Taco" and cart.items[0].unit_price == 4.5
    assert cart_service.get_cart(ada) == cart


def test_remove_one_of_several_keeps_restaurant(accounts):
    ada = accounts["ada"]["id"]
    cart = cart_service.remove_item(ada, 1)
    assert [item.product_id for item in cart.items] == [2]
    assert cart.restaurant_id == 101 and cart.total == 0.3


def test_removing_last_item_resets_restaurant_binding(accounts):
    ada = accounts["ada"]["id"]
    cart_service.remove_item(ada, 1)
    cart = cart_service.remove_item(ada, 2)
    assert cart.items == [] and cart.restaurant_id is None and cart.subtotal == cart.total == 0
    assert add(ada, 4).restaurant_id == 102


def test_clear_keeps_cart_id_and_is_idempotent(accounts):
    ada = accounts["ada"]["id"]
    cart_id = cart_service.get_cart(ada).cart_id
    for _ in range(2):
        cart = cart_service.clear_cart(ada)
        assert (cart.cart_id, cart.items, cart.restaurant_id, cart.total) == (cart_id, [], None, 0)
    assert add(ada, 4).restaurant_id == 102


def test_unknown_item_and_missing_cart(accounts, data_dir):
    ada, cartless = accounts["ada"]["id"], accounts["cartless"]["id"]
    before = carts(data_dir)
    with pytest.raises(cart_service.CartItemNotFoundError, match="Cart item not found"):
        cart_service.update_item(ada, 4, CartItemUpdate(quantity=1))
    with pytest.raises(cart_service.CartItemNotFoundError):
        cart_service.remove_item(ada, 4)
    for operation in (lambda: cart_service.update_item(cartless, 1, CartItemUpdate(quantity=1)),
                      lambda: cart_service.remove_item(cartless, 1),
                      lambda: cart_service.clear_cart(cartless)):
        with pytest.raises(cart_service.CartNotFoundError, match="Cart not found"):
            operation()
    assert carts(data_dir) == before


def test_deactivated_customer_is_rejected(accounts, data_dir):
    ada = accounts["ada"]["id"]
    customer_service.deactivate_customer(ada)
    before = carts(data_dir)
    for operation in (lambda: cart_service.update_item(ada, 1, CartItemUpdate(quantity=1)),
                      lambda: cart_service.remove_item(ada, 1),
                      lambda: cart_service.clear_cart(ada)):
        with pytest.raises(customer_service.InactiveCustomerError):
            operation()
    assert carts(data_dir) == before


def test_concurrent_updates_to_different_items_are_all_kept(accounts):
    ada = accounts["ada"]["id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: cart_service.update_item(ada, 1 + i % 2, CartItemUpdate(quantity=10 + i % 2)),
                      range(20)))
    cart = cart_service.get_cart(ada)
    assert {item.product_id: item.quantity for item in cart.items} == {1: 10, 2: 11}
    assert cart.total == round(4.5 * 10 + 0.1 * 11, 2)


# API

def test_api_update_remove_and_clear(http, accounts):
    ada = accounts["ada"]
    response = call(http, "patch", "/customers/{id}/cart/items/2", ada, {"quantity": 10})
    assert response.status_code == 200
    assert response.json()["subtotal"] == response.json()["total"] == 10.0
    response = call(http, "delete", "/customers/{id}/cart/items/2", ada)
    assert response.status_code == 200 and [i["product_id"] for i in response.json()["items"]] == [1]
    response = call(http, "delete", "/customers/{id}/cart/items", ada)
    body = response.json()
    assert response.status_code == 200
    assert (body["items"], body["restaurant_id"], body["subtotal"], body["total"]) == ([], None, 0, 0)
    assert call(http, "delete", "/customers/{id}/cart/items", ada).status_code == 200


@pytest.mark.parametrize("body", [
    {"quantity": 0}, {"quantity": -1}, {"quantity": "2"}, {"quantity": 1.5}, {"quantity": True},
    {"quantity": None}, {}, {"quantity": 2, "price": 0.01}, None,
])
def test_invalid_quantity_is_422_without_changes(http, accounts, data_dir, body):
    before = carts(data_dir)
    response = call(http, "patch", "/customers/{id}/cart/items/1", accounts["ada"], body)
    assert response.status_code == 422
    assert carts(data_dir) == before


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize("product_id", ["0", "-1", "abc"])
def test_invalid_product_id_is_422(http, accounts, data_dir, method, product_id):
    before = carts(data_dir)
    response = call(http, method, f"/customers/{{id}}/cart/items/{product_id}", accounts["ada"], {"quantity": 1})
    assert response.status_code == 422
    assert carts(data_dir) == before


@pytest.mark.parametrize("method,path,body", OPERATIONS)
def test_errors_leave_storage_unchanged(http, accounts, data_dir, method, path, body):
    ada, bob = accounts["ada"], accounts["bob"]
    before = carts(data_dir)
    for headers, status, detail in [
        ({}, 401, "Invalid credentials"),
        ({"Authorization": "Bearer unknown"}, 401, "Invalid credentials"),
        (bearer(bob), 403, "Forbidden"),
    ]:
        response = call(http, method, path, ada, body, headers)
        assert (response.status_code, response.json()) == (status, {"detail": detail})
    response = call(http, method, path, accounts["cartless"], body)
    assert (response.status_code, response.json()) == (404, {"detail": "Cart not found"})
    if path.endswith("/1"):
        missing = path.replace("/1", "/4")
        response = call(http, method, missing, ada, body)
        assert (response.status_code, response.json()) == (404, {"detail": "Cart item not found"})
    customer_service.deactivate_customer(ada["id"])
    response = call(http, method, path, ada, body)
    assert (response.status_code, response.json()) == (403, {"detail": "Forbidden"})
    assert carts(data_dir) == before


@pytest.mark.parametrize("method,path,body", OPERATIONS)
@pytest.mark.parametrize("content", ["{bad", "{}", '[{"cart_id": 1}]'])
def test_malformed_storage_is_500_unchanged(http, accounts, data_dir, method, path, body, content):
    (data_dir / "carts.json").write_text(content, encoding="utf-8")
    response = call(http, method, path, accounts["ada"], body)
    assert response.status_code == 500
    assert (data_dir / "carts.json").read_text(encoding="utf-8") == content


def test_changes_survive_restart(http, accounts, data_dir):
    ada = accounts["ada"]
    call(http, "patch", "/customers/{id}/cart/items/1", ada, {"quantity": 4})
    expected = call(http, "delete", "/customers/{id}/cart/items/2", ada).json()
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': sys.argv[1], 'password': sys.argv[2]}).json()
    cart = client.get(f"/customers/{login['customer']['id']}/cart",
                      headers={'Authorization': f"Bearer {login['access_token']}"})
    print(json.dumps([cart.status_code, cart.json()]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, ada["email"], PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    assert json.loads(result.stdout) == [200, expected]


def test_openapi_documents_edit_routes(http):
    document = http.get("/openapi.json").json()
    paths = document["paths"]
    item = "/customers/{customer_id}/cart/items/{product_id}"
    for method, path in [("patch", item), ("delete", item), ("delete", "/customers/{customer_id}/cart/items")]:
        operation = paths[path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert {"200", "401", "403", "404", "422", "500"} <= set(operation["responses"])
        assert operation["summary"] and operation["description"]
    body = paths[item]["patch"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert body.endswith("/CartItemUpdate")
    variants = paths[item]["patch"]["responses"]["422"]["content"]["application/json"]["schema"]["anyOf"]
    assert variants == [{"$ref": "#/components/schemas/HTTPValidationError"},
                        {"$ref": "#/components/schemas/ErrorResponse"}]
    schemas = document["components"]["schemas"]
    assert schemas["HTTPValidationError"]["properties"]["detail"]["type"] == "array"
    assert schemas["ErrorResponse"]["properties"]["detail"]["type"] == "string"
