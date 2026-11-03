import json
import os
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import customer_auth
from app.main import app
from app.repositories import customer_repo, json_store
from app.schemas.auth import LoginRequest
from app.schemas.customer import CustomerCreate
from app.services import customer_service


REGISTRATION = {
    "name": " Ada 陈 ", "email": " ADA@example.com ", "password": "correct-horse-秘密",
    "phone": "250-555-0100",
    "delivery_address": {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"},
}
LOGIN = {"email": "ada@example.com", "password": REGISTRATION["password"]}


@pytest.fixture
def storage(data_dir, monkeypatch):
    path = data_dir / "customers.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(customer_auth, "_sessions", {})
    return path


def register():
    return customer_service.register_customer(CustomerCreate.model_validate(REGISTRATION))


def test_service_registration_and_login(storage):
    customer = register()
    assert customer.id == 1 and customer.is_active and customer.role == "customer"
    assert customer.name == "Ada 陈" and customer.email == "ada@example.com"
    stored = json.loads(storage.read_text(encoding="utf-8"))[0]
    assert "password" not in stored and stored["password_hash"] != LOGIN["password"]
    assert customer_auth.verify_password(LOGIN["password"], stored["password_hash"])
    result = customer_service.sign_in(LoginRequest(**LOGIN))
    assert result.customer == customer and result.token_type == "bearer"
    assert customer_auth.resolve_token(result.access_token) == customer.id
    assert "password" not in result.model_dump_json()


def test_service_duplicate_preserves_storage(storage):
    register()
    before = storage.read_bytes()
    with pytest.raises(customer_repo.DuplicateEmailError):
        register()
    assert storage.read_bytes() == before


@pytest.mark.parametrize("credentials", [
    {**LOGIN, "password": "wrong"}, {**LOGIN, "email": "unknown@example.com"},
])
def test_service_rejects_credentials(storage, credentials):
    register()
    with pytest.raises(customer_service.InvalidCredentialsError):
        customer_service.sign_in(LoginRequest(**credentials))
    assert not customer_auth._sessions


def test_service_rejects_inactive(storage):
    customer_repo.update_by_id(register().id, {"is_active": False})
    with pytest.raises(customer_service.InactiveCustomerError):
        customer_service.sign_in(LoginRequest(**LOGIN))
    assert not customer_auth._sessions


def test_api_registration_duplicate_and_login(storage, client):
    created = client.post("/customers", json=REGISTRATION)
    assert created.status_code == 201
    assert "password" not in created.text
    before = storage.read_bytes()
    duplicate = client.post("/customers", json={**REGISTRATION, "email": "ada@EXAMPLE.com"})
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Email is already registered"}
    assert storage.read_bytes() == before
    login = client.post("/auth/login", json=LOGIN)
    assert login.status_code == 200
    assert login.json()["customer"] == created.json()
    assert login.json()["token_type"] == "bearer"
    assert customer_auth.resolve_token(login.json()["access_token"]) == created.json()["id"]
    assert "password" not in login.text and storage.read_bytes() == before


@pytest.mark.parametrize("change", [
    {"name": ""}, {"password": "tiny-pw"}, {"password": "a" * 129},
    {"email": "invalid"}, {"role": "admin"}, {"id": 100}, {"is_active": False},
    {"delivery_address": {}},
])
def test_registration_validation(storage, client, change):
    body = {**REGISTRATION, **change}
    response = client.post("/customers", json=body)
    assert response.status_code == 422
    assert storage.read_text() == "[]"
    assert body["password"] not in response.text
    assert all("input" not in error for error in response.json()["detail"])


@pytest.mark.parametrize("body", [{}, {"email": "invalid", "password": "secret"}, {**LOGIN, "role": "admin"}])
def test_login_validation(storage, client, body):
    response = client.post("/auth/login", json=body)
    assert response.status_code == 422
    assert body.get("password", REGISTRATION["password"]) not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert not customer_auth._sessions


def test_prefixed_validation_redacts_passwords(storage):
    mounted = FastAPI()
    mounted.mount("/api", app)
    for target in (TestClient(app, root_path="/api"), TestClient(mounted)):
        with target as prefixed_client:
            for path, body in (
                ("/api/customers", {**REGISTRATION, "password": "tiny-pw"}),
                ("/api/auth/login", {**LOGIN, "role": "admin"}),
            ):
                response = prefixed_client.post(path, json=body)
                assert response.status_code == 422
                assert body["password"] not in response.text
                assert all("input" not in error for error in response.json()["detail"])


def test_api_wrong_credentials_and_deactivation(storage, client):
    register()
    for body in ({**LOGIN, "password": "wrong"}, {**LOGIN, "email": "unknown@example.com"}):
        response = client.post("/auth/login", json=body)
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid credentials"}
        assert response.headers["WWW-Authenticate"] == "Bearer"
    customer_repo.update_by_id(1, {"is_active": False})
    response = client.post("/auth/login", json=LOGIN)
    assert response.status_code == 403 and response.json() == {"detail": "Forbidden"}
    assert client.post("/auth/login", json={**LOGIN, "password": "wrong"}).status_code == 401
    assert not customer_auth._sessions


@pytest.mark.parametrize("content", ["{bad", "{}", '[{"id": 1}]', None])
@pytest.mark.parametrize("path,body", [("/customers", REGISTRATION), ("/auth/login", LOGIN)])
def test_api_storage_errors(storage, content, path, body):
    if content is None:
        storage.unlink()
    else:
        storage.write_text(content, encoding="utf-8")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=body)
    assert response.status_code == 500 and response.text == "Internal Server Error"
    assert not storage.exists() if content is None else storage.read_text() == content
    assert not customer_auth._sessions


def test_failed_registration_write_preserves_existing_account(storage, monkeypatch):
    register()
    before = storage.read_bytes()

    def fail(*args):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(json_store.os, "replace", fail)
    body = {**REGISTRATION, "email": "new@example.com"}
    with pytest.raises(OSError):
        customer_service.register_customer(CustomerCreate.model_validate(body))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/customers", json=body).status_code == 500
    assert storage.read_bytes() == before
    assert not list(storage.parent.glob(".customers.json.*.tmp"))


def test_service_read_failure_propagates(storage, monkeypatch):
    def fail(*args):
        raise OSError("simulated read failure")

    monkeypatch.setattr(customer_repo, "get_by_email", fail)
    with pytest.raises(OSError):
        customer_service.sign_in(LoginRequest(**LOGIN))
    assert not customer_auth._sessions


def test_malformed_password_hash_is_storage_error(storage):
    register()
    records = json.loads(storage.read_text(encoding="utf-8"))
    records[0]["password_hash"] = "scrypt$invalid"
    storage.write_text(json.dumps(records), encoding="utf-8")
    before = storage.read_bytes()
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/auth/login", json=LOGIN).status_code == 500
    assert storage.read_bytes() == before and not customer_auth._sessions


def test_password_salts_and_token_expiry(storage, monkeypatch):
    first = customer_auth.hash_password(LOGIN["password"])
    second = customer_auth.hash_password(LOGIN["password"])
    assert first != second
    assert customer_auth.verify_password(LOGIN["password"], first)
    assert not customer_auth.verify_password("wrong", first)
    monkeypatch.setattr(customer_auth, "monotonic", lambda: 100)
    token = customer_auth.issue_token(1)
    assert customer_auth.issue_token(1) != token
    assert customer_auth.resolve_token(token) == 1
    assert customer_auth.resolve_token(token + "x") is None
    assert customer_auth.resolve_token("") is None
    monkeypatch.setattr(customer_auth, "monotonic", lambda: 100 + customer_auth.SESSION_TTL_SECONDS)
    assert customer_auth.resolve_token(token) is None
    customer_auth.issue_token(2)
    assert len(customer_auth._sessions) == 1


def test_login_after_real_process_restart(storage, client):
    customer = client.post("/customers", json=REGISTRATION).json()
    old_token = client.post("/auth/login", json=LOGIN).json()["access_token"]
    script = '''
import json, sys
from fastapi.testclient import TestClient
from app.main import app
from app.core.customer_auth import resolve_token
credentials, old_token = json.load(sys.stdin)
assert resolve_token(old_token) is None
with TestClient(app) as client:
    result = client.post('/auth/login', json=credentials)
    assert result.status_code == 200
    assert resolve_token(result.json()['access_token']) == result.json()['customer']['id']
    print(json.dumps(result.json()['customer']))
'''
    result = subprocess.run(
        [sys.executable, "-c", script], input=json.dumps([LOGIN, old_token]),
        text=True, capture_output=True, check=True,
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(storage.parent)},
    )
    assert json.loads(result.stdout) == customer


def test_openapi_auth_contract(client):
    spec = client.get("/openapi.json").json()
    for path, request, response, statuses in [
        ("/customers", "CustomerCreate", "CustomerRead", {"201", "409", "422", "500"}),
        ("/auth/login", "LoginRequest", "TokenResponse", {"200", "401", "403", "422", "500"}),
    ]:
        operation = spec["paths"][path]["post"]
        assert set(operation["responses"]) == statuses
        assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith('/' + request)
        success = "201" if path == "/customers" else "200"
        assert operation["responses"][success]["content"]["application/json"]["schema"]["$ref"].endswith('/' + response)
        assert "text/plain" in operation["responses"]["500"]["content"]
    assert "password_hash" not in spec["components"]["schemas"]["CustomerRead"]["properties"]
