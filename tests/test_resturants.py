import json

def test_restaurant_and_menu():
    with open("data/restaurants.json") as f:
        restaurants = json.load(f)

    with open("data/menu.json") as f:
        menu = json.load(f)

    restaurant = restaurants[0]

    restaurant_menu = [
        item
        for item in menu
        if item["restaurant_id"] == restaurant["restaurant_id"]
    ]
    assert restaurant["brand_name"] == "McDonalds"
    assert len(restaurant_menu) > 0

###Run "pytest -v tests/test_resturants.py to see the test results, which all passed for me confirming that data is loading correctly.