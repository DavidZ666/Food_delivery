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
         "image": "https://example.com/taco.png", "is_available": False},
        {"product_id": 3, "restaurant_id": 102, "name": "Fries",
         "description": "Golden fries", "price": 2.0, "category": "Sides",
         "image": "https://example.com/fries.png", "is_available": True},
        {"product_id": 5, "restaurant_id": 101, "name": "Salsa",
         "description": "Fresh salsa", "price": 1.0, "category": "Sides",
         "image": "https://example.com/salsa.png", "is_available": True},
    ]
    (data_dir / "products.json").write_text(json.dumps(products), encoding="utf-8")
    return products


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
