"""Restaurant and menu writes require restaurant-owner or admin credentials (#78)."""
import json

import pytest

from app.core import customer_auth
from app.repositories import customer_repo
from tests.conftest import MANAGER


ITEM = {
    "product_id": 1, "restaurant_id": 101, "name": "Taco", "description": "Bean taco",
    "price": 4.5, "category": "Main", "image": "", "is_available": True,
}
NEW_RESTAURANT = {
    "name": "Guarded Café", "cuisine": "Fusion",
    "location": {"address": "3 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V3"},
}
WRITES = [
    ("post", "/restaurants", NEW_RESTAURANT, 201),
    ("patch", "/restaurants/101", {"cuisine": "Thai"}, 200),
    ("post", "/restaurants/101/menu", {"name": "Soup", "category": "Main", "price": 5}, 201),
    ("patch", "/restaurants/101/menu/1", {"price": 6}, 200),
    ("delete", "/restaurants/101/menu/1", None, 204),
]
READS = ["/restaurants", "/restaurants/101", "/restaurants/101/menu", "/restaurants/101/menu/1"]
WRITE_OPERATIONS = [
    ("post", "/restaurants"), ("patch", "/restaurants/{restaurant_id}"),
    ("post", "/restaurants/{restaurant_id}/menu"),
    ("patch", "/restaurants/{restaurant_id}/menu/{product_id}"),
    ("delete", "/restaurants/{restaurant_id}/menu/{product_id}"),
]
READ_OPERATIONS = [
    ("get", "/restaurants"), ("get", "/restaurants/{restaurant_id}"),
    ("get", "/restaurants/{restaurant_id}/menu"),
    ("get", "/restaurants/{restaurant_id}/menu/{product_id}"),
]


@pytest.fixture
def accounts(data_dir):
    (data_dir / "products.json").write_text(json.dumps([ITEM]), encoding="utf-8")
    created = {
        name: customer_repo.create({
            **{key: value for key, value in MANAGER.items() if key != "id"},
            "email": f"{name}@example.com", "role": role, "is_active": active,
        })
        for name, role, active in [
            ("customer", "customer", True), ("admin", "admin", True),
            ("inactive_owner", "restaurant_owner", False),
        ]
    }
    return {"restaurant_owner": MANAGER, **created}


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def storage(data_dir):
    return [(data_dir / name).read_bytes() for name in ("restaurants.json", "products.json", "customers.json")]


@pytest.mark.parametrize("method,path,body,status", WRITES)
@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_writes_without_valid_credentials_are_401(
    anonymous_client, accounts, data_dir, method, path, body, status, authorization,
):
    before = storage(data_dir)
    headers = {} if authorization is None else {"Authorization": authorization}
    response = anonymous_client.request(method, path, json=body, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path,body,status", WRITES)
@pytest.mark.parametrize("account", ["customer", "inactive_owner"])
def test_writes_by_customers_or_inactive_accounts_are_403(
    anonymous_client, accounts, data_dir, method, path, body, status, account,
):
    before = storage(data_dir)
    response = anonymous_client.request(method, path, json=body, headers=bearer(accounts[account]))
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path,body,status", WRITES)
@pytest.mark.parametrize("account", ["restaurant_owner", "admin"])
def test_owners_and_admins_can_write(anonymous_client, accounts, method, path, body, status, account):
    response = anonymous_client.request(method, path, json=body, headers=bearer(accounts[account]))
    assert response.status_code == status


@pytest.mark.parametrize("method,path,body,status", WRITES[:4])
def test_authentication_is_checked_before_body_validation(anonymous_client, accounts, method, path, body, status):
    assert anonymous_client.request(method, path, json={"unknown": True}).status_code == 401


@pytest.mark.parametrize("path", READS)
def test_browsing_stays_public(anonymous_client, accounts, path):
    assert anonymous_client.get(path).status_code == 200


def test_openapi_declares_security_only_on_writes(anonymous_client):
    paths = anonymous_client.get("/openapi.json").json()["paths"]
    for method, path in WRITE_OPERATIONS:
        operation = paths[path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert operation["responses"]["401"]["content"]["application/json"]["example"] == {
            "detail": "Invalid credentials"}
        assert operation["responses"]["403"]["content"]["application/json"]["example"] == {
            "detail": "Forbidden"}
    for method, path in READ_OPERATIONS:
        assert "security" not in paths[path][method]
        assert "401" not in paths[path][method]["responses"]
