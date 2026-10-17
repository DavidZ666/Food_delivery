"""Menu creation uses isolated data and the shared JSON transaction (#46)."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store, product_repo


NEW_ITEM = {"name": "Soup", "category": "Main", "price": 5.5}


@pytest.fixture
def products(data_dir):
    records = [
        {"product_id": 8, "restaurant_id": 101, "name": "Taco",
         "description": "Bean taco", "price": 4.5, "category": "Main",
         "image": "", "is_available": False, "metadata": {"special": True}},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "", "is_available": True},
    ]
    (data_dir / "products.json").write_text(json.dumps(records), encoding="utf-8")
    return records


def storage_bytes(data_dir):
    return {name: (data_dir / name).read_bytes() if (data_dir / name).exists() else None
            for name in ("restaurants.json", "products.json")}


def test_creation_preserves_sparse_ids_metadata_and_ownership(client, data_dir, products):
    before = (data_dir / "restaurants.json").read_bytes()
    response = client.post("/restaurants/102/menu", json={
        **NEW_ITEM, "product_id": 1, "restaurant_id": 999,
    })
    assert response.status_code == 201
    created = {**NEW_ITEM, "product_id": 9, "restaurant_id": 102,
               "description": "", "image": "", "is_available": True}
    assert response.json() == created
    assert product_repo.list_all() == [*products, created]
    assert client.get("/restaurants/102/menu").json() == [products[1], created]
    assert client.get("/restaurants/102/menu/9").json() == created
    assert client.get("/restaurants/101/menu/9").status_code == 404
    assert (data_dir / "restaurants.json").read_bytes() == before
    assert not list(data_dir.glob("*.tmp"))


def test_concurrent_creations_keep_unique_ids_and_all_records(data_dir, products):
    before = (data_dir / "restaurants.json").read_bytes()
    start = Barrier(8)

    def create(index):
        with TestClient(app) as http:
            start.wait(timeout=10)
            response = http.post(f"/restaurants/{101 + index % 2}/menu", json={
                **NEW_ITEM, "name": f"Item {index}",
            })
            assert response.status_code == 201
            return response.json()

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create, range(24)))
    assert sorted(item["product_id"] for item in created) == list(range(9, 33))
    stored = product_repo.list_all()
    assert stored[:2] == products
    assert sorted(stored[2:], key=lambda item: item["product_id"]) == sorted(
        created, key=lambda item: item["product_id"],
    )
    assert {item["name"]: item["restaurant_id"] for item in created} == {
        f"Item {index}": 101 + index % 2 for index in range(24)
    }
    assert (data_dir / "restaurants.json").read_bytes() == before
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.parametrize("body", [
    {}, {"category": "Main", "price": 5}, {**NEW_ITEM, "name": ""},
    {**NEW_ITEM, "category": None}, {**NEW_ITEM, "price": 0},
    {**NEW_ITEM, "is_available": "maybe"},
])
def test_invalid_creation_preserves_both_stores(client, data_dir, products, body):
    before = storage_bytes(data_dir)
    assert client.post("/restaurants/101/menu", json=body).status_code == 422
    assert storage_bytes(data_dir) == before


def test_unknown_restaurant_preserves_storage(client, data_dir, products):
    before = storage_bytes(data_dir)
    response = client.post("/restaurants/999/menu", json=NEW_ITEM)
    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}
    assert storage_bytes(data_dir) == before


@pytest.mark.parametrize("filename", ["restaurants.json", "products.json"])
@pytest.mark.parametrize("failure", ["missing", "malformed"])
def test_storage_failures_do_not_initialize_or_rewrite_files(data_dir, products, filename, failure):
    path = data_dir / filename
    if failure == "missing":
        path.rename(data_dir / f"unavailable-{filename}")
    else:
        path.write_text("{invalid", encoding="utf-8")
    before = storage_bytes(data_dir)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.post("/restaurants/101/menu", json=NEW_ITEM).status_code == 500
    assert storage_bytes(data_dir) == before
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.parametrize("stored", [None, {}, [1], [{"product_id": 8}]])
def test_invalid_collection_is_rejected_without_writing(data_dir, products, stored):
    (data_dir / "products.json").write_text(json.dumps(stored), encoding="utf-8")
    before = storage_bytes(data_dir)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.post("/restaurants/101/menu", json=NEW_ITEM).status_code == 500
    assert storage_bytes(data_dir) == before


@pytest.mark.parametrize("identifier", [0, -1, True, "8", 8.0, 3])
def test_invalid_or_duplicate_stored_ids_are_rejected(data_dir, products, identifier):
    products[0]["product_id"] = identifier
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    before = storage_bytes(data_dir)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.post("/restaurants/101/menu", json=NEW_ITEM).status_code == 500
    assert storage_bytes(data_dir) == before


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("category", ""), ("price", 0),
    ("price", "invalid"), ("price", float("inf")), ("description", None),
])
def test_invalid_stored_fields_are_rejected(data_dir, products, field, value):
    products[0][field] = value
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    before = storage_bytes(data_dir)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.post("/restaurants/101/menu", json=NEW_ITEM).status_code == 500
    assert storage_bytes(data_dir) == before


@pytest.mark.parametrize("stage", ["temporary", "serialization", "sync", "replacement"])
def test_failed_transaction_preserves_files_cleans_temp_and_allows_retry(
    data_dir, products, monkeypatch, stage,
):
    before = storage_bytes(data_dir)
    calls = []

    def fail(*args, **kwargs):
        calls.append(stage)
        if stage == "serialization":
            args[1].write('{"incomplete":')
        raise OSError("Simulated creation failure")

    target, attribute = {
        "temporary": (json_store, "NamedTemporaryFile"),
        "serialization": (json_store.json, "dump"),
        "sync": (json_store.os, "fsync"),
        "replacement": (json_store.os, "replace"),
    }[stage]
    with TestClient(app, raise_server_exceptions=False) as http:
        with monkeypatch.context() as patch:
            patch.setattr(target, attribute, fail)
            response = http.post("/restaurants/101/menu", json=NEW_ITEM)
        assert calls == [stage]
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert storage_bytes(data_dir) == before
        assert not list(data_dir.glob("*.tmp"))
        retry = http.post("/restaurants/101/menu", json=NEW_ITEM)
        assert retry.status_code == 201
        assert retry.json()["product_id"] == 9
        assert product_repo.list_all() == [*products, retry.json()]
    assert (data_dir / "restaurants.json").read_bytes() == before["restaurants.json"]
