import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLE_RESTAURANTS = [
    {
        "id": 101,
        "name": "Testaurant",
        "cuisine": "Mexican",
        "location": {
            "address": "1 Test St",
            "city": "Kelowna",
            "province": "BC",
            "postal_code": "V1V 1V1"
        },
        "description": "Test description",
        "logo_url": "https://example.com/logo.png",
        "hours": {
            "monday": "09:00-21:00",
            "tuesday": "09:00-21:00",
            "wednesday": "09:00-21:00",
            "thursday": "09:00-21:00",
            "friday": "09:00-22:00",
            "saturday": "10:00-22:00",
            "sunday": None
        }
    },
    {
        "id": 102,
        "name": "McTest",
        "cuisine": "Fast Food",
        "location": {
            "address": "2 Test St",
            "city": "Kelowna",
            "province": "BC",
            "postal_code": "V1V 1V2",
        }
    }
]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point the app at a temporary data folder containing sample restaurants."""
    (tmp_path / "restaurants.json").write_text(json.dumps(SAMPLE_RESTAURANTS))
    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(app)