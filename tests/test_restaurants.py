import json


def test_restaurant_and_menu(tmp_path):
    restaurants = [
        {"restaurant_id": 1, "brand_name": "Test Restaurant"},
        {"restaurant_id": 2, "brand_name": "Other Restaurant"},
    ]
    products = [
        {"product_id": 1, "restaurant_id": 1, "name": "Burger"},
        {"product_id": 2, "restaurant_id": 2, "name": "Noodles"},
    ]

    restaurant_file = tmp_path / "restaurants_info.json"
    product_file = tmp_path / "products.json"

    restaurant_file.write_text(
        json.dumps(restaurants), encoding="utf-8"
    )
    product_file.write_text(
        json.dumps(products), encoding="utf-8"
    )

    restaurants = json.loads(
        restaurant_file.read_text(encoding="utf-8")
    )
    products = json.loads(
        product_file.read_text(encoding="utf-8")
    )

    restaurant = restaurants[0]
    restaurant_products = [
        item
        for item in products
        if item["restaurant_id"] == restaurant["restaurant_id"]
    ]

    assert restaurant["brand_name"] == "Test Restaurant"
    assert len(restaurant_products) == 1
    assert restaurant_products[0]["name"] == "Burger"