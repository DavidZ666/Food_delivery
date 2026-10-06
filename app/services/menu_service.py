from app.repositories import product_repo, restaurant_repo


class RestaurantNotFound(Exception):
    pass


class MenuItemNotFound(Exception):
    pass


def list_menu(restaurant_id: int):
    restaurants = restaurant_repo.list_all()
    if not any(restaurant["id"] == restaurant_id for restaurant in restaurants):
        raise RestaurantNotFound
    return [product for product in product_repo.list_all()
            if product["restaurant_id"] == restaurant_id]


def get_menu_item(restaurant_id: int, product_id: int):
    for product in list_menu(restaurant_id):
        if product["product_id"] == product_id:
            return product
    raise MenuItemNotFound
