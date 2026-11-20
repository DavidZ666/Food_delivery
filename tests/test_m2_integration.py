"""M2 customer to order workflow through the API (#101).

Everything goes through real routes, services and repositories against a
temporary data folder, so committed data/ files are never touched.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app


PASSWORD = "integration-password"
ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}


@pytest.fixture
def store(data_dir):
    for name in ("products.json", "carts.json", "orders.json"):
        (data_dir / name).write_text("[]", encoding="utf-8")
    return data_dir


@pytest.fixture
def manager(store, client):
    """Restaurant owner client, used to set up and change the menu."""
    return client


@pytest.fixture
def anon(store):
    with TestClient(app, raise_server_exceptions=False) as http:
        yield http


def sign_up(anon, name):
    """Register a customer and sign in, returning (customer_id, auth headers)."""
    email = f"{name}@example.com"
    registered = anon.post("/customers", json={
        "name": name.title(), "email": email, "password": PASSWORD,
        "phone": "250-555-0100", "delivery_address": ADDRESS,
    })
    assert registered.status_code == 201
    login = anon.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return login.json()["customer"]["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


def add_menu_item(manager, name, price, restaurant_id=101):
    response = manager.post(f"/restaurants/{restaurant_id}/menu",
                            json={"name": name, "category": "Main", "price": price})
    assert response.status_code == 201
    return response.json()["product_id"]


def storage(data_dir):
    return [(data_dir / name).read_bytes() for name in ("carts.json", "orders.json")]


def test_customer_to_order_workflow(anon, manager, store):
    taco = add_menu_item(manager, "Taco", 4.5)
    churro = add_menu_item(manager, "Churro", 2.0)
    ada, headers = sign_up(anon, "ada")

    # browse: find the restaurant, then its menu
    found = anon.get("/restaurants", params={"cuisine": "mexican"}).json()
    assert [r["id"] for r in found] == [101]
    menu = anon.get("/restaurants/101/menu").json()
    assert [item["name"] for item in menu] == ["Taco", "Churro"]

    # build the cart
    cart_path = f"/customers/{ada}/cart"
    assert anon.post(cart_path, headers=headers).status_code == 201
    assert anon.post(f"{cart_path}/items", headers=headers,
                     json={"product_id": taco, "quantity": 2}).status_code == 200
    assert anon.post(f"{cart_path}/items", headers=headers,
                     json={"product_id": churro, "quantity": 1}).status_code == 200
    cart = anon.patch(f"{cart_path}/items/{taco}", headers=headers, json={"quantity": 3}).json()
    assert cart["total"] == 15.5  # 3 * 4.5 + 2.0, worked out by the backend

    # the owner raises the price before checkout, so checkout has to use the new one
    assert manager.patch(f"/restaurants/101/menu/{taco}", json={"price": 5.0}).status_code == 200

    response = anon.post(f"/customers/{ada}/checkout", headers=headers)
    assert response.status_code == 201
    order = response.json()
    assert order["customer_id"] == ada and order["restaurant_id"] == 101
    assert order["delivery_address"] == ADDRESS
    assert [(i["product_id"], i["unit_price"], i["quantity"]) for i in order["items"]] == [
        (taco, 5.0, 3), (churro, 2.0, 1)]
    assert order["subtotal"] == order["total"] == 17.0

    # cart is empty after the order saved, and the order can be read back
    cart = anon.get(cart_path, headers=headers).json()
    assert cart["items"] == [] and cart["total"] == 0
    assert anon.get(f"/customers/{ada}/orders", headers=headers).json() == [order]
    assert anon.get(f"/customers/{ada}/orders/{order['order_id']}", headers=headers).json() == order

    # restart: a fresh process signs in again and sees the same order and empty cart
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': sys.argv[1], 'password': sys.argv[2]}).json()
    headers = {'Authorization': f"Bearer {login['access_token']}"}
    customer_id = login['customer']['id']
    orders = client.get(f'/customers/{customer_id}/orders', headers=headers).json()
    cart = client.get(f'/customers/{customer_id}/cart', headers=headers).json()
    print(json.dumps([customer_id, orders, cart]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, "ada@example.com", PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(store)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    customer_id, orders, cart = json.loads(result.stdout)
    assert customer_id == ada
    assert orders == [order]
    assert cart["items"] == [] and cart["total"] == 0

