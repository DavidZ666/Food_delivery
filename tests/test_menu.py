import json

import pytest
from fastapi.exceptions import ResponseValidationError

from app.repositories import product_repo
from app.services import menu_service


@pytest.fixture
def menu_data(data_dir):
    products = [
        {"product_id": 8, "restaurant_id": 101, "name": "Taco",
         "description": "Bean taco", "price": 4.5, "category": "Main",
         "image": "", "is_available": False},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "", "is_available": True},
        {"product_id": 5, "restaurant_id": 101, "name": "Salsa",
         "description": "Fresh salsa", "price": 1.0, "category": "Sides",
         "image": "", "is_available": True},
    ]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    return products

NEW_ITEM = {
    "name": "Nachos", "description": "Cheesy nachos", "price": 5.25, "category": "Snacks",
    "image": "", "is_available": True,}

def read_products(data_dir):
    return json.loads((data_dir / "products.json").read_text(encoding="utf-8"))

def test_repository_reads_configured_products(menu_data):
    assert product_repo.list_all() == menu_data


def test_service_filters_menu_and_enforces_ownership(menu_data):
    assert menu_service.list_menu(101) == [menu_data[0], menu_data[2]]
    assert menu_service.get_menu_item(102, 3) == menu_data[1]
    with pytest.raises(menu_service.MenuItemNotFound):
        menu_service.get_menu_item(101, 3)
    with pytest.raises(menu_service.RestaurantNotFound):
        menu_service.list_menu(999)


def test_menu_preserves_order_fields_and_availability(client, menu_data):
    response = client.get("/restaurants/101/menu")
    assert response.status_code == 200
    assert response.json() == [menu_data[0], menu_data[2]]
    item = client.get("/restaurants/101/menu/8")
    assert item.status_code == 200
    assert item.json() == menu_data[0]


@pytest.mark.parametrize("products", [[], [{"product_id": 1, "restaurant_id": 102}]])
def test_existing_restaurant_empty_menu(client, data_dir, products):
    (data_dir / "products.json").write_text(json.dumps(products))
    response = client.get("/restaurants/101/menu")
    assert response.status_code == 200
    assert response.json() == []
    assert client.get("/restaurants/101/menu/1").json() == {"detail": "Menu item not found"}


@pytest.mark.parametrize("path,detail", [
    ("/restaurants/999/menu", "Restaurant not found"),
    ("/restaurants/999/menu/8", "Restaurant not found"),
    ("/restaurants/101/menu/999", "Menu item not found"),
    ("/restaurants/101/menu/3", "Menu item not found"),
])
def test_missing_resource(client, menu_data, path, detail):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("path", ["/restaurants/101/menu", "/restaurants/101/menu/8"])
def test_empty_restaurant_store_is_not_an_empty_menu(client, data_dir, path):
    (data_dir / "restaurants.json").write_text("[]")
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Restaurant not found"}


@pytest.mark.parametrize("path", [
    "/restaurants/invalid/menu", "/restaurants/invalid/menu/8",
    "/restaurants/101/menu/invalid",
])
def test_invalid_ids(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize("file_name", ["restaurants.json", "products.json"])
@pytest.mark.parametrize("failure", ["missing", "invalid_json"])
@pytest.mark.parametrize("path", ["/restaurants/101/menu", "/restaurants/101/menu/8"])
def test_storage_failures_propagate(client, data_dir, menu_data, file_name, failure, path):
    file_path = data_dir / file_name
    if failure == "missing":
        file_path.rename(data_dir / f"unavailable-{file_name}")
        error = FileNotFoundError
    else:
        file_path.write_text("{invalid")
        error = json.JSONDecodeError
    with pytest.raises(error):
        client.get(path)


@pytest.mark.parametrize("path", ["/restaurants/101/menu", "/restaurants/101/menu/8"])
def test_invalid_product_rejected_by_response_model(client, data_dir, path):
    (data_dir / "products.json").write_text(json.dumps([
        {"product_id": 8, "restaurant_id": 101, "name": "Incomplete"}
    ]))
    with pytest.raises(ResponseValidationError):
        client.get(path)


def test_reads_do_not_change_storage(client, data_dir, menu_data):
    files = [data_dir / name for name in ("restaurants.json", "products.json")]
    before = [path.read_bytes() for path in files]
    for path in ("/restaurants/101/menu", "/restaurants/101/menu/8",
                 "/restaurants/101/menu/3", "/restaurants/999/menu"):
        client.get(path)
    assert [path.read_bytes() for path in files] == before


#Create menu item tests

def test_create_menu_item(client, data_dir, menu_data):
    response = client.post("/restaurants/101/menu", json=NEW_ITEM)

    assert response.status_code == 201
    expected = {"product_id": 9, "restaurant_id": 101, **NEW_ITEM}
    assert response.json() == expected
    assert read_products(data_dir) == menu_data + [expected]

def test_created_item_is_visible_through_read_routes(client, menu_data):
    created = client.post("/restaurants/101/menu", json=NEW_ITEM).json()

    menu = client.get("/restaurants/101/menu").json()
    assert menu[-1] == created
    assert client.get(f"/restaurants/101/menu/{created['product_id']}").json() == created
    # The other restaurant's menu is untouched
    assert client.get("/restaurants/102/menu").json() == [menu_data[1]]

def test_create_in_empty_store_starts_at_id_1(client, data_dir):
    (data_dir / "products.json").write_text("[]")

    response = client.post("/restaurants/101/menu", json=NEW_ITEM)

    assert response.status_code == 201
    assert response.json()["product_id"] == 1

def test_create_assigns_unique_increasing_ids(client, menu_data):
    first = client.post("/restaurants/101/menu", json=NEW_ITEM).json()
    second = client.post("/restaurants/102/menu", json=NEW_ITEM).json()

    assert (first["product_id"], second["product_id"]) == (9, 10)

def test_create_ignores_client_supplied_ids(client, menu_data):
    body = {**NEW_ITEM, "product_id": 3, "restaurant_id": 102}

    response = client.post("/restaurants/101/menu", json=body)

    assert response.status_code == 201
    assert response.json()["product_id"] == 9
    assert response.json()["restaurant_id"] == 101

#Update menu item tests

def test_update_changes_only_sent_fields(client, data_dir, menu_data):
    response = client.patch("/restaurants/101/menu/8", json={"price": 7.49})

    assert response.status_code == 200
    expected = {**menu_data[0], "price": 7.49}
    assert response.json() == expected
    assert read_products(data_dir) == [expected, menu_data[1], menu_data[2]]

def test_update_multiple_fields(client, menu_data):
    changes = {"name": "Big Taco", "is_available": True, "category": "Specials"}

    response = client.patch("/restaurants/101/menu/8", json=changes)

    assert response.status_code == 200
    assert response.json() == {**menu_data[0], **changes}

def test_update_can_toggle_availability_off(client, menu_data):
    response = client.patch("/restaurants/101/menu/5", json={"is_available": False})

    assert response.status_code == 200
    assert response.json()["is_available"] is False

def test_update_with_empty_body_changes_nothing(client, data_dir, menu_data):
    response = client.patch("/restaurants/101/menu/8", json={})

    assert response.status_code == 200
    assert response.json() == menu_data[0]
    assert read_products(data_dir) == menu_data

def test_update_cannot_change_ids(client, data_dir, menu_data):
    response = client.patch(
        "/restaurants/101/menu/8", json={"product_id": 99, "restaurant_id": 102}
    )

    assert response.status_code == 200
    assert response.json()["product_id"] == 8
    assert response.json()["restaurant_id"] == 101
    assert read_products(data_dir) == menu_data

def test_update_does_not_touch_other_items(client, data_dir, menu_data):
    client.patch("/restaurants/101/menu/8", json={"name": "Renamed"})

    products = read_products(data_dir)
    assert products[1] == menu_data[1]
    assert products[2] == menu_data[2]

@pytest.mark.parametrize("changes", [
    {"price": 0},
    {"price": -3},
    {"name": ""},
    {"category": ""},
    {"is_available": "maybe"},
])
def test_update_rejects_invalid_fields(client, data_dir, menu_data, changes):
    before = (data_dir / "products.json").read_bytes()

    response = client.patch("/restaurants/101/menu/8", json=changes)

    assert response.status_code == 422
    assert (data_dir / "products.json").read_bytes() == before

#Delete menu item tests

def test_delete_menu_item(client, data_dir, menu_data):
    response = client.delete("/restaurants/101/menu/8")

    assert response.status_code == 204
    assert response.content == b""
    assert read_products(data_dir) == [menu_data[1], menu_data[2]]


def test_deleted_item_is_gone_from_read_routes(client, menu_data):
    client.delete("/restaurants/101/menu/8")

    assert client.get("/restaurants/101/menu").json() == [menu_data[2]]
    assert client.get("/restaurants/101/menu/8").status_code == 404


def test_delete_last_item_leaves_empty_menu(client, data_dir):
    (data_dir / "products.json").write_text(json.dumps([
        {"product_id": 1, "restaurant_id": 101, "name": "Only", "description": "",
         "price": 1.0, "category": "Main", "image": "", "is_available": True},
    ]))

    assert client.delete("/restaurants/101/menu/1").status_code == 204
    assert client.get("/restaurants/101/menu").json() == []


def test_delete_twice_returns_404_the_second_time(client, menu_data):
    assert client.delete("/restaurants/101/menu/8").status_code == 204

    response = client.delete("/restaurants/101/menu/8")

    assert response.status_code == 404
    assert response.json() == {"detail": "Menu item not found"}


@pytest.mark.parametrize("path,detail", [
    ("/restaurants/999/menu/8", "Restaurant not found"),
    ("/restaurants/101/menu/999", "Menu item not found"),
    ("/restaurants/101/menu/3", "Menu item not found"),  # belongs to restaurant 102
])
def test_delete_missing_resource(client, data_dir, menu_data, path, detail):
    before = (data_dir / "products.json").read_bytes()

    response = client.delete(path)

    assert response.status_code == 404
    assert response.json() == {"detail": detail}
    assert (data_dir / "products.json").read_bytes() == before

#OpenAPI contract tests

def test_openapi_contract(client):
    schema = client.get("/openapi.json").json()
    for path in ("/restaurants/{restaurant_id}/menu",
                 "/restaurants/{restaurant_id}/menu/{product_id}"):
        operation = schema["paths"][path]["get"]
        assert operation["summary"] and operation["description"]
        assert set(operation["responses"]) == {"200", "404", "422"}
        for parameter in operation["parameters"]:
            assert parameter["in"] == "path"
            assert parameter["required"]
            assert parameter["schema"]["type"] == "integer"
            assert parameter["description"]
        error = operation["responses"]["404"]["content"]["application/json"]["schema"]
        assert error["$ref"].endswith("/MenuError")
        result = operation["responses"]["200"]["content"]["application/json"]["schema"]
        if path.endswith("/menu"):
            assert result["type"] == "array"
            result = result["items"]
        assert result["$ref"].endswith("/MenuItemRead")
