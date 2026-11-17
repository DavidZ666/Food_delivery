"""Order snapshot schemas and repository (#89)."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.repositories import order_repo
from app.schemas.order import Order, utc_timestamp


ADDRESS = {"address": "1 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V1"}
BIG_MAC = {"product_id": 1, "name": "Big Mac", "unit_price": 6.99, "quantity": 3, "line_total": 20.97}
FRIES = {"product_id": 2, "name": "Fries", "unit_price": 3.49, "quantity": 1, "line_total": 3.49}
CREATED_AT = "2026-11-04T18:30:00Z"


def snapshot(customer_id=1, items=(BIG_MAC, FRIES), **changes):
    """Order fields as checkout (#90) will build them, without order_id."""
    items = [dict(item) for item in items]
    subtotal = round(sum(item["line_total"] for item in items), 2)
    return {
        "customer_id": customer_id, "restaurant_id": 1, "delivery_address": dict(ADDRESS),
        "items": items, "subtotal": subtotal, "total": subtotal,
        "status": "placed", "created_at": CREATED_AT, **changes,
    }


def order(order_id=1, **changes):
    return {"order_id": order_id, **snapshot(**changes)}


@pytest.fixture
def storage(tmp_path, monkeypatch):
    path = tmp_path / "orders.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))
    return path


def stored(path):
    return json.loads(path.read_text(encoding="utf-8"))


# Schemas

def test_order_keeps_the_snapshot_as_stored():
    assert Order.model_validate(order()).model_dump() == order()


def test_totals_are_stored_snapshots_and_must_be_consistent():
    assert Order.model_validate(order()).total == 24.46
    for changes in (
        {"items": [{**BIG_MAC, "line_total": 20.96}]},
        {"subtotal": 24.47},
        {"total": 24.47},
    ):
        with pytest.raises(ValidationError):
            Order.model_validate({**order(), **changes})


def test_line_totals_round_to_cents():
    item = {"product_id": 3, "name": "Tea", "unit_price": 0.1, "quantity": 3, "line_total": 0.3}
    assert Order.model_validate(order(items=[item])).subtotal == 0.3


@pytest.mark.parametrize("changes", [
    {"items": []},
    {"items": [BIG_MAC, BIG_MAC]},
    {"items": [{**BIG_MAC, "quantity": 0}]},
    {"items": [{**BIG_MAC, "quantity": 1.0}]},
    {"items": [{**BIG_MAC, "quantity": "3"}]},
    {"items": [{**BIG_MAC, "unit_price": 0}]},
    {"items": [{**BIG_MAC, "name": " "}]},
    {"items": [{**BIG_MAC, "extra": 1}]},
    {"status": "delivered"},
    {"status": None},
    {"restaurant_id": 0},
    {"customer_id": "1"},
    {"delivery_address": {**ADDRESS, "city": ""}},
    {"delivery_address": {**ADDRESS, "country": "CA"}},
    {"unknown": True},
])
def test_invalid_orders_are_rejected(changes):
    with pytest.raises(ValidationError):
        Order.model_validate({**order(), **changes}, strict=True)


@pytest.mark.parametrize("created_at", [
    "2026-11-04T18:30:00", "2026-11-04T18:30:00+02:00", "2026-11-04 18:30:00Z",
    "2026-13-04T18:30:00Z", "yesterday", "", 1730745000,
])
def test_created_at_must_be_a_utc_iso_timestamp(created_at):
    with pytest.raises(ValidationError):
        Order.model_validate(order(created_at=created_at))


def test_created_at_accepts_fractional_seconds():
    assert Order.model_validate(order(created_at="2026-11-04T18:30:00.123456Z")).created_at == (
        "2026-11-04T18:30:00.123456Z")


def test_utc_timestamp_formats_aware_times_in_utc():
    local = datetime(2026, 11, 4, 10, 30, tzinfo=timezone(timedelta(hours=-8)))
    assert utc_timestamp(local) == CREATED_AT
    assert Order.model_validate(order(created_at=utc_timestamp())).created_at.endswith("Z")
    with pytest.raises(ValueError):
        utc_timestamp(datetime(2026, 11, 4, 18, 30))


# Repository

def test_create_allocates_ids_from_storage_and_preserves_records(storage):
    existing = {**order(order_id=5, customer_id=9), "metadata": {"source": "seed"}}
    storage.write_text(json.dumps([existing]), encoding="utf-8")

    created = order_repo.create(snapshot(customer_id=2))

    assert created == order(order_id=6, customer_id=2)
    assert stored(storage) == [existing, created]
    assert order_repo.create(snapshot())["order_id"] == 7


def test_create_normalizes_text_and_rejects_invalid_snapshots(storage):
    created = order_repo.create(snapshot(items=[{**FRIES, "name": " Fries "}]))
    assert created["items"][0]["name"] == "Fries"
    before = storage.read_bytes()
    for fields in (snapshot(items=[]), {**snapshot(), "order_id": 99}, snapshot(status="cancelled")):
        with pytest.raises(ValueError):
            order_repo.create(fields)
    assert storage.read_bytes() == before


def test_lookup_by_order_and_customer(storage):
    first = order_repo.create(snapshot(customer_id=1))
    other = order_repo.create(snapshot(customer_id=2))
    second = order_repo.create(snapshot(customer_id=1, items=[FRIES]))

    assert order_repo.get_by_id(other["order_id"]) == other
    assert order_repo.get_by_id(99) is None
    assert order_repo.list_by_customer(1) == [first, second]
    assert order_repo.list_by_customer(3) == []
    assert order_repo.list_all() == [first, other, second]


def test_order_ids_survive_a_fresh_process(storage):
    order_repo.create(snapshot())
    script = (
        "from app.repositories import order_repo\n"
        "from tests.test_order_repo import snapshot\n"
        "print(order_repo.create(snapshot(customer_id=7))['order_id'])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(storage.parent)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    assert result.stdout.strip() == "2"
    assert [record["order_id"] for record in stored(storage)] == [1, 2]


def test_concurrent_creates_get_unique_ids(storage):
    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda customer: order_repo.create(snapshot(customer_id=customer)),
                                range(1, 21)))
    assert sorted(record["order_id"] for record in created) == list(range(1, 21))
    assert len(stored(storage)) == 20


@pytest.mark.parametrize("content", [
    "{ not json",
    "{}",
    json.dumps([{"order_id": 1}]),
    json.dumps([order(order_id=0)]),
    json.dumps([order(order_id="1")]),
    json.dumps([order(order_id=True)]),
    json.dumps([order(customer_id=0)]),
    json.dumps([order(items=[])]),
    json.dumps([{**order(), "total": 1.0}]),
    json.dumps([order(status="lost")]),
    json.dumps([order(created_at="2026-11-04T18:30:00")]),
    "[" + json.dumps(order()).replace("6.99", "NaN") + "]",
    json.dumps([order(), order()]),
])
def test_malformed_storage_is_rejected_without_overwriting(storage, content):
    storage.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        order_repo.list_all()
    with pytest.raises(ValueError):
        order_repo.list_by_customer(1)
    with pytest.raises(ValueError):
        order_repo.create(snapshot())

    assert storage.read_text(encoding="utf-8") == content


def test_missing_storage_is_not_created(storage):
    storage.unlink()

    with pytest.raises(FileNotFoundError):
        order_repo.create(snapshot())
    assert not storage.exists()


def test_representative_orders_file_is_an_empty_valid_store():
    path = Path(__file__).resolve().parents[1] / "data" / "orders.json"
    assert json.loads(path.read_text(encoding="utf-8")) == []
