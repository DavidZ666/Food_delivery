"""Order history and single-order reads return stored snapshots (#92)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.repositories import customer_repo, order_repo, product_repo
from app.services import checkout_service, customer_service, order_service
from tests.test_checkout import (  # noqa: F401 - shared checkout fixtures
    ADDRESS, PASSWORD, PASSWORD_HASH, accounts, add, bearer, http,
)


@pytest.fixture
def people(accounts):
    for name, role in (("admin", "admin"), ("owner", "restaurant_owner")):
        accounts[name] = customer_repo.create({
            "name": name.title(), "email": f"{name}@example.com", "phone": "250-555-0100",
            "delivery_address": ADDRESS, "password_hash": PASSWORD_HASH,
            "role": role, "is_active": True,
        })
    return accounts


@pytest.fixture
def placed(people):
    """Two orders for ada and one for bob, placed through checkout."""
    ada, bob = people["ada"]["id"], people["bob"]["id"]
    first = checkout_service.checkout(ada).model_dump()
    add(ada, 1, 1)
    second = checkout_service.checkout(ada).model_dump()
    other = checkout_service.checkout(bob).model_dump()
    return {"ada": [first, second], "bob": [other]}


def orders_path(account, order_id=None):
    path = f"/customers/{account['id']}/orders"
    return path if order_id is None else f"{path}/{order_id}"


def storage(data_dir):
    return (data_dir / "orders.json").read_bytes()


# Service

def test_service_lists_and_reads_stored_snapshots(placed, people):
    ada = people["ada"]["id"]
    assert [order.model_dump() for order in order_service.list_orders(ada)] == placed["ada"]
    assert order_service.get_order(ada, placed["ada"][1]["order_id"]).model_dump() == placed["ada"][1]
    assert order_service.list_orders(people["cartless"]["id"]) == []


def test_service_hides_other_customers_orders_and_unknown_ids(placed, people):
    with pytest.raises(order_service.OrderNotFoundError):
        order_service.get_order(people["ada"]["id"], placed["bob"][0]["order_id"])
    with pytest.raises(order_service.OrderNotFoundError):
        order_service.get_order(people["ada"]["id"], 999)
    with pytest.raises(customer_service.CustomerNotFoundError):
        order_service.list_orders(999)


# API: own orders

def test_customer_lists_orders_in_creation_order(http, people):
    ada = people["ada"]
    response = http.get(orders_path(ada), headers=bearer(ada))
    assert response.status_code == 200 and response.json() == []
    first = http.post(f"/customers/{ada['id']}/checkout", headers=bearer(ada)).json()
    add(ada["id"], 2, 1)
    second = http.post(f"/customers/{ada['id']}/checkout", headers=bearer(ada)).json()
    response = http.get(orders_path(ada), headers=bearer(ada))
    assert response.status_code == 200 and response.json() == [first, second]
    assert [order["order_id"] for order in response.json()] == sorted(
        order["order_id"] for order in response.json())


def test_customer_reads_one_order(http, placed, people):
    ada, order = people["ada"], placed["ada"][0]
    response = http.get(orders_path(ada, order["order_id"]), headers=bearer(ada))
    assert response.status_code == 200 and response.json() == order
    assert response.json() == order_repo.get_by_id(order["order_id"])


@pytest.mark.parametrize("order_id", ["other", 999])
def test_other_or_unknown_order_is_404_without_changes(http, placed, people, data_dir, order_id):
    ada = people["ada"]
    target = placed["bob"][0]["order_id"] if order_id == "other" else order_id
    before = storage(data_dir)
    response = http.get(orders_path(ada, target), headers=bearer(ada))
    assert response.status_code == 404 and response.json() == {"detail": "Order not found"}
    assert storage(data_dir) == before


# API: access

@pytest.mark.parametrize("actor", ["bob", "owner"])
@pytest.mark.parametrize("single", [False, True])
def test_other_accounts_are_forbidden(http, placed, people, data_dir, actor, single):
    ada = people["ada"]
    path = orders_path(ada, placed["ada"][0]["order_id"] if single else None)
    before = storage(data_dir)
    response = http.get(path, headers=bearer(people[actor]))
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("single", [False, True])
@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_missing_or_invalid_credentials_are_401(http, placed, people, single, authorization):
    ada = people["ada"]
    path = orders_path(ada, placed["ada"][0]["order_id"] if single else None)
    response = http.get(path, headers={} if authorization is None else {"Authorization": authorization})
    assert response.status_code == 401 and response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("single", [False, True])
def test_deactivated_caller_is_forbidden(http, placed, people, single):
    ada = people["ada"]
    headers = bearer(ada)
    customer_service.deactivate_customer(ada["id"])
    path = orders_path(ada, placed["ada"][0]["order_id"] if single else None)
    response = http.get(path, headers=headers)
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}


def test_admin_reads_any_customer_including_deactivated(http, placed, people):
    ada, admin = people["ada"], bearer(people["admin"])
    customer_service.deactivate_customer(ada["id"])
    assert http.get(orders_path(ada), headers=admin).json() == placed["ada"]
    order = placed["ada"][1]
    response = http.get(orders_path(ada, order["order_id"]), headers=admin)
    assert response.status_code == 200 and response.json() == order
    response = http.get(orders_path(ada, placed["bob"][0]["order_id"]), headers=admin)
    assert response.status_code == 404 and response.json() == {"detail": "Order not found"}


@pytest.mark.parametrize("path", ["/customers/999/orders", "/customers/999/orders/1"])
def test_admin_unknown_customer_is_404(http, placed, people, path):
    response = http.get(path, headers=bearer(people["admin"]))
    assert response.status_code == 404 and response.json() == {"detail": "Customer not found"}


@pytest.mark.parametrize("path", ["/customers/0/orders", "/customers/abc/orders",
                                  "/customers/{id}/orders/0", "/customers/{id}/orders/abc"])
def test_invalid_ids_are_422(http, people, path):
    admin = people["admin"]
    response = http.get(path.format(id=admin["id"]), headers=bearer(admin))
    assert response.status_code == 422


# Snapshot integrity

def test_menu_changes_and_deletion_leave_orders_unchanged(http, placed, people, data_dir):
    ada = people["ada"]
    stored = order_repo.list_by_customer(ada["id"])
    product_repo.update_by_id(101, 1, {"price": 99.99, "name": "Renamed taco", "is_available": False})
    product_repo.delete_by_id(101, 2)
    response = http.get(orders_path(ada), headers=bearer(ada))
    assert response.status_code == 200 and response.json() == placed["ada"] == stored
    for order in placed["ada"]:
        assert http.get(orders_path(ada, order["order_id"]), headers=bearer(ada)).json() == order


# Persistence and storage

def test_orders_survive_restart(http, placed, people, data_dir):
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
email, password = sys.argv[1:3]
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': email, 'password': password}).json()
    headers = {'Authorization': f"Bearer {login['access_token']}"}
    path = f"/customers/{login['customer']['id']}/orders"
    orders = client.get(path, headers=headers).json()
    one = client.get(f"{path}/{orders[-1]['order_id']}", headers=headers).json()
    print(json.dumps([orders, one]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, people["ada"]["email"], PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    assert json.loads(result.stdout) == [placed["ada"], placed["ada"][-1]]


@pytest.mark.parametrize("content", ["{bad", "{}", '[{"order_id": 1}]'])
def test_malformed_order_storage_is_500_unchanged(http, people, data_dir, content):
    path = data_dir / "orders.json"
    path.write_text(content, encoding="utf-8")
    for url in (orders_path(people["ada"]), orders_path(people["ada"], 1)):
        response = http.get(url, headers=bearer(people["ada"]))
        assert response.status_code == 500 and response.text == "Internal Server Error"
    assert path.read_text(encoding="utf-8") == content


def test_openapi_documents_order_reads(http):
    paths = http.get("/openapi.json").json()["paths"]
    for path in ("/customers/{customer_id}/orders", "/customers/{customer_id}/orders/{order_id}"):
        operation = paths[path]["get"]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert {"200", "401", "403", "404", "422", "500"} <= set(operation["responses"])
        assert operation["summary"] and operation["description"]
    assert paths["/customers/{customer_id}/orders"]["get"]["responses"]["200"][
        "content"]["application/json"]["schema"]["type"] == "array"
