"""Checkout integrity: durable product identity and cart/checkout coordination (#120 review)."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from threading import Event, RLock

import pytest

from app.repositories import cart_repo, order_repo, product_repo
from app.schemas.cart import CartItemUpdate
from app.services import cart_service, checkout_service, menu_service
from tests.test_checkout import accounts, add, cart_of, checkout, http, storage  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]


def menu_item(name, price):
    return {"name": name, "description": "", "price": price, "category": "Main",
            "image": "", "is_available": True}


def create_in_fresh_process(data_dir, name="Beef Burger", price=25.0):
    script = """
import json, sys
from app.services import menu_service
print(json.dumps(menu_service.create_menu_item(101, json.loads(sys.argv[1]))))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(menu_item(name, price))], cwd=ROOT,
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    return json.loads(result.stdout)


# Product identity

def test_deleted_product_id_is_never_given_to_a_new_product(http, accounts, data_dir):
    empty = accounts["empty"]
    soup = menu_service.create_menu_item(101, menu_item("Vegetarian Soup", 5.0))
    add(empty["id"], soup["product_id"])
    menu_service.delete_menu_item(101, soup["product_id"])
    burger = menu_service.create_menu_item(101, menu_item("Beef Burger", 25.0))
    assert burger["product_id"] != soup["product_id"]

    before = storage(data_dir)
    response = checkout(http, empty)
    assert response.status_code == 409 and response.json() == {"detail": "Menu item is unavailable"}
    assert storage(data_dir) == before


@pytest.mark.parametrize("deleted", ["highest", "every"])
def test_product_ids_are_not_reused_after_deletion_and_restart(accounts, data_dir, deleted):
    products = product_repo.list_all()
    issued = [p["product_id"] for p in products]
    for product in products:
        if deleted == "every" or product["product_id"] == max(issued):
            menu_service.delete_menu_item(product["restaurant_id"], product["product_id"])
    created = create_in_fresh_process(data_dir)
    assert created["product_id"] > max(issued)
    again = create_in_fresh_process(data_dir, "Fries", 3.0)
    assert again["product_id"] > created["product_id"]


def test_name_and_price_updates_keep_identity_and_are_used_at_checkout(http, accounts):
    ada = accounts["ada"]
    menu_service.update_menu_item(101, 1, {"name": "Taco Supreme", "price": 5.25})
    response = checkout(http, ada)
    assert response.status_code == 201
    assert response.json()["items"][0] == {"product_id": 1, "name": "Taco Supreme",
                                           "unit_price": 5.25, "quantity": 2, "line_total": 10.5}


@pytest.mark.parametrize("content", ["{bad", "[]", '{"last_product_id": -1}',
                                     '{"last_product_id": true}', '{"last_product_id": 1.5}'])
def test_malformed_product_id_sequence_is_rejected_without_changes(accounts, data_dir, content):
    sequence = data_dir / "product_ids.json"
    sequence.write_text(content, encoding="utf-8")
    before = (data_dir / "products.json").read_bytes()
    with pytest.raises(ValueError):
        menu_service.create_menu_item(101, menu_item("Soup", 5.0))
    with pytest.raises(ValueError):
        menu_service.delete_menu_item(101, 1)
    assert (data_dir / "products.json").read_bytes() == before
    assert sequence.read_text(encoding="utf-8") == content


# Cart mutations overlapping checkout

class ContentionSignal:
    """The per-cart lock, signalling when another thread has to wait for it."""

    def __init__(self):
        self.lock = RLock()
        self.contended = Event()

    def __call__(self, customer_id):
        return self

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            self.contended.set()
            self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


@pytest.fixture
def paused_checkout(monkeypatch):
    """Pause the first order save; release with resume.set()."""
    paused, resume = Event(), Event()
    create = order_repo.create
    calls = []

    def pause_then_save(fields):
        calls.append(fields)
        if len(calls) == 1:
            paused.set()
            assert resume.wait(timeout=5), "checkout was never resumed"
        return create(fields)

    monkeypatch.setattr(order_repo, "create", pause_then_save)
    signal = ContentionSignal()
    monkeypatch.setattr(cart_repo, "cart_lock", signal, raising=False)
    return paused, resume, signal


def wait_until_blocked_or_done(signal, future):
    """Return once the concurrent mutation has finished or is waiting for the cart lock."""
    future.add_done_callback(lambda _: signal.contended.set())
    assert signal.contended.wait(timeout=5), "cart mutation neither finished nor waited for the cart"


def try_checkout(customer_id):
    try:
        return checkout_service.checkout(customer_id)
    except checkout_service.EmptyCartError:
        return None


def test_add_and_queued_checkout_during_checkout_never_buy_units_twice(accounts, paused_checkout):
    ada = accounts["ada"]
    paused, resume, signal = paused_checkout
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(checkout_service.checkout, ada["id"])
        assert paused.wait(timeout=5), "checkout did not reach the order save"
        added = pool.submit(add, ada["id"], 1, 1)
        wait_until_blocked_or_done(signal, added)
        second = pool.submit(try_checkout, ada["id"])
        resume.set()
        orders = [first.result(timeout=5), second.result(timeout=5)]
        added.result(timeout=5)

    assert [(i.product_id, i.quantity) for i in orders[0].items] == [(1, 2), (2, 3)]
    ordered = {1: 0, 2: 0}
    for order in filter(None, orders):
        for item in order.items:
            ordered[item.product_id] += item.quantity
    remaining = {item["product_id"]: item["quantity"] for item in cart_of(ada)["items"]}
    # 2 + 1 tacos and 3 mints were ever added; each unit is bought at most once and none is lost.
    assert ordered[1] + remaining.get(1, 0) == 3
    assert ordered[2] + remaining.get(2, 0) == 3
    assert len(order_repo.list_all()) == len(list(filter(None, orders)))


@pytest.mark.parametrize("mutation", ["set_quantity", "remove", "clear"])
def test_edits_during_checkout_apply_to_the_consumed_cart(accounts, paused_checkout, mutation):
    ada = accounts["ada"]
    paused, resume, signal = paused_checkout
    edit = {
        "set_quantity": lambda: cart_service.update_item(ada["id"], 2, CartItemUpdate(quantity=5)),
        "remove": lambda: cart_service.remove_item(ada["id"], 1),
        "clear": lambda: cart_service.clear_cart(ada["id"]),
    }[mutation]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(checkout_service.checkout, ada["id"])
        assert paused.wait(timeout=5), "checkout did not reach the order save"
        edited = pool.submit(edit)
        wait_until_blocked_or_done(signal, edited)
        resume.set()
        order = first.result(timeout=5)
        if mutation == "clear":
            assert edited.result(timeout=5).items == []
        else:
            # The edit runs after the purchase and reports that the item is gone.
            with pytest.raises(cart_service.CartItemNotFoundError):
                edited.result(timeout=5)

    assert [(i.product_id, i.quantity) for i in order.items] == [(1, 2), (2, 3)]
    assert cart_of(ada)["items"] == []
    with pytest.raises(checkout_service.EmptyCartError):
        checkout_service.checkout(ada["id"])
    assert len(order_repo.list_all()) == 1
