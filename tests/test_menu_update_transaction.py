"""Concurrent menu changes preserve records, IDs and ownership (#48)."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import product_repo


@pytest.fixture
def products(data_dir):
    records = [
        {"product_id": 8, "restaurant_id": 101, "name": "Soup",
         "description": "Vegetable soup", "price": 5.0, "category": "Main",
         "image": "", "is_available": True, "metadata": {"special": True}},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "", "is_available": True},
    ]
    (data_dir / "products.json").write_text(json.dumps(records), encoding="utf-8")
    return records


def test_concurrent_partial_updates_and_creation_preserve_every_change(data_dir, products):
    restaurants_before = (data_dir / "restaurants.json").read_bytes()
    changes = {"name": "New soup", "description": "Seasonal", "price": 6.75,
               "category": "Specials", "image": "soup.png", "is_available": False}
    jobs = [("patch", "/restaurants/101/menu/8", {key: value})
            for key, value in changes.items()]
    jobs += [("post", f"/restaurants/{101 + index % 2}/menu",
              {"name": f"Item {index}", "category": "Main", "price": 5.5})
             for index in range(8)]
    start = Barrier(7)

    def request(job):
        method, path, body = job
        with TestClient(app) as http:
            start.wait(timeout=10)
            response = http.request(method, path, json=body)
            assert response.status_code == (201 if method == "post" else 200)
            return response.json()

    with ThreadPoolExecutor(max_workers=7) as pool:
        responses = list(pool.map(request, jobs))
    stored = product_repo.list_all()
    assert stored[:2] == [{**products[0], **changes}, products[1]]
    assert sorted(stored[2:], key=lambda item: item["product_id"]) == sorted(
        responses[6:], key=lambda item: item["product_id"],
    )
    assert sorted(item["product_id"] for item in stored[2:]) == list(range(9, 17))
    assert {item["name"]: item["restaurant_id"] for item in stored[2:]} == {
        f"Item {index}": 101 + index % 2 for index in range(8)
    }
    assert (data_dir / "restaurants.json").read_bytes() == restaurants_before
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.parametrize("corruption", ["duplicate-id", "invalid-price", "invalid-collection"])
def test_invalid_storage_is_not_rewritten_by_updates(data_dir, products, corruption):
    if corruption == "duplicate-id":
        products[0]["product_id"] = 3
    elif corruption == "invalid-price":
        products[0]["price"] = 0
    else:
        products = {}
    path = data_dir / "products.json"
    path.write_text(json.dumps(products), encoding="utf-8")
    before = path.read_bytes()
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.patch("/restaurants/101/menu/8", json={"price": 6}).status_code == 500
    assert path.read_bytes() == before
    assert not list(data_dir.glob("*.tmp"))
