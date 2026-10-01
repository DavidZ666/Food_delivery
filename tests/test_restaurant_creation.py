import copy
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store, restaurant_repo
from app.schemas.restaurant import RestaurantCreate
from app.services import restaurant_service


@pytest.fixture
def payload():
    return {
        "name": "Café 新", "cuisine": "Fusion",
        "location": {
            "address": "3 Main St", "city": "Kelowna",
            "province": "BC", "postal_code": "V1V 1V3",
        },
    }


def test_create_preserves_records_and_products(client, data_dir, payload):
    original = restaurant_repo.list_all()
    products_path = data_dir / "products.json"
    products_path.write_text('[{"product_id": 1, "restaurant_id": 101}]')
    products = products_path.read_bytes()
    payload.update(description="Lunch", logo_url="https://example.com/logo.png",
                   hours={"monday": "09:00-18:00", "sunday": None})

    response = client.post("/restaurants", json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 103
    assert created["name"] == payload["name"]
    assert created["description"] == "Lunch"
    assert created["logo_url"] == payload["logo_url"]
    assert created["hours"]["monday"] == "09:00-18:00"
    assert created["hours"]["sunday"] is None
    assert restaurant_repo.list_all() == [*original, created]
    assert client.get("/restaurants").json()[-1] == created
    assert products_path.read_bytes() == products


def test_empty_storage_starts_at_one(client, data_dir, payload):
    (data_dir / "restaurants.json").write_text("[]")
    response = client.post("/restaurants", json=payload)
    assert response.status_code == 201
    assert response.json() == {**payload, "id": 1, "description": None,
                               "logo_url": None, "hours": None}


def test_creation_survives_fresh_process(client, data_dir, payload):
    created = client.post("/restaurants", json=payload).json()
    script = '''
import json
import sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    before = client.get("/restaurants").json()
    response = client.post("/restaurants", json=json.loads(sys.argv[1]))
    print(json.dumps([before, response.status_code, response.json()]))
'''
    output = subprocess.check_output(
        [sys.executable, "-c", script, json.dumps(payload)],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)}, text=True,
    )
    before, status, after = json.loads(output)
    assert before[-1] == created
    assert status == 201
    assert after["id"] == created["id"] + 1
    assert restaurant_repo.list_all()[-1] == after


@pytest.mark.parametrize("path,value", [
    (("name",), "  "), (("name",), None), (("name",), 42),
    (("cuisine",), "\t"), (("location",), None),
    (("location", "address"), ""), (("location", "city"), " "),
    (("location", "province"), None), (("location", "postal_code"), "\n"),
    (("id",), 99), (("unknown",), True), (("location", "unknown"), True),
    (("hours",), {"unknown": "09:00-18:00"}),
    (("hours",), {"monday": 17}), (("description",), ["text"]),
])
def test_invalid_request_preserves_storage(client, data_dir, payload, path, value):
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    original = (data_dir / "restaurants.json").read_bytes()
    assert client.post("/restaurants", json=payload).status_code == 422
    assert (data_dir / "restaurants.json").read_bytes() == original


@pytest.mark.parametrize("missing", ["name", "cuisine", "location"])
def test_missing_required_field(client, data_dir, payload, missing):
    payload.pop(missing)
    original = (data_dir / "restaurants.json").read_bytes()
    assert client.post("/restaurants", json=payload).status_code == 422
    assert (data_dir / "restaurants.json").read_bytes() == original


def test_trim_required_text(client, payload):
    payload["name"] = "  Café 新  "
    payload["location"]["city"] = " Kelowna "
    created = client.post("/restaurants", json=payload).json()
    assert created["name"] == "Café 新"
    assert created["location"]["city"] == "Kelowna"


@pytest.mark.parametrize("stored", [
    "{bad json", "{}", '[{"id": 1}]',
])
def test_bad_storage_is_server_error(data_dir, payload, stored):
    path = data_dir / "restaurants.json"
    path.write_text(stored)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/restaurants", json=payload).status_code == 500
    assert path.read_text() == stored


def test_missing_storage_is_not_reinitialized(data_dir, payload):
    path = data_dir / "restaurants.json"
    missing = data_dir / "missing.json"
    path.rename(missing)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/restaurants", json=payload).status_code == 500
    assert not path.exists()


def test_service_delegates_and_propagates_failure(payload, monkeypatch):
    request = RestaurantCreate(**payload)
    observed = []

    def create(fields):
        observed.append(copy.deepcopy(fields))
        return {**fields, "id": 7}

    monkeypatch.setattr(restaurant_repo, "create", create)
    assert restaurant_service.create_restaurant(request).id == 7
    assert observed == [request.model_dump(mode="json")]

    def fail(fields):
        raise OSError("disk failure")

    monkeypatch.setattr(restaurant_repo, "create", fail)
    with pytest.raises(OSError, match="disk failure"):
        restaurant_service.create_restaurant(request)


def test_write_failure_is_server_error(data_dir, payload, monkeypatch):
    original = (data_dir / "restaurants.json").read_bytes()

    def fail(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr(json_store.os, "replace", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/restaurants", json=payload).status_code == 500
    assert (data_dir / "restaurants.json").read_bytes() == original
    assert not list(data_dir.glob("*.tmp"))


def test_creation_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/restaurants"]["post"]
    assert operation["summary"] == "Create a restaurant"
    assert operation["description"]
    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RestaurantCreate"}
    assert operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RestaurantRead"}
    assert "422" in operation["responses"]
    assert "500" in operation["responses"]
    request = schema["components"]["schemas"]["RestaurantCreate"]
    assert request["additionalProperties"] is False
    assert "id" not in request["properties"]
    assert set(request["required"]) == {"name", "cuisine", "location"}
