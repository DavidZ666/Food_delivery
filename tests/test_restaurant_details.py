import json

import pytest
from fastapi.exceptions import ResponseValidationError

from app.repositories import restaurant_repo
from app.services import restaurant_service


@pytest.mark.parametrize("restaurant_id", [101, 102])
def test_detail_matches_list_without_changing_storage(client, data_dir, restaurant_id):
    data_file = data_dir / "restaurants.json"
    original = data_file.read_bytes()
    expected = next(
        item for item in client.get("/restaurants").json()
        if item["id"] == restaurant_id
    )

    response = client.get(f"/restaurants/{restaurant_id}")

    assert response.status_code == 200
    assert response.json() == expected
    assert data_file.read_bytes() == original


def test_unknown_restaurant_returns_404(client):
    response = client.get("/restaurants/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}


def test_empty_collection_returns_404(client, data_dir):
    (data_dir / "restaurants.json").write_text("[]")

    response = client.get("/restaurants/101")

    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}


@pytest.mark.parametrize("invalid_id", ["abc", "101.5"])
def test_invalid_id_returns_422(client, invalid_id):
    response = client.get(f"/restaurants/{invalid_id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "restaurant_id"]


def test_detail_rejects_invalid_stored_record(client, data_dir):
    (data_dir / "restaurants.json").write_text(json.dumps([{"id": 101}]))

    with pytest.raises(ResponseValidationError):
        client.get("/restaurants/101")


def test_repository_looks_up_stored_id(data_dir):
    assert restaurant_repo.get_by_id(102)["name"] == "McTest"
    assert restaurant_repo.get_by_id(999) is None


def test_storage_failure_is_not_reported_as_missing_restaurant(data_dir):
    (data_dir / "restaurants.json").write_text("invalid json")

    with pytest.raises(json.JSONDecodeError):
        restaurant_service.get_restaurant(101)


def test_service_returns_repository_record(monkeypatch):
    record = {"id": 101, "name": "Stored restaurant"}
    requested_ids = []

    def lookup(restaurant_id):
        requested_ids.append(restaurant_id)
        return record

    monkeypatch.setattr(restaurant_repo, "get_by_id", lookup)

    assert restaurant_service.get_restaurant(101) is record
    assert requested_ids == [101]


def test_service_raises_domain_error_for_missing_restaurant(monkeypatch):
    monkeypatch.setattr(restaurant_repo, "get_by_id", lambda restaurant_id: None)

    with pytest.raises(restaurant_service.RestaurantNotFoundError):
        restaurant_service.get_restaurant(999)


def test_detail_openapi_documents_contract(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/restaurants/{restaurant_id}"]["get"]
    parameter = operation["parameters"][0]

    assert operation["description"]
    assert parameter["name"] == "restaurant_id"
    assert parameter["in"] == "path"
    assert parameter["required"] is True
    assert parameter["schema"]["type"] == "integer"
    assert parameter["description"]
    responses = operation["responses"]
    assert set(responses) == {"200", "404", "422"}
    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RestaurantRead"
    }
    assert responses["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    assert responses["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HTTPValidationError"
    }
