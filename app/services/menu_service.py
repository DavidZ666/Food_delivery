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

def create_menu_item(restaurant_id: int, data: dict):
    list_menu(restaurant_id)
    products = product_repo.list_all()
    next_id = max((p["product_id"] for p in products), default=0) + 1
    item = {"product_id": next_id, "restaurant_id": restaurant_id, **data}
    products.append(item)
    product_repo.save_all(products)
    return item


def update_menu_item(restaurant_id: int, product_id: int, changes: dict):
    list_menu(restaurant_id)
    products = product_repo.list_all()
    for product in products:
        if product["product_id"] == product_id and product["restaurant_id"] == restaurant_id:
            product.update(changes)
            product_repo.save_all(products)
            return product
    raise MenuItemNotFound


def delete_menu_item(restaurant_id: int, product_id: int):
    list_menu(restaurant_id)
    products = product_repo.list_all()
    remaining = [
        p for p in products
        if not (p["product_id"] == product_id and p["restaurant_id"] == restaurant_id)
    ]
    if len(remaining) == len(products):
        raise MenuItemNotFound
    product_repo.save_all(remaining)