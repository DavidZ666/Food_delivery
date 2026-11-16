"""Preserve product identities referenced by pre-sequence carts and orders."""
import json

import pytest

from app.repositories import product_repo
from app.services import checkout_service


FIELDS = {"name": "Replacement soup", "description": "", "price": 99.0,
          "category": "Main", "image": "", "is_available": True}


def write_json(data_dir, name, document):
    (data_dir / name).write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("source", ["carts.json", "orders.json"])
def test_bootstrap_preserves_deleted_product_references(data_dir, source):
    # Legacy deletion left a cart/order reference above the surviving menu maximum.
    write_json(data_dir, "products.json", [{**FIELDS, "name": "Original", "product_id": 1,
                                            "restaurant_id": 101}])
    line = {"product_id": 2, "name": "Deleted burger", "unit_price": 7.25,
            "quantity": 1, "line_total": 7.25}
    write_json(data_dir, source, [{"restaurant_id": 101, "items": [line]}])

    created = product_repo.create(101, FIELDS)

    assert created["product_id"] > 2
    with pytest.raises(checkout_service.MenuItemUnavailableError):
        checkout_service._current_item(101, line)


def test_bootstrap_allows_absent_legacy_cart_and_order_files(data_dir):
    write_json(data_dir, "products.json", [])
    assert product_repo.create(101, FIELDS)["product_id"] == 1


def test_deletion_bootstraps_sequence_from_legacy_references(data_dir):
    write_json(data_dir, "products.json", [{**FIELDS, "product_id": 1, "restaurant_id": 101}])
    write_json(data_dir, "carts.json", [{"items": [{"product_id": 8}]}])

    product_repo.delete_by_id(101, 1)

    assert json.loads((data_dir / "product_ids.json").read_text(encoding="utf-8")) == {
        "last_product_id": 8}
    assert product_repo.create(101, FIELDS)["product_id"] == 9


@pytest.mark.parametrize("source", ["carts.json", "orders.json"])
@pytest.mark.parametrize("document", [
    {}, [None], [{}], [{"items": {}}], [{"items": [None]}],
    [{"items": [{}]}], [{"items": [{"product_id": True}]}],
    [{"items": [{"product_id": 0}]}], [{"items": [{"product_id": -1}]}],
    [{"items": [{"product_id": "2"}]}], [{"items": [{"product_id": 2.5}]}],
])
def test_corrupt_legacy_references_cannot_initialize_sequence(data_dir, source, document):
    write_json(data_dir, "products.json", [])
    write_json(data_dir, source, document)
    before = {path.name: path.read_bytes() for path in data_dir.iterdir()}

    with pytest.raises(ValueError):
        product_repo.create(101, FIELDS)

    assert {path.name: path.read_bytes() for path in data_dir.iterdir()} == before


@pytest.mark.parametrize("source", ["carts.json", "orders.json"])
def test_invalid_json_history_cannot_initialize_sequence(data_dir, source):
    write_json(data_dir, "products.json", [])
    (data_dir / source).write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        product_repo.create(101, FIELDS)
    assert (data_dir / "products.json").read_text(encoding="utf-8") == "[]"
    assert not (data_dir / "product_ids.json").exists()


def test_existing_sequence_does_not_depend_on_historical_files(data_dir):
    write_json(data_dir, "products.json", [])
    write_json(data_dir, "product_ids.json", {"last_product_id": 8})
    write_json(data_dir, "orders.json", {"unrelated": "invalid history"})
    assert product_repo.create(101, FIELDS)["product_id"] == 9
