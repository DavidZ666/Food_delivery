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
    if restaurant_repo.get_by_id(restaurant_id) is None:
        raise RestaurantNotFound
    return product_repo.create(restaurant_id, data)


def update_menu_item(restaurant_id: int, product_id: int, changes: dict):
    if restaurant_repo.get_by_id(restaurant_id) is None:
        raise RestaurantNotFound
    try:
        return product_repo.update_by_id(restaurant_id, product_id, changes)
    except product_repo.ProductRecordNotFoundError:
        raise MenuItemNotFound from None


def delete_menu_item(restaurant_id: int, product_id: int):
    if restaurant_repo.get_by_id(restaurant_id) is None:
        raise RestaurantNotFound
    try:
        product_repo.delete_by_id(restaurant_id, product_id)
    except product_repo.ProductRecordNotFoundError:
        raise MenuItemNotFound from None
