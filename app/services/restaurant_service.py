from app.repositories import restaurant_repo


def list_restaurants(name: str | None = None):
    restaurants = restaurant_repo.list_all()
    query = name.strip().casefold() if name is not None else ""
    if not query:
        return restaurants
    return [restaurant for restaurant in restaurants
            if query in restaurant["name"].casefold()]
