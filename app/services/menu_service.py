from app.repositories import product_repo, restaurant_repo


class RestaurantNotFound(Exception):
    pass


class MenuItemNotFound(Exception):
    pass


def _validate_restaurant(restaurant_id: int):
    restaurant = restaurant_repo.get_by_id(restaurant_id)
    if restaurant is None:
        raise RestaurantNotFound
    return restaurant


def list_menu(restaurant_id: int):
    _validate_restaurant(restaurant_id)
    return [
        product for product in product_repo.list_all()
        if product["restaurant_id"] == restaurant_id
    ]


def get_menu_item(restaurant_id: int, product_id: int):
    for product in list_menu(restaurant_id):
        if product["product_id"] == product_id:
            return product
    raise MenuItemNotFound

def create_menu_item(restaurant_id: int, data: dict):
    _validate_restaurant(restaurant_id)
    return product_repo.create(restaurant_id, data)


def update_menu_item(restaurant_id: int, product_id: int, changes: dict):
    _validate_restaurant(restaurant_id)

    try:
        return product_repo.update_by_id(restaurant_id, product_id, changes)
    except product_repo.ProductRecordNotFoundError:
        raise MenuItemNotFound from None


def delete_menu_item(restaurant_id: int, product_id: int):
    _validate_restaurant(restaurant_id)

    try:
        product_repo.delete_by_id(restaurant_id, product_id)
    except product_repo.ProductRecordNotFoundError:
        raise MenuItemNotFound from None
