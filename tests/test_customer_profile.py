"""Customer profile, delivery-address updates and deactivation (#75)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.core import customer_auth
from app.main import app
from app.repositories import customer_repo
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services import customer_service


PASSWORD = "profile-test-password"
PASSWORD_HASH = customer_auth.hash_password(PASSWORD)
ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
NAMES = ("ada", "bob", "admin", "owner")
ROLES = {"ada": "customer", "bob": "customer", "admin": "admin", "owner": "restaurant_owner"}
ROUTES = [
    ("get", "/customers/{id}", None),
    ("patch", "/customers/{id}", {"phone": "250-555-0199"}),
    ("post", "/customers/{id}/deactivate", None),
]


@pytest.fixture
def accounts(data_dir, monkeypatch):
    (data_dir / "customers.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    return {
        name: customer_repo.create({
            "name": name.title(), "email": f"{name}@example.com", "phone": "250-555-0100",
            "delivery_address": ADDRESS, "password_hash": PASSWORD_HASH,
            "role": ROLES[name], "is_active": True,
        })
        for name in NAMES
    }


@pytest.fixture
def http(accounts):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def storage(data_dir):
    return (data_dir / "customers.json").read_bytes()


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def public(account):
    return CustomerRead.model_validate(account).model_dump()


def call(http, method, path, account_id, body=None, headers=None):
    return http.request(method, path.format(id=account_id), json=body, headers=headers or {})


# Service

def test_get_customer_returns_public_fields(accounts):
    assert customer_service.get_customer(accounts["ada"]["id"]) == CustomerRead.model_validate(accounts["ada"])
    with pytest.raises(customer_service.CustomerNotFoundError):
        customer_service.get_customer(999)


def test_update_customer_merges_address_and_preserves_other_data(accounts, data_dir):
    ada, others = accounts["ada"], [accounts[name] for name in NAMES[1:]]
    updated = customer_service.update_customer(ada["id"], CustomerUpdate.model_validate(
        {"name": "  Ada L  ", "delivery_address": {"city": " Vancouver "}},
    ))
    assert updated.name == "Ada L"
    assert updated.delivery_address.model_dump() == {**ADDRESS, "city": "Vancouver"}
    assert updated.phone == ada["phone"] and updated.email == ada["email"]
    records = json.loads(storage(data_dir))
    assert records[0]["password_hash"] == PASSWORD_HASH
    assert records[1:] == others
    with pytest.raises(customer_service.CustomerNotFoundError):
        customer_service.update_customer(999, CustomerUpdate.model_validate({"name": "X"}))
    assert json.loads(storage(data_dir)) == records


def test_deactivation_keeps_record_and_id(accounts, data_dir):
    ada = accounts["ada"]
    deactivated = customer_service.deactivate_customer(ada["id"])
    assert deactivated == CustomerRead.model_validate({**ada, "is_active": False})
    assert customer_repo.get_by_id(ada["id"]) == {**ada, "is_active": False}
    created = customer_service.register_customer(CustomerCreate.model_validate({
        "name": "New", "email": "new@example.com", "password": PASSWORD,
        "phone": "250-555-0100", "delivery_address": ADDRESS,
    }))
    assert created.id == max(account["id"] for account in accounts.values()) + 1
    with pytest.raises(customer_service.CustomerNotFoundError):
        customer_service.deactivate_customer(999)


def test_require_active_customer(accounts):
    ada = accounts["ada"]
    assert customer_service.require_active_customer(ada["id"]) == CustomerRead.model_validate(ada)
    customer_service.deactivate_customer(ada["id"])
    with pytest.raises(customer_service.InactiveCustomerError):
        customer_service.require_active_customer(ada["id"])
    with pytest.raises(customer_service.CustomerNotFoundError):
        customer_service.require_active_customer(999)


# API

def test_customer_reads_and_updates_own_profile(http, accounts, data_dir):
    ada = accounts["ada"]
    headers = bearer(ada)
    response = http.get(f"/customers/{ada['id']}", headers=headers)
    assert response.status_code == 200 and response.json() == public(ada)
    assert "password" not in response.text
    response = http.patch(f"/customers/{ada['id']}", headers=headers, json={
        "phone": " 250-555-0199 ", "delivery_address": {"postal_code": "V1V 9Z9"},
    })
    expected = {**public(ada), "phone": "250-555-0199",
                "delivery_address": {**ADDRESS, "postal_code": "V1V 9Z9"}}
    assert response.status_code == 200 and response.json() == expected
    assert http.get(f"/customers/{ada['id']}", headers=headers).json() == expected


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("actor,target", [("ada", "bob"), ("owner", "ada"), ("ada", 999)])
def test_other_accounts_are_forbidden(http, accounts, data_dir, method, path, body, actor, target):
    before = storage(data_dir)
    target_id = target if isinstance(target, int) else accounts[target]["id"]
    response = call(http, method, path, target_id, body, bearer(accounts[actor]))
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_admin_can_manage_any_customer_and_unknown_is_404(http, accounts, data_dir, method, path, body):
    headers = bearer(accounts["admin"])
    before = storage(data_dir)
    response = call(http, method, path, 999, body, headers)
    assert response.status_code == 404 and response.json() == {"detail": "Customer not found"}
    assert storage(data_dir) == before
    assert call(http, method, path, accounts["ada"]["id"], body, headers).status_code == 200


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc"])
def test_missing_or_invalid_credentials_are_401(http, accounts, data_dir, method, path, body, authorization):
    before = storage(data_dir)
    headers = {} if authorization is None else {"Authorization": authorization}
    response = call(http, method, path, accounts["ada"]["id"], body, headers)
    assert response.status_code == 401 and response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert storage(data_dir) == before


@pytest.mark.parametrize("body", [
    {}, {"name": None}, {"name": "  "}, {"phone": ""}, {"delivery_address": {}},
    {"delivery_address": None}, {"delivery_address": {"city": None}},
    {"delivery_address": {"country": "CA"}}, {"email": "x@example.com"},
    {"password": "new-password"}, {"role": "admin"}, {"is_active": False}, {"id": 5},
])
def test_invalid_updates_are_422_without_changes(http, accounts, data_dir, body):
    before = storage(data_dir)
    response = http.patch(f"/customers/{accounts['ada']['id']}", headers=bearer(accounts["ada"]), json=body)
    assert response.status_code == 422
    assert storage(data_dir) == before


def test_deactivation_blocks_sign_in_and_profile_access(http, accounts, data_dir):
    ada = accounts["ada"]
    headers = bearer(ada)
    response = http.post(f"/customers/{ada['id']}/deactivate", headers=headers)
    assert response.status_code == 200 and response.json() == {**public(ada), "is_active": False}
    for method, path, body in ROUTES:
        response = call(http, method, path, ada["id"], body, headers)
        assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    login = http.post("/auth/login", json={"email": ada["email"], "password": PASSWORD})
    assert login.status_code == 403 and login.json() == {"detail": "Forbidden"}
    assert customer_repo.get_by_id(ada["id"]) == {**ada, "is_active": False}


def test_updates_and_deactivation_survive_restart(http, accounts, data_dir):
    ada = accounts["ada"]
    headers = bearer(ada)
    updated = http.patch(f"/customers/{ada['id']}", headers=headers,
                         json={"delivery_address": {"city": "Vancouver"}}).json()
    script = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
email, password = sys.argv[1:3]
with TestClient(app) as client:
    login = client.post('/auth/login', json={'email': email, 'password': password})
    if login.status_code != 200:
        print(json.dumps([login.status_code, login.json()]))
    else:
        token = login.json()['access_token']
        profile = client.get(f"/customers/{login.json()['customer']['id']}",
                             headers={'Authorization': f'Bearer {token}'})
        print(json.dumps([profile.status_code, profile.json()]))
"""

    def fresh_process():
        result = subprocess.run(
            [sys.executable, "-c", script, ada["email"], PASSWORD],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
            capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
        )
        return json.loads(result.stdout)

    assert fresh_process() == [200, updated]
    assert http.post(f"/customers/{ada['id']}/deactivate", headers=headers).status_code == 200
    assert fresh_process() == [403, {"detail": "Forbidden"}]


def test_openapi_documents_protected_profile_routes(http):
    paths = http.get("/openapi.json").json()["paths"]
    for method, path in [("get", "/customers/{customer_id}"), ("patch", "/customers/{customer_id}"),
                         ("post", "/customers/{customer_id}/deactivate")]:
        operation = paths[path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert {"200", "401", "403", "404", "422", "500"} <= set(operation["responses"])
        assert operation["summary"] and operation["description"]
    assert "security" not in paths["/customers"]["post"]


def test_access_is_checked_before_body_validation(http, accounts):
    ada, bob = accounts["ada"], accounts["bob"]
    assert http.patch(f"/customers/{ada['id']}", json={}).status_code == 401
    assert http.patch(f"/customers/{ada['id']}", json={}, headers=bearer(bob)).status_code == 403
    assert http.patch("/customers/999", json={}, headers=bearer(accounts["admin"])).status_code == 422
