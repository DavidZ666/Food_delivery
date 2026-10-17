"""Menu-update acceptance (#49), using only temporary JSON data."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store


ROOT = Path(__file__).resolve().parents[1]
CHANGES = {
    "name": "Soupe du jour",
    "description": "Légumes frais",
    "price": 6.75,
    "category": "Specials",
    "image": "https://example.com/soup.png",
    "is_available": False,
}


@pytest.fixture(scope="module", autouse=True)
def representative_data_unchanged():
    paths = [ROOT / "data" / name for name in ("restaurants.json", "products.json")]
    before = [path.read_bytes() for path in paths]
    yield
    assert [path.read_bytes() for path in paths] == before


@pytest.fixture
def menu_store(data_dir):
    products = [
        {"product_id": 8, "restaurant_id": 101, "name": "Soup",
         "description": "Vegetable soup", "price": 5.0, "category": "Main",
         "image": "", "is_available": True},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "", "is_available": True},
        {"product_id": 5, "restaurant_id": 101, "name": "Salad",
         "description": "Green salad", "price": 4.0, "category": "Sides",
         "image": "", "is_available": True},
    ]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    return products


def storage_bytes(data_dir):
    return [(data_dir / name).read_bytes()
            for name in ("restaurants.json", "products.json")]


@pytest.mark.parametrize("changes", [
    CHANGES,
    {"price": 7.5},
    {},
    {"product_id": 99, "restaurant_id": 102, "unknown": "ignored"},
], ids=["all-fields", "partial", "empty-noop", "immutable-ids"])
def test_update_survives_a_fresh_process(data_dir, menu_store, changes):
    restaurants_before = (data_dir / "restaurants.json").read_bytes()
    expected = {**menu_store[0], **{key: value for key, value in changes.items()
                                 if key in CHANGES}}
    with TestClient(app) as http:
        response = http.patch("/restaurants/101/menu/8", json=changes)
        assert response.status_code == 200
        assert response.json() == expected

    # A new interpreter must load the persisted values, without shared app state.
    script = """
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as http:
    responses = [http.get(path) for path in (
        '/restaurants/101/menu', '/restaurants/101/menu/8',
        '/restaurants/102/menu', '/restaurants/102/menu/8')]
    print(json.dumps([[response.status_code, response.json()] for response in responses]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT,
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, check=True, timeout=15,
    )
    assert json.loads(result.stdout) == [
        [200, [expected, menu_store[2]]],
        [200, expected],
        [200, [menu_store[1]]],
        [404, {"detail": "Menu item not found"}],
    ]
    assert json.loads((data_dir / "products.json").read_text(encoding="utf-8")) == [
        expected, menu_store[1], menu_store[2],
    ]
    assert (data_dir / "restaurants.json").read_bytes() == restaurants_before


@pytest.mark.parametrize("path,changes,status,detail", [
    ("/restaurants/101/menu/8", {"price": None}, 422, None),
    ("/restaurants/101/menu/invalid", {"price": 6}, 422, None),
    ("/restaurants/999/menu/8", {"price": 6}, 404, "Restaurant not found"),
    ("/restaurants/101/menu/999", {"price": 6}, 404, "Menu item not found"),
    ("/restaurants/102/menu/8", {"price": 6}, 404, "Menu item not found"),
])
def test_rejected_update_preserves_both_stores(client, data_dir, menu_store,
                                              path, changes, status, detail):
    before = storage_bytes(data_dir)
    response = client.patch(path, json=changes)
    assert response.status_code == status
    if detail is not None:
        assert response.json() == {"detail": detail}
    assert storage_bytes(data_dir) == before
    assert client.get("/restaurants/101/menu/8").json() == menu_store[0]


@pytest.mark.parametrize("stage", ["temporary-file", "serialization", "replacement"])
def test_failed_update_preserves_data_and_allows_retry(data_dir, menu_store,
                                                      monkeypatch, stage):
    before = storage_bytes(data_dir)
    calls = []

    def fail(*args, **kwargs):
        calls.append(stage)
        if stage == "serialization":
            args[1].write('{"incomplete":')
        raise OSError("Simulated menu write failure")

    target, attribute = {
        "temporary-file": (json_store.tempfile, "mkstemp"),
        "serialization": (json_store.json, "dump"),
        "replacement": (json_store.os, "replace"),
    }[stage]
    with TestClient(app, raise_server_exceptions=False) as http:
        with monkeypatch.context() as patch:
            patch.setattr(target, attribute, fail)
            response = http.patch("/restaurants/101/menu/8", json=CHANGES)
        assert calls == [stage]
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert storage_bytes(data_dir) == before
        assert http.get("/restaurants/101/menu/8").json() == menu_store[0]

        retry = http.patch("/restaurants/101/menu/8", json=CHANGES)
        assert retry.status_code == 200
        assert retry.json() == {**menu_store[0], **CHANGES}
        assert http.get("/restaurants/101/menu").json() == [retry.json(), menu_store[2]]
    stored = json.loads((data_dir / "products.json").read_text(encoding="utf-8"))
    assert stored == [retry.json(), menu_store[1], menu_store[2]]
    assert (data_dir / "restaurants.json").read_bytes() == before[0]
