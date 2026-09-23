import json

def test_restaurant_and_menu():
    with open("data/restaurants_info.json") as f:
        restaurants = json.load(f)

    with open("data/products.json") as f:
        products = json.load(f)

    restaurant = restaurants[0]

    restaurant_products = [
        item
        for item in products
        if item["restaurant_id"] == restaurant["restaurant_id"]
    ]
    assert restaurant["brand_name"] == "McDonalds"
    assert len(restaurant_products) > 0

###Run "pytest -v tests/test_restaurants.py" to see the test results, which all passed for me confirming that data is loading correctly.