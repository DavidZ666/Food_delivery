import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLE_RESTAURANTS = [
    {"id": "t1", "name": "Test Tacos", "cuisine": "Mexican"},
    {"id": "t2", "name": "Test Thai", "cuisine": "Thai"}
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