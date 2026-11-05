"""Active cart creation and retrieval endpoints (#82)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.core import customer_auth
from app.main import app
from app.repositories import cart_repo, customer_repo
from app.schemas.cart import CartRead
from app.services import cart_service, customer_service


PASSWORD = "cart-test-password"
PASSWORD_HASH = customer_auth.hash_password(PASSWORD)
ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
ROLES = {"ada": "customer", "bob": "customer", "admin": "admin", "owner": "restaurant_owner"}
ITEM = {"product_id": 1, "name": "Big Mac", "unit_price": 6.99, "quantity": 3}
FRIES = {"product_id": 2, "name": "Fries", "unit_price": 3.49, "quantity": 1}
ROUTES = [("get", "/customers/{id}/cart"), ("post", "/customers/{id}/cart")]


@pytest.fixture
def accounts(data_dir, monkeypatch):
    (data_dir / "customers.json").write_text("[]", encoding="utf-8")
    (data_dir / "carts.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    return {
        name: customer_repo.create({
            "name": name.title(), "email": f"{name}@example.com", "phone": "250-555-0100",
            "delivery_address": ADDRESS, "password_hash": PASSWORD_HASH,
            "role": role, "is_active": True,
        })
        for name, role in ROLES.items()
    }


@pytest.fixture
def http(accounts):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def storage(data_dir):
    return [(data_dir / name).read_bytes() for name in ("carts.json", "customers.json")]


def empty_cart(cart_id, customer_id):
    return {"cart_id": cart_id, "customer_id": customer_id, "restaurant_id": None,
            "items": [], "subtotal": 0.0, "total": 0.0}


def seed_cart(data_dir, customer_id):
    record = {"cart_id": 7, "customer_id": customer_id, "restaurant_id": 1, "items": [ITEM, FRIES]}
    (data_dir / "carts.json").write_text(json.dumps([record]), encoding="utf-8")
    return CartRead.model_validate(record).model_dump()


# Service

def test_service_creates_once_then_returns_existing(accounts, data_dir):
    ada = accounts["ada"]["id"]
    with pytest.raises(cart_service.CartNotFoundError):
        cart_service.get_cart(ada)
    cart, created = cart_service.get_or_create_cart(ada)
    assert created and cart.model_dump() == empty_cart(1, ada)
    again, created = cart_service.get_or_create_cart(ada)
    assert not created and again == cart
    assert cart_service.get_cart(ada) == cart
    assert len(cart_repo.list_all()) == 1


def test_service_returns_backend_totals_for_existing_cart(accounts, data_dir):
    expected = seed_cart(data_dir, accounts["ada"]["id"])
    assert expected["subtotal"] == expected["total"] == 24.46
    assert cart_service.get_cart(accounts["ada"]["id"]).model_dump() == expected
    cart, created = cart_service.get_or_create_cart(accounts["ada"]["id"])
    assert not created and cart.model_dump() == expected


def test_service_rejects_inactive_and_unknown_customers(accounts, data_dir):
    ada = accounts["ada"]["id"]
    customer_service.deactivate_customer(ada)
    before = storage(data_dir)
    for call in (cart_service.get_cart, cart_service.get_or_create_cart):
        with pytest.raises(customer_service.InactiveCustomerError):
            call(ada)
        with pytest.raises(customer_service.CustomerNotFoundError):
            call(999)
    assert storage(data_dir) == before


def test_service_concurrent_create_returns_existing_cart(accounts, data_dir, monkeypatch):
    ada = accounts["ada"]["id"]
    real_create = cart_repo.create

    def create_after_race(customer_id):
        real_create(customer_id)  # another request wins the race
        return real_create(customer_id)

    monkeypatch.setattr(cart_repo, "create", create_after_race)
    cart, created = cart_service.get_or_create_cart(ada)
    assert not created and cart.model_dump() == empty_cart(1, ada)
    assert len(cart_repo.list_all()) == 1


# API

def test_customer_initializes_then_retrieves_cart(http, accounts, data_dir):
    ada = accounts["ada"]
    headers = bearer(ada)
    missing = http.get(f"/customers/{ada['id']}/cart", headers=headers)
    assert missing.status_code == 404 and missing.json() == {"detail": "Cart not found"}
    created = http.post(f"/customers/{ada['id']}/cart", headers=headers)
    assert created.status_code == 201 and created.json() == empty_cart(1, ada["id"])
    existing = http.post(f"/customers/{ada['id']}/cart", headers=headers)
    assert existing.status_code == 200 and existing.json() == created.json()
    read = http.get(f"/customers/{ada['id']}/cart", headers=headers)
    assert read.status_code == 200 and read.json() == created.json()
    assert len(json.loads((data_dir / "carts.json").read_text(encoding="utf-8"))) == 1


def test_existing_cart_returns_items_and_totals(http, accounts, data_dir):
    ada = accounts["ada"]
    expected = seed_cart(data_dir, ada["id"])
    for method, path in ROUTES:
        response = http.request(method, path.format(id=ada["id"]), headers=bearer(ada))
        assert response.status_code == 200 and response.json() == expected


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_missing_or_invalid_credentials_are_401(http, accounts, data_dir, method, path, authorization):
    before = storage(data_dir)
    headers = {} if authorization is None else {"Authorization": authorization}
    response = http.request(method, path.format(id=accounts["ada"]["id"]), headers=headers)
    assert response.status_code == 401 and response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("actor,target", [
    ("ada", "bob"), ("ada", 999), ("admin", "ada"), ("owner", "ada"), ("admin", "admin"), ("owner", "owner"),
])
def test_only_the_owning_customer_may_use_the_cart(http, accounts, data_dir, method, path, actor, target):
    seed_cart(data_dir, accounts["ada"]["id"])
    before = storage(data_dir)
    target_id = target if isinstance(target, int) else accounts[target]["id"]
    response = http.request(method, path.format(id=target_id), headers=bearer(accounts[actor]))
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path", ROUTES)
def test_deactivated_customer_is_403_without_changes(http, accounts, data_dir, method, path):
    ada = accounts["ada"]
    headers = bearer(ada)
    customer_service.deactivate_customer(ada["id"])
    before = storage(data_dir)
    response = http.request(method, path.format(id=ada["id"]), headers=headers)
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path", ROUTES)
def test_invalid_customer_id_is_422(http, accounts, method, path):
    assert http.request(method, path.format(id="abc"), headers=bearer(accounts["ada"])).status_code == 422


@pytest.mark.parametrize("content", ["{bad", "{}", '[{"cart_id": 1}]'])
@pytest.mark.parametrize("method,path", ROUTES)
def test_malformed_cart_storage_is_500_without_rewrite(http, accounts, data_dir, method, path, content):
    (data_dir / "carts.json").write_text(content, encoding="utf-8")
    response = http.request(method, path.format(id=accounts["ada"]["id"]), headers=bearer(accounts["ada"]))
    assert response.status_code == 500
    assert (data_dir / "carts.json").read_text(encoding="utf-8") == content


def test_cart_survives_restart(http, accounts, data_dir):
    ada = accounts["ada"]
    created = http.post(f"/customers/{ada['id']}/cart", headers=bearer(ada)).json()
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': sys.argv[1], 'password': sys.argv[2]}).json()
    headers = {'Authorization': f"Bearer {login['access_token']}"}
    path = f"/customers/{login['customer']['id']}/cart"
    read, again = client.get(path, headers=headers), client.post(path, headers=headers)
    print(json.dumps([read.status_code, read.json(), again.status_code, again.json()]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, ada["email"], PASSWORD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    assert json.loads(result.stdout) == [200, created, 200, created]
    assert len(json.loads((data_dir / "carts.json").read_text(encoding="utf-8"))) == 1


def test_openapi_documents_cart_routes(http):
    paths = http.get("/openapi.json").json()["paths"]
    for method, statuses in (("get", {"200", "401", "403", "404", "422", "500"}),
                             ("post", {"200", "201", "401", "403", "404", "422", "500"})):
        operation = paths["/customers/{customer_id}/cart"][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert statuses <= set(operation["responses"])
        assert operation["summary"] and operation["description"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/CartRead"}
