"""Checkout: revalidate the cart, persist an order snapshot, then clear the cart (#90)."""
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
from app.repositories import cart_repo, customer_repo, order_repo
from app.schemas.cart import CartItemAdd
from app.schemas.order import Order
from app.services import cart_service, checkout_service, customer_service


PASSWORD = "checkout-password"
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


@pytest.fixture
def accounts(data_dir, monkeypatch):
    for name in ("customers.json", "carts.json", "orders.json"):
        (data_dir / name).write_text("[]", encoding="utf-8")
    (data_dir / "products.json").write_text(json.dumps(PRODUCTS), encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    accounts = {
        name: customer_repo.create({
            "name": name.title(), "email": f"{name}@example.com", "phone": "250-555-0100",
            "delivery_address": ADDRESS, "password_hash": PASSWORD_HASH,
            "role": "customer", "is_active": True,
        })
        for name in ("ada", "bob", "cartless", "empty")
    }
    for name in ("ada", "bob", "empty"):
        cart_repo.create(accounts[name]["id"])
    for name in ("ada", "bob"):
        add(accounts[name]["id"], 1, 2)
        add(accounts[name]["id"], 2, 3)
    return accounts


@pytest.fixture
def http(accounts):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def add(customer_id, product_id, quantity=1):
    return cart_service.add_item(customer_id, CartItemAdd(product_id=product_id, quantity=quantity))


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def checkout(http, account, headers=None):
    return http.post(f"/customers/{account['id']}/checkout",
                     headers=bearer(account) if headers is None else headers)


def storage(data_dir):
    return [(data_dir / name).read_bytes() for name in ("carts.json", "orders.json")]


def set_product(data_dir, product_id, **changes):
    path = data_dir / "products.json"
    products = json.loads(path.read_text(encoding="utf-8"))
    for product in products:
        if product["product_id"] == product_id:
            product.update(changes)
    path.write_text(json.dumps(products), encoding="utf-8")


def cart_of(account):
    return cart_repo.get_by_customer_id(account["id"])


# Success

def test_checkout_saves_snapshot_and_clears_cart(http, accounts, data_dir):
    ada = accounts["ada"]
    cart_id = cart_of(ada)["cart_id"]
    response = checkout(http, ada)
    assert response.status_code == 201
    order = response.json()
    assert order_repo.list_all() == [order]
    Order.model_validate(order, strict=True)
    assert {key: order[key] for key in ("order_id", "customer_id", "restaurant_id", "status")} == {
        "order_id": 1, "customer_id": ada["id"], "restaurant_id": 101, "status": "placed"}
    assert order["delivery_address"] == ADDRESS
    assert order["items"] == [
        {"product_id": 1, "name": "Taco", "unit_price": 4.5, "quantity": 2, "line_total": 9.0},
        {"product_id": 2, "name": "Mint", "unit_price": 0.1, "quantity": 3, "line_total": 0.3},
    ]
    assert order["subtotal"] == order["total"] == 9.3
    assert order["created_at"].endswith("Z")
    assert cart_of(ada) == {"cart_id": cart_id, "customer_id": ada["id"], "restaurant_id": None, "items": []}
    assert cart_of(accounts["bob"])["items"]  # other carts untouched


def test_checkout_uses_current_menu_names_and_prices(http, accounts, data_dir):
    set_product(data_dir, 1, price=5.25, name="Taco Supreme")
    order = checkout(http, accounts["ada"]).json()
    assert order["items"][0] == {"product_id": 1, "name": "Taco Supreme", "unit_price": 5.25,
                                 "quantity": 2, "line_total": 10.5}
    assert order["subtotal"] == order["total"] == 10.8


def test_delivery_address_is_a_snapshot(http, accounts):
    ada = accounts["ada"]
    order = checkout(http, ada).json()
    customer_repo.update_by_id(ada["id"], {"delivery_address": {"city": "Vancouver"}})
    assert order_repo.get_by_id(order["order_id"])["delivery_address"] == ADDRESS


# Revalidation and rejected checkouts

@pytest.mark.parametrize("change", ["unavailable", "removed", "restaurant_deleted"])
def test_items_no_longer_orderable_are_409_without_changes(http, accounts, data_dir, change):
    if change == "unavailable":
        set_product(data_dir, 2, is_available=False)
    elif change == "removed":
        products = [p for p in PRODUCTS if p["product_id"] != 2]
        (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    else:
        restaurants = json.loads((data_dir / "restaurants.json").read_text(encoding="utf-8"))
        (data_dir / "restaurants.json").write_text(
            json.dumps([r for r in restaurants if r["id"] != 101]), encoding="utf-8")
    before = storage(data_dir)
    response = checkout(http, accounts["ada"])
    assert response.status_code == 409 and response.json() == {"detail": "Menu item is unavailable"}
    assert storage(data_dir) == before


def test_item_moved_to_another_restaurant_is_409(http, accounts, data_dir):
    set_product(data_dir, 2, restaurant_id=102)
    before = storage(data_dir)
    response = checkout(http, accounts["ada"])
    assert response.status_code == 409 and response.json() == {"detail": "Menu item is unavailable"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("name,status,detail", [
    ("empty", 409, "Cart is empty"), ("cartless", 404, "Cart not found"),
])
def test_empty_or_missing_cart(http, accounts, data_dir, name, status, detail):
    before = storage(data_dir)
    response = checkout(http, accounts[name])
    assert response.status_code == status and response.json() == {"detail": detail}
    assert storage(data_dir) == before


def test_deactivated_customer_is_403(http, accounts, data_dir):
    ada = accounts["ada"]
    headers = bearer(ada)
    customer_service.deactivate_customer(ada["id"])
    before = storage(data_dir)
    response = checkout(http, ada, headers)
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before
    with pytest.raises(customer_service.InactiveCustomerError):
        checkout_service.checkout(ada["id"])


@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_missing_or_invalid_credentials_are_401(http, accounts, data_dir, authorization):
    before = storage(data_dir)
    headers = {} if authorization is None else {"Authorization": authorization}
    response = checkout(http, accounts["ada"], headers)
    assert response.status_code == 401 and response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert storage(data_dir) == before


def test_other_customers_cart_is_403(http, accounts, data_dir):
    before = storage(data_dir)
    response = http.post(f"/customers/{accounts['bob']['id']}/checkout", headers=bearer(accounts["ada"]))
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


def test_invalid_customer_id_is_422(http, accounts):
    assert http.post("/customers/abc/checkout", headers=bearer(accounts["ada"])).status_code == 422


# Failure safety and concurrency

def test_order_write_failure_leaves_cart_and_orders_unchanged(http, accounts, data_dir, monkeypatch):
    def fail(fields):
        raise OSError("simulated order write failure")

    monkeypatch.setattr(order_repo, "create", fail)
    before = storage(data_dir)
    response = checkout(http, accounts["ada"])
    assert response.status_code == 500
    assert storage(data_dir) == before


def test_malformed_orders_storage_is_500_without_changes(http, accounts, data_dir):
    (data_dir / "orders.json").write_text("{bad", encoding="utf-8")
    before = storage(data_dir)
    assert checkout(http, accounts["ada"]).status_code == 500
    assert storage(data_dir) == before


def test_cart_clear_failure_after_save_still_returns_the_order(http, accounts, data_dir, monkeypatch, caplog):
    def fail(*args):
        raise OSError("simulated cart write failure")

    monkeypatch.setattr(cart_repo, "clear_if_unchanged", fail)
    cart = cart_of(accounts["ada"])
    with caplog.at_level("WARNING", logger="app.services.checkout_service"):
        response = checkout(http, accounts["ada"])
    assert response.status_code == 201
    assert order_repo.list_all() == [response.json()]
    assert cart_of(accounts["ada"]) == cart
    # The kept cart must be visible to operators, not silently ignored.
    assert any(f"order {response.json()['order_id']}" in record.getMessage() and record.levelname == "WARNING"
               for record in caplog.records)


def test_cart_changed_during_checkout_is_not_cleared(accounts, monkeypatch):
    ada = accounts["ada"]
    create = order_repo.create

    def change_cart_then_save(fields):
        add(ada["id"], 1, 1)  # a concurrent add lands between the snapshot and the clear
        return create(fields)

    monkeypatch.setattr(order_repo, "create", change_cart_then_save)
    order = checkout_service.checkout(ada["id"])
    assert [item.quantity for item in order.items] == [2, 3]
    assert [item["quantity"] for item in cart_of(ada)["items"]] == [3, 3]


def test_concurrent_checkouts_create_one_order(accounts):
    ada = accounts["ada"]

    def attempt(_):
        try:
            return checkout_service.checkout(ada["id"]).order_id
        except checkout_service.EmptyCartError:
            return "empty"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sorted(results, key=str) == [1, *["empty"] * 7]
    assert len(order_repo.list_all()) == 1
    assert cart_of(ada)["items"] == []


def test_order_and_empty_cart_survive_restart(http, accounts, data_dir):
    ada = accounts["ada"]
    order = checkout(http, ada).json()
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
from app.repositories import order_repo
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': sys.argv[1], 'password': sys.argv[2]}).json()
    cart = client.get(f"/customers/{login['customer']['id']}/cart",
                      headers={'Authorization': f"Bearer {login['access_token']}"}).json()
    print(json.dumps([order_repo.list_by_customer(login['customer']['id']), cart]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, ada["email"], PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    orders, cart = json.loads(result.stdout)
    assert orders == [order]
    assert cart["items"] == [] and cart["restaurant_id"] is None and cart["total"] == 0


def test_openapi_documents_checkout(http):
    operation = http.get("/openapi.json").json()["paths"]["/customers/{customer_id}/checkout"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"201", "401", "403", "404", "409", "422", "500"} <= set(operation["responses"])
    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith("/Order")
    assert operation["summary"] and operation["description"]
