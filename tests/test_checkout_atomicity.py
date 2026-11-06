"""An order and consumption of its cart have one durable commit point."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest

from app.repositories import cart_repo, json_store, order_repo
from app.schemas.cart import CartItemUpdate
from app.services import cart_service, checkout_service
from tests.test_checkout import accounts, add, cart_of, storage  # noqa: F401
from tests.test_checkout_integrity import ContentionSignal, wait_until_blocked_or_done


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_order_storage_outage_never_needs_a_cart_rollback(accounts, data_dir, monkeypatch, operation):
    """A persistent I/O outage beginning at order save must not lose the cart."""
    before = storage(data_dir)
    create = order_repo.create

    def fail_write(*args):
        raise OSError("persistent storage outage")

    def save_during_outage(fields):
        monkeypatch.setattr(json_store.os, operation, fail_write)
        return create(fields)

    monkeypatch.setattr(order_repo, "create", save_during_outage)
    with pytest.raises(OSError, match="persistent storage outage"):
        checkout_service.checkout(accounts["ada"]["id"])
    assert storage(data_dir) == before


def test_order_consumes_cart_even_when_cart_file_cannot_be_replaced(accounts, data_dir, monkeypatch):
    """Persisted consumption, rather than a second file write, prevents repurchase."""
    ada = accounts["ada"]
    carts_before = (data_dir / "carts.json").read_bytes()
    replace = json_store.os.replace

    def fail_cart_replace(source, destination):
        if Path(destination).name == "carts.json":
            raise OSError("cart file cannot be replaced")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(json_store.os, "replace", fail_cart_replace)
        order = checkout_service.checkout(ada["id"])
        assert [item.quantity for item in order.items] == [2, 3]
        assert cart_of(ada)["items"] == []
        with pytest.raises(checkout_service.EmptyCartError):
            checkout_service.checkout(ada["id"])
    assert (data_dir / "carts.json").read_bytes() == carts_before

    script = """
import json, sys
from app.repositories import cart_repo, order_repo
from app.services import checkout_service
customer_id = int(sys.argv[1])
try:
    checkout_service.checkout(customer_id)
except checkout_service.EmptyCartError:
    pass
else:
    raise AssertionError('purchased cart was orderable after restart')
print(json.dumps([cart_repo.get_by_customer_id(customer_id), len(order_repo.list_all())]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(ada["id"])],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "FOOD_DELIVERY_DATA_DIR": str(data_dir)},
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
    )
    cart, count = json.loads(result.stdout)
    assert cart["items"] == [] and count == 1

    # A new add is independent of the consumed generation, even for the same item.
    add(ada["id"], 1, 1)
    next_order = checkout_service.checkout(ada["id"])
    assert [(item.product_id, item.quantity) for item in next_order.items] == [(1, 1)]
    assert cart_of(ada)["items"] == []
    assert len(order_repo.list_all()) == 2


@pytest.mark.parametrize("mutation,expected", [
    ("add", {1: 3, 2: 3}), ("set", {1: 5, 2: 3}), ("remove", {2: 3}), ("clear", {}),
])
def test_queued_edits_apply_to_original_cart_after_failed_order(accounts, monkeypatch, mutation, expected):
    ada = accounts["ada"]
    original = cart_of(ada)
    paused, resume = Event(), Event()
    signal = ContentionSignal()

    def fail_order(fields):
        paused.set()
        assert resume.wait(timeout=5), "checkout was never resumed"
        raise OSError("order could not be saved")

    monkeypatch.setattr(order_repo, "create", fail_order)
    monkeypatch.setattr(cart_repo, "cart_lock", signal)
    edit = {
        "add": lambda: add(ada["id"], 1, 1),
        "set": lambda: cart_service.update_item(ada["id"], 1, CartItemUpdate(quantity=5)),
        "remove": lambda: cart_service.remove_item(ada["id"], 1),
        "clear": lambda: cart_service.clear_cart(ada["id"]),
    }[mutation]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(checkout_service.checkout, ada["id"])
        try:
            assert paused.wait(timeout=5), "checkout did not reach order save"
            assert cart_of(ada) == original  # no transient empty cart before commit
            edited = pool.submit(edit)
            wait_until_blocked_or_done(signal, edited)
            assert not edited.done()
        finally:
            resume.set()
        with pytest.raises(OSError, match="order could not be saved"):
            first.result(timeout=5)
        edited.result(timeout=5)
    assert {item["product_id"]: item["quantity"] for item in cart_of(ada)["items"]} == expected
    assert order_repo.list_all() == []


@pytest.mark.parametrize("generation", [-1, True, "0"])
def test_invalid_cart_generation_blocks_checkout_without_writes(accounts, data_dir, generation):
    path = data_dir / "carts.json"
    carts = json.loads(path.read_text(encoding="utf-8"))
    carts[0]["checkout_generation"] = generation
    path.write_text(json.dumps(carts), encoding="utf-8")
    before = storage(data_dir)
    with pytest.raises(ValueError):
        checkout_service.checkout(accounts["ada"]["id"])
    assert storage(data_dir) == before


@pytest.mark.parametrize("receipt", [
    {"cart_id": 1, "generation": True}, {"cart_id": 1, "generation": -1},
    {"cart_id": 0, "generation": 0}, {"cart_id": 1},
])
def test_invalid_consumption_receipt_fails_closed(accounts, data_dir, receipt):
    ada = accounts["ada"]
    checkout_service.checkout(ada["id"])
    path = data_dir / "orders.json"
    orders = json.loads(path.read_text(encoding="utf-8"))
    orders[0]["cart_consumption"] = receipt
    path.write_text(json.dumps(orders), encoding="utf-8")
    before = storage(data_dir)
    with pytest.raises(ValueError):
        cart_of(ada)
    with pytest.raises(ValueError):
        add(ada["id"], 1, 1)
    assert storage(data_dir) == before
