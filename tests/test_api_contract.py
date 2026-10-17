"""Execute the published OpenAPI examples against isolated JSON storage."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


OPERATIONS = [
    ("get", "/health", 200),
    ("get", "/restaurants", 200),
    ("post", "/restaurants", 201),
    ("get", "/restaurants/{restaurant_id}", 200),
    ("patch", "/restaurants/{restaurant_id}", 200),
    ("get", "/restaurants/{restaurant_id}/menu", 200),
    ("post", "/restaurants/{restaurant_id}/menu", 201),
    ("get", "/restaurants/{restaurant_id}/menu/{product_id}", 200),
    ("patch", "/restaurants/{restaurant_id}/menu/{product_id}", 200),
    ("delete", "/restaurants/{restaurant_id}/menu/{product_id}", 204),
]


@pytest.fixture
def contract(client, data_dir):
    spec = client.get("/openapi.json").json()
    restaurant = spec["paths"]["/restaurants/{restaurant_id}"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    item = spec["paths"]["/restaurants/{restaurant_id}/menu/{product_id}"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    (data_dir / "restaurants.json").write_text(json.dumps([restaurant]))
    (data_dir / "products.json").write_text(json.dumps([item]))
    return spec


def request_body(operation):
    media = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    examples = media.get("examples", {})
    return next(iter(examples.values()))["value"] if examples else None


def url(path, restaurant="1", item="1"):
    return path.replace("{restaurant_id}", restaurant).replace("{product_id}", item)


@pytest.mark.parametrize("method,path,status", OPERATIONS)
def test_documented_success_examples_execute(client, data_dir, contract, method, path, status):
    operation = contract["paths"][path][method]
    assert operation["summary"] and operation["description"]
    for parameter in operation.get("parameters", []):
        assert parameter["description"]
        assert parameter["schema"]["examples"]
    if method == "post":
        target = "restaurants.json" if path == "/restaurants" else "products.json"
        (data_dir / target).write_text("[]")
    response = client.request(method, url(path), json=request_body(operation))
    assert response.status_code == status
    documented = operation["responses"][str(status)]
    if status == 204:
        assert "content" not in documented
        assert response.content == b""
    else:
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == documented["content"]["application/json"]["example"]


@pytest.mark.parametrize("method,path,status,filename", [
    (*entry, filename)
    for entry in OPERATIONS[1:]
    for filename in ("restaurants.json", "products.json")
    if filename == "restaurants.json" or "/menu" in entry[1]
])
@pytest.mark.parametrize("failure", ["missing", "malformed"])
def test_documented_storage_failures_match_actual_format(data_dir, contract, method, path, status, filename, failure):
    operation = contract["paths"][path][method]
    storage = data_dir / filename
    if failure == "missing":
        storage.unlink()
    else:
        storage.write_text("{invalid")
    with TestClient(app, raise_server_exceptions=False) as http:
        response = http.request(method, url(path), json=request_body(operation))
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    media = operation["responses"]["500"]["content"]["text/plain"]
    assert media["schema"] == {"type": "string"}
    assert response.text == media["example"]


def test_empty_product_object_currently_reads_as_empty_menu(client, data_dir, contract):
    storage = data_dir / "products.json"
    storage.write_text("{}")
    response = client.get("/restaurants/1/menu")
    assert response.status_code == 200
    assert response.json() == []
    assert storage.read_text() == "{}"


def test_menu_creation_does_not_validate_existing_products(client, data_dir, contract):
    storage = data_dir / "products.json"
    existing = {**json.loads(storage.read_text())[0], "price": "invalid"}
    storage.write_text(json.dumps([existing]))
    operation = contract["paths"]["/restaurants/{restaurant_id}/menu"]["post"]
    response = client.post("/restaurants/1/menu", json=request_body(operation))
    assert response.status_code == 201
    expected = {**operation["responses"]["201"]["content"]["application/json"]["example"], "product_id": 2}
    assert response.json() == expected
    assert json.loads(storage.read_text()) == [existing, expected]


@pytest.mark.parametrize("method,path,status", [entry for entry in OPERATIONS if "{" in entry[1]])
def test_documented_path_validation_example_matches_actual_response(client, data_dir, contract, method, path, status):
    operation = contract["paths"][path][method]
    before = [(data_dir / name).read_bytes() for name in ("restaurants.json", "products.json")]
    response = client.request(method, url(path, restaurant="abc"), json=request_body(operation))
    assert response.status_code == 422
    media = operation["responses"]["422"]["content"]["application/json"]
    assert media["schema"]["$ref"].endswith("/HTTPValidationError")
    assert response.json() == media["examples"]["invalidId"]["value"]
    assert [(data_dir / name).read_bytes() for name in ("restaurants.json", "products.json")] == before


@pytest.mark.parametrize("path", ["/restaurants", "/restaurants/{restaurant_id}/menu"])
def test_documented_create_validation_example_matches_actual_response(client, contract, path):
    operation = contract["paths"][path]["post"]
    body = {**request_body(operation), "name": ""}
    response = client.post(url(path), json=body)
    assert response.status_code == 422
    assert response.json() == operation["responses"]["422"]["content"]["application/json"]["examples"]["invalidName"]["value"]


@pytest.mark.parametrize("method,path,status", [entry for entry in OPERATIONS if "{" in entry[1]])
def test_unknown_restaurant_error_matches_documentation(client, contract, method, path, status):
    operation = contract["paths"][path][method]
    response = client.request(method, url(path, restaurant="999"), json=request_body(operation))
    assert response.status_code == 404
    media = operation["responses"]["404"]["content"]["application/json"]
    example = media.get("example") or media["examples"]["restaurant"]["value"]
    assert response.json() == example


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_wrong_owner_error_matches_documentation(client, data_dir, contract, method):
    path = "/restaurants/{restaurant_id}/menu/{product_id}"
    operation = contract["paths"][path][method]
    products = json.loads((data_dir / "products.json").read_text())
    products[0]["restaurant_id"] = 2
    (data_dir / "products.json").write_text(json.dumps(products))
    before = (data_dir / "products.json").read_bytes()
    response = client.request(method, url(path), json=request_body(operation))
    assert response.status_code == 404
    assert response.json() == operation["responses"]["404"]["content"]["application/json"]["examples"]["item"]["value"]
    assert (data_dir / "products.json").read_bytes() == before


def test_menu_noop_example_and_deleted_maximum_id_reuse(client, contract):
    path = "/restaurants/1/menu/1"
    original = client.get(path).json()
    operation = contract["paths"]["/restaurants/{restaurant_id}/menu/{product_id}"]["patch"]
    noop = operation["requestBody"]["content"]["application/json"]["examples"]["noop"]["value"]
    assert client.patch(path, json=noop).json() == original
    assert client.delete(path).status_code == 204
    create = contract["paths"]["/restaurants/{restaurant_id}/menu"]["post"]
    response = client.post("/restaurants/1/menu", json=request_body(create))
    assert response.status_code == 201
    assert response.json()["product_id"] == 1  # Current ID policy, not a tombstone allocator.


def test_health_is_liveness_even_with_missing_storage(client, data_dir, contract):
    (data_dir / "restaurants.json").unlink()
    (data_dir / "products.json").unlink()
    assert client.get("/health").json() == {"status": "ok"}
    response = contract["paths"]["/health"]["get"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("/HealthResponse")
