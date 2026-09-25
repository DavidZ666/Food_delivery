import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import restaurant_repo


@pytest.fixture
def test_data(tmp_path, monkeypatch):
    restaurants = [
        {"id": "test-1", "name": "Test Sushi", "cuisine": "Japanese"},
        {"id": "test-2", "name": "Test Noodles", "cuisine": "Chinese"},
    ]

    file_path = tmp_path / "restaurants.json"
    file_path.write_text(json.dumps(restaurants), encoding="utf-8")

    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))

    return file_path, restaurants


@pytest.fixture
def client(test_data):
    with TestClient(app) as client:
        yield client


# health
def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# restaurant
def test_restaurants_endpoint(client, test_data):
    _, expected = test_data

    response = client.get("/restaurants")

    assert response.status_code == 200
    assert response.json() == expected


# Repository
def test_restaurant_repository(test_data):
    _, expected = test_data

    assert restaurant_repo.list_all() == expected


# JSON error
def test_invalid_json(test_data):
    file_path, _ = test_data
    file_path.write_text("{broken json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        restaurant_repo.list_all()