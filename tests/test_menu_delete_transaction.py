"""Deletion cannot overwrite other menu transactions (#62)."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store, product_repo


@pytest.fixture
def products(data_dir):
    records = [
        {"product_id": 8, "restaurant_id": 101, "name": "Soup",
         "description": "Vegetable soup", "price": 5.0, "category": "Main",
         "image": "", "is_available": True, "metadata": {"special": True}},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "", "is_available": True},
        {"product_id": 2, "restaurant_id": 101, "name": "Salad",
         "description": "Green salad", "price": 4.0, "category": "Sides",
         "image": "", "is_available": False},
    ]
    (data_dir / "products.json").write_text(json.dumps(records), encoding="utf-8")
    return records


def test_concurrent_delete_create_and_update_preserve_all_other_changes(data_dir, products):
    restaurants_before = (data_dir / "restaurants.json").read_bytes()
    changes = {"name": "New soup", "description": "Seasonal", "price": 6.75,
               "category": "Specials", "image": "soup.png", "is_available": False}
    jobs = [("delete", "/restaurants/101/menu/2", None)]
    jobs += [("patch", "/restaurants/101/menu/8", {key: value})
             for key, value in changes.items()]
    jobs += [("post", f"/restaurants/{101 + index % 2}/menu",
              {"name": f"Item {index}", "category": "Main", "price": 5.5})
             for index in range(7)]
    start = Barrier(7)

    def request(job):
        method, path, body = job
        with TestClient(app) as http:
            start.wait(timeout=10)
            response = http.request(method, path, json=body)
            assert response.status_code == {"delete": 204, "post": 201, "patch": 200}[method]
            if method == "delete":
                assert response.content == b""
                return None
            return response.json()

    with ThreadPoolExecutor(max_workers=7) as pool:
        responses = list(pool.map(request, jobs))
    stored = product_repo.list_all()
    assert stored[:2] == [{**products[0], **changes}, products[1]]
    assert sorted(stored[2:], key=lambda item: item["product_id"]) == sorted(
        responses[7:], key=lambda item: item["product_id"],
    )
    assert sorted(item["product_id"] for item in stored[2:]) == list(range(9, 16))
    assert {item["name"]: item["restaurant_id"] for item in stored[2:]} == {
        f"Item {index}": 101 + index % 2 for index in range(7)
    }
    with TestClient(app) as http:
        assert http.get("/restaurants/101/menu/2").status_code == 404
    assert (data_dir / "restaurants.json").read_bytes() == restaurants_before
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.parametrize("stage", ["temporary", "serialization", "sync", "replacement"])
def test_failed_delete_preserves_files_cleans_temp_and_allows_retry(
    data_dir, products, monkeypatch, stage,
):
    paths = [data_dir / name for name in ("restaurants.json", "products.json")]
    before = [path.read_bytes() for path in paths]
    calls = []

    def fail(*args, **kwargs):
        calls.append(stage)
        if stage == "serialization":
            args[1].write('{"incomplete":')
        raise OSError("Simulated deletion failure")

    target, attribute = {
        "temporary": (json_store, "NamedTemporaryFile"),
        "serialization": (json_store.json, "dump"),
        "sync": (json_store.os, "fsync"),
        "replacement": (json_store.os, "replace"),
    }[stage]
    with TestClient(app, raise_server_exceptions=False) as http:
        with monkeypatch.context() as patch:
            patch.setattr(target, attribute, fail)
            response = http.delete("/restaurants/101/menu/2")
        assert calls == [stage]
        assert response.status_code == 500
        assert [path.read_bytes() for path in paths] == before
        assert not list(data_dir.glob("*.tmp"))
        assert http.get("/restaurants/101/menu/2").json() == products[2]
        retry = http.delete("/restaurants/101/menu/2")
        assert retry.status_code == 204
        assert retry.content == b""
    assert product_repo.list_all() == products[:2]
    assert paths[0].read_bytes() == before[0]
    assert not list(data_dir.glob("*.tmp"))
