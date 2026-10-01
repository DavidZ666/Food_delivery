import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.repositories import json_store, restaurant_repo


def test_transaction_preserves_original_until_replace(data_dir, monkeypatch):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()
    replace = json_store.os.replace
    observed = []

    def inspect(source, destination):
        assert path.read_bytes() == original
        assert source.parent == path.parent
        observed.append(json.loads(source.read_text()))
        replace(source, destination)

    monkeypatch.setattr(json_store.os, "replace", inspect)
    result = json_store.update_json(path, lambda current: ([*current, {"id": 999}], 999))
    assert result == 999
    assert json.loads(path.read_text()) == observed[0]
    assert not list(data_dir.glob("*.tmp"))


@pytest.mark.parametrize("failure", ["serialize", "sync", "replace", "temporary"])
def test_failed_transaction_preserves_original_and_cleans_temp(data_dir, monkeypatch, failure):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("simulated storage failure")

    if failure == "sync":
        monkeypatch.setattr(json_store.os, "fsync", fail)
    elif failure == "replace":
        monkeypatch.setattr(json_store.os, "replace", fail)
    elif failure == "temporary":
        monkeypatch.setattr(json_store, "NamedTemporaryFile", fail)
    updated = {"value": object()} if failure == "serialize" else []
    with pytest.raises((OSError, TypeError)):
        json_store.update_json(path, lambda current: (updated, None))
    assert path.read_bytes() == original
    assert not list(data_dir.glob("*.tmp"))


def test_transform_failure_preserves_storage(data_dir):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()

    def fail(records):
        records.clear()
        raise ValueError("rejected")

    with pytest.raises(ValueError, match="rejected"):
        json_store.update_json(path, fail)
    assert path.read_bytes() == original


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_replacement_preserves_file_permissions(data_dir):
    path = data_dir / "restaurants.json"
    path.chmod(0o640)
    json_store.update_json(path, lambda records: (records, None))
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("identifier", [0, -1, True, "101", 101.0, 102])
def test_invalid_existing_ids_are_rejected(data_dir, identifier):
    path = data_dir / "restaurants.json"
    records = restaurant_repo.list_all()
    records[0]["id"] = identifier
    path.write_text(json.dumps(records))
    original = path.read_bytes()
    with pytest.raises(ValueError):
        restaurant_repo.create({key: value for key, value in records[1].items() if key != "id"})
    assert path.read_bytes() == original


def test_unsorted_sparse_ids_and_extra_fields_are_preserved(data_dir):
    path = data_dir / "restaurants.json"
    original = restaurant_repo.list_all()
    original[0]["id"] = 900
    original[0]["future_metadata"] = {"flag": True}
    path.write_text(json.dumps(original))
    created = restaurant_repo.create({key: value for key, value in original[1].items() if key != "id"})
    assert created["id"] == 901
    assert restaurant_repo.list_all() == [*original, created]


def test_invalid_new_record_does_not_write(data_dir):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()
    with pytest.raises(ValueError):
        restaurant_repo.create({"name": "Incomplete"})
    assert path.read_bytes() == original


def test_concurrent_creates_are_unique_and_preserve_records(data_dir):
    original = restaurant_repo.list_all()
    fields = {key: value for key, value in original[1].items() if key != "id"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda index: restaurant_repo.create(
            {**fields, "name": f"Restaurant {index}"}), range(24)))
    assert sorted(record["id"] for record in created) == list(range(103, 127))
    stored = restaurant_repo.list_all()
    assert stored[:2] == original
    assert len(stored) == 26
    assert {record["name"] for record in stored[2:]} == {
        f"Restaurant {index}" for index in range(24)}
    assert not list(data_dir.glob("*.tmp"))
