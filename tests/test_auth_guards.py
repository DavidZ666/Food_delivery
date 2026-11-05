import json
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.core import auth, customer_auth
from app.repositories import customer_repo
from app.routes import auth as auth_routes
from app.schemas.customer import CustomerRead


PASSWORD = "guard-test-password"
PASSWORD_HASH = customer_auth.hash_password(PASSWORD)
ROLES = ("customer", "restaurant_owner", "admin")
PROTECTED_PATHS = (
    "/current", "/customer", "/restaurant-owner", "/admin", "/management",
    "/customers/1/profile",
)


@pytest.fixture
def accounts(data_dir, monkeypatch):
    (data_dir / "customers.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    return {
        role: customer_repo.create({
            "name": role, "email": f"{role}@example.com", "phone": "250-555-0100",
            "delivery_address": {
                "address": "1 Main St", "city": "Kelowna", "province": "BC",
                "postal_code": "V1V 1V1",
            },
            "password_hash": PASSWORD_HASH, "role": role, "is_active": True,
        })
        for role in ROLES
    }


@pytest.fixture
def guarded_client(accounts):
    # Exercise real dependency injection without protecting production routes (#78).
    app = FastAPI()
    app.include_router(auth_routes.router)

    @app.get("/current")
    def current(customer: Annotated[CustomerRead, Depends(auth.get_current_customer)]):
        return customer

    for path, roles in (
        ("/customer", ("customer",)),
        ("/restaurant-owner", ("restaurant_owner",)),
        ("/admin", ("admin",)),
        ("/management", ("restaurant_owner", "admin")),
    ):
        app.add_api_route(path, auth.require_roles(*roles), methods=["GET"])

    @app.get("/customers/{customer_id}/profile")
    def owned(customer: Annotated[CustomerRead, Depends(auth.require_customer_owner)]):
        return customer

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def bearer(account):
    return {"Authorization": f"Bearer {customer_auth.issue_token(account['id'])}"}


def assert_unauthorized(response):
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def assert_forbidden(response):
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    assert "WWW-Authenticate" not in response.headers


@pytest.mark.parametrize("role", ROLES)
def test_resolves_current_account_without_password_hash(accounts, role):
    account = accounts[role]
    token = customer_auth.issue_token(account["id"])
    current = auth.get_current_customer(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
    )
    assert type(current) is CustomerRead
    assert current.model_dump() == {key: value for key, value in account.items() if key != "password_hash"}


def test_login_token_works_with_case_insensitive_bearer_scheme(guarded_client, accounts, data_dir):
    before = (data_dir / "customers.json").read_bytes()
    login = guarded_client.post("/auth/login", json={
        "email": accounts["customer"]["email"], "password": PASSWORD,
    })
    assert login.status_code == 200
    response = guarded_client.get("/current", headers={
        "Authorization": f"bEaReR {login.json()['access_token']}",
    })
    assert response.status_code == 200
    assert response.json() == login.json()["customer"]
    assert "password" not in response.text
    assert (data_dir / "customers.json").read_bytes() == before


@pytest.mark.parametrize("authorization", [
    None, "", "Basic abc", "Bearer", "Bearer ", "Bearer unknown", "Bearer a b",
])
def test_missing_or_invalid_credentials_reject_every_guard(guarded_client, data_dir, authorization):
    before = (data_dir / "customers.json").read_bytes()
    headers = {} if authorization is None else {"Authorization": authorization}
    for path in PROTECTED_PATHS:
        assert_unauthorized(guarded_client.get(path, headers=headers))
    assert (data_dir / "customers.json").read_bytes() == before


def test_query_and_cookie_tokens_do_not_authenticate(guarded_client, accounts):
    token = customer_auth.issue_token(accounts["customer"]["id"])
    assert_unauthorized(guarded_client.get(
        "/current", params={"access_token": token},
        headers={"Cookie": f"access_token={token}"},
    ))


@pytest.mark.parametrize("scheme", ["Basic", "Digest", "Token"])
def test_valid_token_with_wrong_scheme_is_rejected(guarded_client, accounts, scheme):
    token = customer_auth.issue_token(accounts["customer"]["id"])
    assert_unauthorized(guarded_client.get("/current", headers={
        "Authorization": f"{scheme} {token}",
    }))


def test_expired_and_tampered_tokens_are_rejected(guarded_client, accounts, monkeypatch):
    monkeypatch.setattr(customer_auth, "monotonic", lambda: 100)
    headers = bearer(accounts["customer"])
    assert guarded_client.get("/current", headers=headers).status_code == 200
    assert_unauthorized(guarded_client.get("/current", headers={
        "Authorization": headers["Authorization"] + "x",
    }))
    monkeypatch.setattr(customer_auth, "monotonic", lambda: 100 + customer_auth.SESSION_TTL_SECONDS)
    assert_unauthorized(guarded_client.get("/current", headers=headers))


@pytest.mark.parametrize("role", ROLES)
def test_deactivation_rejects_existing_token_on_every_guard(guarded_client, accounts, role):
    account = accounts[role]
    headers = bearer(account)
    assert guarded_client.get("/current", headers=headers).status_code == 200
    customer_repo.update_by_id(account["id"], {"is_active": False})
    for path in PROTECTED_PATHS:
        assert_forbidden(guarded_client.get(path, headers=headers))


def test_deleted_account_invalidates_existing_token(guarded_client, accounts, data_dir):
    headers = bearer(accounts["customer"])
    assert guarded_client.get("/current", headers=headers).status_code == 200
    (data_dir / "customers.json").write_text("[]", encoding="utf-8")
    assert_unauthorized(guarded_client.get("/current", headers=headers))


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("path,allowed", [
    ("/customer", {"customer"}),
    ("/restaurant-owner", {"restaurant_owner"}),
    ("/admin", {"admin"}),
    ("/management", {"restaurant_owner", "admin"}),
])
def test_role_matrix(guarded_client, accounts, data_dir, role, path, allowed):
    before = (data_dir / "customers.json").read_bytes()
    response = guarded_client.get(path, headers=bearer(accounts[role]))
    if role in allowed:
        assert response.status_code == 200
        assert response.json() == CustomerRead.model_validate(accounts[role]).model_dump()
    else:
        assert_forbidden(response)
    assert (data_dir / "customers.json").read_bytes() == before


def test_role_change_applies_to_existing_token(guarded_client, accounts, data_dir):
    headers = bearer(accounts["admin"])
    assert guarded_client.get("/admin", headers=headers).status_code == 200
    path = data_dir / "customers.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    records[-1]["role"] = "customer"
    path.write_text(json.dumps(records), encoding="utf-8")
    assert_forbidden(guarded_client.get("/admin", headers=headers))
    response = guarded_client.get("/customer", headers=headers)
    assert response.status_code == 200 and response.json()["role"] == "customer"


def test_customer_ownership(guarded_client, accounts, data_dir):
    account = accounts["customer"]
    headers = bearer(account)
    before = (data_dir / "customers.json").read_bytes()
    response = guarded_client.get(f"/customers/{account['id']}/profile", headers=headers)
    assert response.status_code == 200
    assert response.json() == CustomerRead.model_validate(account).model_dump()
    for customer_id in (accounts["admin"]["id"], 999):
        assert_forbidden(guarded_client.get(f"/customers/{customer_id}/profile", headers=headers))
    assert (data_dir / "customers.json").read_bytes() == before


@pytest.mark.parametrize("role", ["restaurant_owner", "admin"])
def test_non_customer_cannot_pass_ownership_even_with_matching_id(guarded_client, accounts, role):
    account = accounts[role]
    assert_forbidden(guarded_client.get(
        f"/customers/{account['id']}/profile", headers=bearer(account),
    ))


@pytest.mark.parametrize("content", ["{bad", "{}", '[{"id": 1}]'])
def test_malformed_storage_is_server_error(guarded_client, accounts, data_dir, content):
    headers = bearer(accounts["customer"])
    path = data_dir / "customers.json"
    path.write_text(content, encoding="utf-8")
    response = guarded_client.get("/current", headers=headers)
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert path.read_text(encoding="utf-8") == content
    assert_unauthorized(guarded_client.get("/current"))


def test_storage_read_failure_is_not_an_authentication_error(guarded_client, accounts, monkeypatch):
    headers = bearer(accounts["customer"])

    def fail(customer_id):
        raise OSError("simulated read failure")

    monkeypatch.setattr(customer_repo, "get_by_id", fail)
    response = guarded_client.get("/current", headers=headers)
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_no_allowed_roles_denies_access(accounts):
    current = CustomerRead.model_validate(accounts["admin"])
    with pytest.raises(HTTPException) as error:
        auth.require_roles()(current)
    assert error.value.status_code == 403


@pytest.mark.parametrize("roles", [("owner",), ("customer", "restaurant-owner"), ("Admin",)])
def test_unknown_roles_are_rejected_when_guard_is_defined(roles):
    with pytest.raises(ValueError, match="Unknown role"):
        auth.require_roles(*roles)


def test_openapi_declares_bearer_security_for_composed_guards(guarded_client):
    spec = guarded_client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["type"] == "http"
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    for path in (*PROTECTED_PATHS[:-1], "/customers/{customer_id}/profile"):
        assert spec["paths"][path]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in spec["paths"]["/auth/login"]["post"]
