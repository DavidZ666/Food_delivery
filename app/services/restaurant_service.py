from app.repositories import restaurant_repo


def list_restaurants():
    return restaurant_repo.list_all()