"""Unmodified new items survive restart with stable IDs and ownership (#47)."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import product_repo


ROOT = Path(__file__).resolve().parents[1]
EXISTING = [{"product_id": 8, "restaurant_id": 102, "name": "Fries",
             "description": "Golden fries", "price": 2.0, "category": "Sides",
             "image": "", "is_available": True, "metadata": {"special": True}}]


@pytest.fixture(scope="module", autouse=True)
def representative_data_unchanged():
    paths = [ROOT / "data" / name for name in ("restaurants.json", "products.json")]
    before = [path.read_bytes() for path in paths]
    yield
    assert [path.read_bytes() for path in paths] == before


@pytest.mark.parametrize("existing", [[], EXISTING], ids=["empty", "existing-records"])
@pytest.mark.parametrize("body", [
    {"name": "Soup", "category": "Main", "price": 5.5},
    {"name": "Soupe du jour", "category": "Specials", "price": 6.75,
     "description": "Légumes frais", "image": "soup.png", "is_available": False,
     "product_id": 999, "restaurant_id": 999},
], ids=["defaults", "all-fields"])
def test_new_items_and_next_id_survive_restart(data_dir, existing, body):
    (data_dir / "products.json").write_text(json.dumps(existing), encoding="utf-8")
    restaurants_before = (data_dir / "restaurants.json").read_bytes()
    first_id = 9 if existing else 1
    fields = {"description": "", "image": "", "is_available": True,
              **{key: value for key, value in body.items()
                 if key not in {"product_id", "restaurant_id"}}}
    created = []
    with TestClient(app) as http:
        for offset, owner in enumerate((101, 102)):
            response = http.post(f"/restaurants/{owner}/menu", json=body)
            expected = {**fields, "product_id": first_id + offset, "restaurant_id": owner}
            assert response.status_code == 201
            assert response.json() == expected
            created.append(expected)

    paths = [f"/restaurants/{item['restaurant_id']}/menu/{item['product_id']}"
             for item in created]
    paths += ["/restaurants/101/menu", "/restaurants/102/menu",
              f"/restaurants/102/menu/{first_id}"]
    script = """
import json
import sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as http:
    responses = [http.get(path) for path in json.load(sys.stdin)]
    next_item = http.post('/restaurants/101/menu', json={
        'name': 'Next item', 'category': 'Main', 'price': 3})
    print(json.dumps({
        'reads': [[response.status_code, response.json()] for response in responses],
        'next': [next_item.status_code, next_item.json()]}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, input=json.dumps(paths),
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, check=True, timeout=15,
    )
    observed = json.loads(result.stdout)
    # Response models omit extra metadata; persisted dictionaries retain it.
    previous_menu = [{key: value for key, value in item.items() if key != "metadata"}
                     for item in existing]
    assert observed["reads"] == [
        [200, created[0]], [200, created[1]],
        [200, [created[0]]], [200, [*previous_menu, created[1]]],
        [404, {"detail": "Menu item not found"}],
    ]
    next_item = {"product_id": first_id + 2, "restaurant_id": 101, "name": "Next item",
                 "category": "Main", "price": 3.0, "description": "", "image": "",
                 "is_available": True}
    assert observed["next"] == [201, next_item]
    assert product_repo.list_all() == [*existing, *created, next_item]
    assert (data_dir / "restaurants.json").read_bytes() == restaurants_before
    assert not list(data_dir.glob("*.tmp"))
