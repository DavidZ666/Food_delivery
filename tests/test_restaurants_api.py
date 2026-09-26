import json
import pytest
from fastapi.exceptions import ResponseValidationError

def test_restaurants_returns_200(client):
    response = client.get("/restaurants")
    
    assert response.status_code == 200


def test_restaurants_returns_sample_data(client):
    restaurants = client.get("/restaurants").json()

    assert [r["id"] for r in restaurants] == [101, 102]
    assert restaurants[0]["name"] == "Testaurant"
    assert restaurants[0]["location"]["city"] == "Kelowna"
    assert restaurants[0]["hours"]["sunday"] is None


def test_missing_optional_gives_none(client):
    restaurant = client.get("/restaurants").json()[1]

    assert restaurant["description"] is None
    assert restaurant["logo_url"] is None
    assert restaurant["hours"] is None


def test_restaurants_have_expected_fields(client):
    for restaurant in client.get("/restaurants").json():
        assert set(restaurant.keys()) == {
            "id", "name", "cuisine", "location",
            "description", "logo_url", "hours",
        }
        

def test_rejects_if_missing_required_field(client, data_dir):
    (data_dir / "restaurants.json").write_text(json.dumps([{"id": 1}]))

    with pytest.raises(ResponseValidationError):
        client.get("/restaurants")