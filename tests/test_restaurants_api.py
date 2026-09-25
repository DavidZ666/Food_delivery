def test_restaurants_returns_200(client):
    response = client.get("/restaurants")
    
    assert response.status_code == 200


def test_health_returns_sample_data(client):
    response = client.get("/restaurants")

    assert response.json() == [
        {"id": "t1", "name": "Test Tacos", "cuisine": "Mexican"},
        {"id": "t2", "name": "Test Thai", "cuisine": "Thai"}
    ]


def test_restaurants_have_required_fields(client):
    response = client.get("/restaurants")

    for restaurant in response.json():
        assert set(restaurant.keys()) == {"id", "name", "cuisine"}