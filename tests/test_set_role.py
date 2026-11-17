"""Local command that grants management roles (#123)."""
import json

import pytest

from scripts.set_role import main
from tests.conftest import MANAGER

NEW_RESTAURANT = {
    "name": "Granted Grill", "cuisine": "BBQ",
    "location": {"address": "4 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V4"},
}
ACCOUNT = {
    "name": "Ada", "email": "ada@example.com", "password": "example-password", "phone": "250-555-0101",
    "delivery_address": {"address": "2 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V2"},
}


def stored(data_dir):
    return (data_dir / "customers.json").read_bytes()


@pytest.mark.parametrize("role", ["restaurant_owner", "admin"])
def test_granted_role_allows_management_writes_with_an_existing_token(anonymous_client, data_dir, capsys, role):
    assert anonymous_client.post("/customers", json=ACCOUNT).status_code == 201
    login = anonymous_client.post("/auth/login", json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert anonymous_client.post("/restaurants", json=NEW_RESTAURANT, headers=headers).status_code == 403

    before = json.loads(stored(data_dir))
    assert main([" ADA@example.com ", role]) == 0

    assert capsys.readouterr().out == f"ada@example.com is now {role}.\n"
    assert anonymous_client.post("/restaurants", json=NEW_RESTAURANT, headers=headers).status_code == 201
    assert json.loads(stored(data_dir)) == [before[0], {**before[1], "role": role}]


def test_role_can_be_returned_to_customer(data_dir):
    [manager] = json.loads(stored(data_dir))
    assert main([MANAGER["email"], "customer"]) == 0
    assert json.loads(stored(data_dir)) == [{**manager, "role": "customer"}]


def test_unknown_email_fails_without_changes(data_dir, capsys):
    before = stored(data_dir)
    assert main(["nobody@example.com", "admin"]) == 1
    assert capsys.readouterr().err == "No account is registered with nobody@example.com.\n"
    assert stored(data_dir) == before


def test_unknown_role_fails_without_changes(data_dir, capsys):
    before = stored(data_dir)
    with pytest.raises(SystemExit) as exit_info:
        main([MANAGER["email"], "superuser"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert stored(data_dir) == before
