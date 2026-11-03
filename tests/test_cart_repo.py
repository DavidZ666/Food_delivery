import json

import pytest
from pydantic import ValidationError

from app.repositories import cart_repo
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartRead


ITEM = {"product_id": 1, "name": "Big Mac", "unit_price": 6.99, "quantity": 3}
FRIES = {"product_id": 2, "name": "Fries", "unit_price": 3.49, "quantity": 1}


def cart(cart_id=1, customer_id=1, restaurant_id=None, items=()):
    return {"cart_id": cart_id, "customer_id": customer_id,
            "restaurant_id": restaurant_id, "items": list(items)}


@pytest.fixture
def storage(tmp_path, monkeypatch):
    path = tmp_path / "carts.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("FOOD_DELIVERY_DATA_DIR", str(tmp_path))
    return path


def stored(path):
    return json.loads(path.read_text(encoding="utf-8"))


# Schemas

def test_read_model_calculates_line_totals_subtotal_and_total():
    read = CartRead.model_validate(cart(restaurant_id=1, items=[ITEM, FRIES]))

    assert read.model_dump() == {
        **cart(restaurant_id=1),
        "items": [{**ITEM, "line_total": 20.97}, {**FRIES, "line_total": 3.49}],
        "subtotal": 24.46, "total": 24.46,
    }


def test_empty_cart_totals_are_zero():
    read = CartRead.model_validate(cart())

    assert (read.items, read.subtotal, read.total) == ([], 0, 0)


@pytest.mark.parametrize("quantity", [0, -1, 1.5, 2.0, "2", True, None])
def test_quantities_must_be_positive_integers(quantity):
    with pytest.raises(ValidationError):
        CartItemAdd.model_validate({"product_id": 1, "quantity": quantity})
    with pytest.raises(ValidationError):
        CartItemUpdate.model_validate({"quantity": quantity})
    with pytest.raises(ValidationError):
        CartRead.model_validate(cart(restaurant_id=1, items=[{**ITEM, "quantity": quantity}]))


def test_add_request_defaults_quantity_and_rejects_client_prices():
    assert CartItemAdd.model_validate({"product_id": 1}).quantity == 1
    for body in ({"product_id": 1, "unit_price": 0.01}, {"product_id": 0}, {}):
        with pytest.raises(ValidationError):
            CartItemAdd.model_validate(body)


@pytest.mark.parametrize("record", [
    cart(restaurant_id=1),
    cart(items=[ITEM]),
    cart(restaurant_id=1, items=[ITEM, {**ITEM, "quantity": 1}]),
    cart(restaurant_id=1, items=[{**ITEM, "unit_price": 0}]),
    cart(restaurant_id=1, items=[{**ITEM, "name": " "}]),
])
def test_cart_rejects_inconsistent_items(record):
    with pytest.raises(ValidationError):
        CartRead.model_validate(record)


# Repository

def test_create_allocates_ids_from_storage_and_preserves_records(storage):
    existing = {**cart(cart_id=5, customer_id=9), "metadata": {"source": "seed"}}
    storage.write_text(json.dumps([existing]), encoding="utf-8")

    created = cart_repo.create(2)

    assert created == cart(cart_id=6, customer_id=2)
    assert stored(storage) == [existing, created]
    assert cart_repo.create(3)["cart_id"] == 7


def test_lookup_by_cart_and_customer(storage):
    created = cart_repo.create(4)

    assert cart_repo.get_by_id(created["cart_id"]) == created
    assert cart_repo.get_by_customer_id(4) == created
    assert cart_repo.get_by_id(99) is None
    assert cart_repo.get_by_customer_id(99) is None


def test_create_rejects_second_cart_for_customer(storage):
    cart_repo.create(1)
    before = storage.read_bytes()

    with pytest.raises(cart_repo.ActiveCartExistsError):
        cart_repo.create(1)
    assert storage.read_bytes() == before


def test_update_replaces_items_and_restaurant(storage):
    created = cart_repo.create(1)

    updated = cart_repo.update_by_id(
        created["cart_id"], {"restaurant_id": 1, "items": [{**ITEM, "name": " Big Mac "}]},
    )

    assert updated == {**created, "restaurant_id": 1, "items": [ITEM]}
    assert stored(storage) == [updated]
    cleared = cart_repo.update_by_id(1, {"restaurant_id": None, "items": []})
    assert cleared == created


def test_update_preserves_metadata(storage):
    existing = {**cart(), "metadata": {"source": "seed"}}
    storage.write_text(json.dumps([existing]), encoding="utf-8")

    updated = cart_repo.update_by_id(1, {"restaurant_id": 1, "items": [ITEM]})

    assert updated == {**existing, "restaurant_id": 1, "items": [ITEM]}
    assert stored(storage) == [updated]


@pytest.mark.parametrize("cart_id,changes,error", [
    (99, {"items": []}, cart_repo.CartNotFoundError),
    (1, {}, ValueError),
    (1, {"customer_id": 2}, ValueError),
    (1, {"cart_id": 2}, ValueError),
    (1, {"items": [ITEM]}, ValueError),
    (1, {"restaurant_id": 1, "items": [{**ITEM, "quantity": 0}]}, ValueError),
])
def test_rejected_updates_leave_storage_unchanged(storage, cart_id, changes, error):
    cart_repo.create(1)
    before = storage.read_bytes()

    with pytest.raises(error):
        cart_repo.update_by_id(cart_id, changes)
    assert storage.read_bytes() == before


@pytest.mark.parametrize("content", [
    "{ not json",
    "{}",
    json.dumps([{"cart_id": 1}]),
    json.dumps([cart(cart_id=0)]),
    json.dumps([cart(cart_id="1")]),
    json.dumps([cart(cart_id=True)]),
    json.dumps([cart(customer_id=0)]),
    json.dumps([cart(restaurant_id=1, items=[{**ITEM, "quantity": 0}])]),
    json.dumps([cart(restaurant_id=1, items=[{**ITEM, "quantity": 1.0}])]),
    json.dumps([cart(restaurant_id=1, items=[{**ITEM, "unit_price": -1}])]),
    "[" + json.dumps(cart(restaurant_id=1, items=[ITEM])).replace("6.99", "NaN") + "]",
    json.dumps([cart(restaurant_id=1)]),
    json.dumps([cart(), cart(customer_id=2)]),
    json.dumps([cart(), cart(cart_id=2)]),
])
def test_malformed_storage_is_rejected_without_overwriting(storage, content):
    storage.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        cart_repo.list_all()
    with pytest.raises(ValueError):
        cart_repo.create(3)
    with pytest.raises(ValueError):
        cart_repo.update_by_id(1, {"items": []})

    assert storage.read_text(encoding="utf-8") == content


def test_missing_storage_is_not_created(storage):
    storage.unlink()

    with pytest.raises(FileNotFoundError):
        cart_repo.create(1)
    assert not storage.exists()
