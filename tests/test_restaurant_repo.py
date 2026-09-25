import json
import pytest

from app.repositories import restaurant_repo


def test_list_all_returns_records_from_file(data_dir):
    restaurants = restaurant_repo.list_all()

    assert len(restaurants) == 2
    assert restaurants[0]["id"] == "t1"
    assert restaurants[1]["id"] == "t2"


def test_list_all_returns_empty_list_for_empty_file(data_dir):
    (data_dir / "restaurants.json").write_text("[]")

    assert restaurant_repo.list_all() == []


def test_list_all_raises_when_file_missing(data_dir):
    (data_dir / "restaurants.json").unlink()

    with pytest.raises(FileNotFoundError):
        restaurant_repo.list_all()


def test_list_all_raises_on_bad_json(data_dir):
    (data_dir / "restaurants.json").write_text("{ not valid json")

    with pytest.raises(json.JSONDecodeError):
        restaurant_repo.list_all()