import json

import pytest
from fastapi.testclient import TestClient

from app.core import customer_auth
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


MANAGER_PASSWORD = "manager-test-password"
MANAGER = {
    "id": 1, "name": "Manager", "email": "manager@example.com", "phone": "250-555-0100",
    "delivery_address": {
        "address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1",
    },
    "password_hash": customer_auth.hash_password(MANAGER_PASSWORD),
    "role": "restaurant_owner", "is_active": True,
}


@pytest.fixture
def manager_headers(monkeypatch):
    """Bearer header for the seeded restaurant owner, with isolated sessions."""
    monkeypatch.setattr(customer_auth, "_sessions", {})
    return {"Authorization": f"Bearer {customer_auth.issue_token(MANAGER['id'])}"}


@pytest.fixture
def data_dir(tmp_path, monkeypatch, manager_headers):
    """Point the app at a temporary data folder with sample restaurants and a manager."""
    (tmp_path / "restaurants.json").write_text(json.dumps(SAMPLE_RESTAURANTS))
    (tmp_path / "customers.json").write_text(json.dumps([MANAGER]))
    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(data_dir, manager_headers):
    """Client authorized for restaurant/menu writes (#78)."""
    return TestClient(app, headers=manager_headers)


@pytest.fixture
def anonymous_client(data_dir):
    return TestClient(app)