import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.repositories import customer_repo
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate


ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
REGISTRATION = {
    "name": "Ada Lovelace", "email": "Ada@Example.com", "password": "correct-horse",
    "phone": "250-555-0100", "delivery_address": ADDRESS,
}


def new_record(email="ada@example.com", **extra):
    return {
        "name": "Ada", "email": email, "phone": "250-555-0100",
        "delivery_address": ADDRESS, "role": "customer", "is_active": True,
        "password_hash": "scrypt$hash", **extra,
    }


@pytest.fixture
def storage(tmp_path, monkeypatch):
    path = tmp_path / "customers.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))
    return path


def stored(path):
    return json.loads(path.read_text(encoding="utf-8"))


# Schemas

def test_registration_normalizes_email_and_trims_text():
    customer = CustomerCreate.model_validate({**REGISTRATION, "name": "  Ada  "})

    assert customer.email == "ada@example.com"
    assert customer.name == "Ada"


@pytest.mark.parametrize("change", [
    {"email": "not-an-email"},
    {"password": "short"},
    {"name": "   "},
    {"delivery_address": {**ADDRESS, "city": ""}},
    {"role": "admin"},
    {"is_active": False},
    {"id": 7},
])
def test_registration_rejects_invalid_or_server_owned_fields(change):
    with pytest.raises(ValidationError):
        CustomerCreate.model_validate({**REGISTRATION, **change})


def test_registration_requires_delivery_address():
    body = {k: v for k, v in REGISTRATION.items() if k != "delivery_address"}

    with pytest.raises(ValidationError):
        CustomerCreate.model_validate(body)


def test_update_accepts_partial_address_and_rejects_empty_or_protected_fields():
    update = CustomerUpdate.model_validate({"delivery_address": {"city": "Vancouver"}})

    assert update.model_dump(exclude_unset=True) == {"delivery_address": {"city": "Vancouver"}}
    for body in ({}, {"delivery_address": {}}, {"email": "b@example.com"},
                 {"role": "admin"}, {"name": None}):
        with pytest.raises(ValidationError):
            CustomerUpdate.model_validate(body)


def test_read_model_excludes_password_hash_and_restricts_roles():
    record = {**new_record(), "id": 1}

    assert "password_hash" not in CustomerRead.model_validate(record).model_dump()
    with pytest.raises(ValidationError):
        CustomerRead.model_validate({**record, "role": "superuser"})


def test_auth_schemas():
    login = LoginRequest.model_validate({"email": " ADA@example.com ", "password": "x"})
    token = TokenResponse(access_token="t", customer={**new_record(), "id": 1})

    assert login.email == "ada@example.com"
    assert token.token_type == "bearer"
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"email": "ada@example.com"})


# Repository

def test_create_allocates_sequential_ids_and_preserves_records(storage):
    existing = {**new_record("old@example.com"), "id": 5, "metadata": {"source": "seed"}}
    storage.write_text(json.dumps([existing]), encoding="utf-8")

    created = customer_repo.create(new_record())

    assert created["id"] == 6
    assert stored(storage) == [existing, created]
    assert customer_repo.get_by_id(6) == created


def test_first_customer_id_is_one(storage):
    assert customer_repo.create(new_record())["id"] == 1


def test_duplicate_email_is_case_insensitive_and_leaves_storage_unchanged(storage):
    customer_repo.create(new_record())
    before = storage.read_bytes()

    with pytest.raises(customer_repo.DuplicateEmailError):
        customer_repo.create(new_record("ADA@example.com"))

    assert storage.read_bytes() == before


def test_get_by_email_is_case_insensitive(storage):
    created = customer_repo.create(new_record())

    assert customer_repo.get_by_email(" Ada@Example.COM ") == created
    assert customer_repo.get_by_email("missing@example.com") is None
    assert customer_repo.get_by_id(99) is None


def test_stored_email_whitespace_does_not_bypass_lookup_or_uniqueness(storage):
    existing = {**new_record(" Ada@Example.COM "), "id": 1}
    storage.write_text(json.dumps([existing]), encoding="utf-8")
    before = storage.read_bytes()

    assert customer_repo.get_by_email("ada@example.com") == existing
    with pytest.raises(customer_repo.DuplicateEmailError):
        customer_repo.create(new_record())
    assert storage.read_bytes() == before


def test_ids_are_stable_across_processes(storage):
    customer_repo.create(new_record())
    script = (
        "from app.repositories import customer_repo;"
        "print(customer_repo.create({'name':'Bo','email':'bo@example.com','phone':'1',"
        "'delivery_address':{'address':'a','city':'b','province':'c','postal_code':'d'},"
        "'role':'customer','is_active':True,'password_hash':'h'})['id'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True,
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(storage.parent)}, encoding="utf-8",
    )

    assert result.stdout.strip() == "2"
    assert [r["id"] for r in stored(storage)] == [1, 2]


def test_update_merges_address_and_preserves_other_fields(storage):
    created = customer_repo.create(new_record())

    updated = customer_repo.update_by_id(
        created["id"], {"phone": "111", "delivery_address": {"city": "Vancouver"}},
    )

    assert updated == {**created, "phone": "111",
                       "delivery_address": {**ADDRESS, "city": "Vancouver"}}
    assert stored(storage) == [updated]


def test_update_can_deactivate(storage):
    created = customer_repo.create(new_record())

    assert customer_repo.update_by_id(created["id"], {"is_active": False})["is_active"] is False
    assert customer_repo.get_by_id(created["id"])["is_active"] is False


def test_update_persists_normalized_fields_and_preserves_metadata(storage):
    existing = {**new_record(), "id": 1, "metadata": {"source": "seed"}}
    storage.write_text(json.dumps([existing]), encoding="utf-8")

    updated = customer_repo.update_by_id(
        1, {"name": "  Grace  ", "phone": "  123  ",
            "delivery_address": {"city": "  Vancouver  "}},
    )

    assert updated == {**existing, "name": "Grace", "phone": "123",
                       "delivery_address": {**ADDRESS, "city": "Vancouver"}}
    assert stored(storage) == [updated]


def test_update_rejects_missing_customer_and_immutable_fields(storage):
    customer_repo.create(new_record())
    before = storage.read_bytes()

    with pytest.raises(customer_repo.CustomerRecordNotFoundError):
        customer_repo.update_by_id(99, {"phone": "1"})
    for changes in ({}, {"email": "x@example.com"}, {"role": "admin"}, {"id": 2}):
        with pytest.raises(ValueError):
            customer_repo.update_by_id(1, changes)

    assert storage.read_bytes() == before


@pytest.mark.parametrize("content", [
    "{ not json",
    "{}",
    json.dumps([{"id": 1}]),
    json.dumps([{**new_record(), "id": 0}]),
    json.dumps([{**new_record(), "id": "1"}]),
    json.dumps([{**new_record(), "id": True}]),
    json.dumps([{**new_record(), "id": 1, "email": "invalid"}]),
    json.dumps([{**new_record(), "id": 1, "name": "  "}]),
    json.dumps([{**new_record(), "id": 1, "phone": ""}]),
    json.dumps([{**new_record(), "id": 1, "role": "owner"}]),
    json.dumps([{**new_record(), "id": 1}, {**new_record("b@example.com"), "id": 1}]),
    json.dumps([{**new_record(), "id": 1}, {**new_record("ADA@example.com"), "id": 2}]),
    json.dumps([{**new_record(), "id": 1}, {**new_record(" Ada@Example.COM "), "id": 2}]),
])
def test_malformed_storage_is_rejected_without_overwriting(storage, content):
    storage.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        customer_repo.list_all()
    with pytest.raises(ValueError):
        customer_repo.create(new_record("new@example.com"))
    with pytest.raises(ValueError):
        customer_repo.update_by_id(1, {"phone": "1"})

    assert storage.read_text(encoding="utf-8") == content


def test_missing_storage_is_not_created(storage):
    storage.unlink()

    with pytest.raises(FileNotFoundError):
        customer_repo.create(new_record())
    assert not storage.exists()
