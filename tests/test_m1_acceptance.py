"""M1 API acceptance uses temporary JSON files, never representative data."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store


def test_management_api_and_readback_in_a_fresh_process(client, data_dir):
    (data_dir / "products.json").write_text("[]")
    restaurant = client.post("/restaurants", json={
        "name": "Acceptance Café", "cuisine": "Fusion",
        "location": {"address": "3 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"},
    })
    assert restaurant.status_code == 201
    rid = restaurant.json()["id"]
    updated = client.patch(f"/restaurants/{rid}", json={"location": {"city": "Vancouver"}})
    assert updated.status_code == 200
    item = client.post(f"/restaurants/{rid}/menu", json={"name": "Soup", "category": "Main", "price": 5})
    assert item.status_code == 201
    pid = item.json()["product_id"]
    updated_item = client.patch(f"/restaurants/{rid}/menu/{pid}", json={"price": 6.5, "is_available": False})
    assert updated_item.status_code == 200
    script = f"""
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    print(json.dumps([client.get('/restaurants/{rid}').json(), client.get('/restaurants/{rid}/menu/{pid}').json()]))
"""
    result = subprocess.run([sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, timeout=15, check=True)
    assert json.loads(result.stdout) == [updated.json(), updated_item.json()]


@pytest.mark.parametrize("field", ["name", "description", "category", "price", "image", "is_available"])
def test_null_item_update_is_rejected_without_corrupting_storage(client, data_dir, field):
    path = data_dir / "products.json"
    path.write_text("[]")
    item = client.post("/restaurants/101/menu", json={"name": "Soup", "category": "Main", "price": 5}).json()
    before = path.read_bytes()
    response = client.patch(f"/restaurants/101/menu/{item['product_id']}", json={field: None})
    assert response.status_code == 422
    assert path.read_bytes() == before
    assert client.get(f"/restaurants/101/menu/{item['product_id']}").json() == item


@pytest.mark.parametrize("price", ["inf", "nan", "1e500"])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_nonfinite_prices_are_rejected_before_writing(client, data_dir, method, price):
    path = data_dir / "products.json"
    path.write_text("[]")
    item = client.post("/restaurants/101/menu", json={"name": "Soup", "category": "Main", "price": 5}).json()
    before = path.read_bytes()
    url = "/restaurants/101/menu"
    if method == "patch":
        url += f"/{item['product_id']}"
    body = {"name": "Soup", "category": "Main", "price": price}
    assert getattr(client, method)(url, json=body).status_code == 422
    assert path.read_bytes() == before


@pytest.mark.parametrize("price", ["1e500", "-1e500", "NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_numeric_nonfinite_prices_return_serializable_validation_errors(client, data_dir, method, price):
    path = data_dir / "products.json"
    path.write_text("[]")
    item = client.post("/restaurants/101/menu", json={"name": "Soup", "category": "Main", "price": 5}).json()
    before = path.read_bytes()
    url = "/restaurants/101/menu"
    if method == "patch":
        url += f"/{item['product_id']}"
    response = getattr(client, method)(
        url, content='{"name":"Soup","category":"Main","price":' + price + '}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "price"]
    assert error["type"] == "finite_number"
    assert isinstance(error["input"], str)
    assert path.read_bytes() == before
    assert client.get(f"/restaurants/101/menu/{item['product_id']}").json() == item


@pytest.mark.parametrize("method,path,body", [
    ("post", "/restaurants/101/menu", {"name": "Soup", "category": "Main", "price": 5}),
    ("patch", "/restaurants/101/menu/1", {"price": 8}),
])
def test_failed_menu_write_preserves_storage(data_dir, monkeypatch, method, path, body):
    file = data_dir / "products.json"
    file.write_text(json.dumps([{"product_id": 1, "restaurant_id": 101, "name": "Soup",
        "description": "", "category": "Main", "image": "", "price": 5, "is_available": True}]))
    before = file.read_bytes()
    def fail(*args, **kwargs):
        raise OSError("Simulated replacement failure")
    monkeypatch.setattr(json_store.os, "replace", fail)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert getattr(http, method)(path, json=body).status_code == 500
    assert file.read_bytes() == before


def test_menu_write_openapi_matches_runtime_validation(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path, method, success, model in [
        ("/restaurants/{restaurant_id}/menu", "post", "201", "MenuItemCreate"),
        ("/restaurants/{restaurant_id}/menu/{product_id}", "patch", "200", "MenuItemUpdate"),
    ]:
        operation = paths[path][method]
        assert operation["description"]
        assert {success, "404", "422", "500"} <= set(operation["responses"])
        assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(model)
    fields = schema["components"]["schemas"]["MenuItemUpdate"]["properties"]
    assert all("anyOf" not in field for field in fields.values())


@pytest.mark.parametrize("path", [
    "/app/restaurant.html", "/app/menu-item.html", "/app/js/restaurants.js",
    "/app/js/restaurant-details.js", "/app/js/menu-item.js",
])
def test_browsing_pages_and_modules_are_served(client, path):
    response = client.get(path)
    assert response.status_code == 200
    expected = "text/html" if path.endswith(".html") else "text/javascript"
    assert response.headers["content-type"].startswith(expected)
