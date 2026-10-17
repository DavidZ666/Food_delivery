import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import restaurant_service


@pytest.mark.parametrize(
    "params, expected_ids",
    [
        ({}, [101, 102]),

        ({"cuisine": "Mexican"}, [101]),
        ({"cuisine": "Fast Food"}, [102]),

        ({"cuisine": "mExIcAn"}, [101]),
        ({"cuisine": "  FAST FOOD\t"}, [102]),

        ({"cuisine": ""}, [101, 102]),
        ({"cuisine": " \t\n"}, [101, 102]),

        ({"cuisine": "Italian"}, []),
        ({"cuisine": "Fast"}, []),
        ({"cuisine": ".*"}, []),

        ({"name": "mctest"}, [102]),

        (
            {"name": "TEST", "cuisine": "Fast Food"},
            [102],
        ),

        (
            {"name": "mctest", "cuisine": "Mexican"},
            [],
        ),

        (
            {"name": "mctest", "cuisine": " "},
            [102],
        ),
        (
            {"name": " ", "cuisine": "Mexican"},
            [101],
        ),
    ],
)
def test_filter_results_and_unchanged_storage(
    client,
    data_dir,
    params,
    expected_ids,
):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()

    all_restaurants = client.get("/restaurants").json()
    expected = [
        restaurant
        for restaurant in all_restaurants
        if restaurant["id"] in expected_ids
    ]

    response = client.get(
        "/restaurants",
        params=params,
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert [
        restaurant["id"]
        for restaurant in response.json()
    ] == expected_ids

    assert path.read_bytes() == original


def test_empty_storage_returns_empty_list(client, data_dir):
    path = data_dir / "restaurants.json"
    path.write_text("[]", encoding="utf-8")

    response = client.get(
        "/restaurants",
        params={"cuisine": "Mexican"},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert path.read_text(encoding="utf-8") == "[]"


def test_matching_records_preserve_storage_order(
    client,
    data_dir,
):
    path = data_dir / "restaurants.json"
    records = json.loads(path.read_text(encoding="utf-8"))

    first = deepcopy(records[0])
    second = deepcopy(records[1])

    first["id"] = 900
    second["id"] = 2
    second["cuisine"] = "Mexican"

    path.write_text(
        json.dumps([first, second]),
        encoding="utf-8",
    )
    original = path.read_bytes()

    response = client.get(
        "/restaurants",
        params={"cuisine": "Mexican"},
    )

    assert response.status_code == 200
    assert [
        restaurant["id"]
        for restaurant in response.json()
    ] == [900, 2]
    assert path.read_bytes() == original


def test_service_reads_repository_without_mutation(monkeypatch):
    records = [
        {"id": 1, "name": "First Café", "cuisine": "Mexican"},
        {"id": 2, "name": "Second Café", "cuisine": "Fast Food"},
    ]
    original = deepcopy(records)
    calls = []

    def load_records():
        calls.append(True)
        return records

    monkeypatch.setattr(
        restaurant_service.restaurant_repo,
        "list_all",
        load_records,
    )

    result = restaurant_service.list_restaurants(
        name="café",
        cuisine=" FAST FOOD ",
    )

    assert result == [records[1]]
    assert records == original
    assert calls == [True]


@pytest.mark.parametrize(
    "failure",
    ["missing", "invalid_json"],
)
def test_storage_failure_is_not_an_empty_result(
    data_dir,
    failure,
):
    path = data_dir / "restaurants.json"

    if failure == "missing":
        path.rename(data_dir / "restaurants.backup.json")
    else:
        path.write_text("{invalid json", encoding="utf-8")

    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/restaurants",
            params={"cuisine": "No Match"},
        )

    assert response.status_code == 500

    if failure == "missing":
        assert not path.exists()
    else:
        assert path.read_text(encoding="utf-8") == "{invalid json"


def test_filter_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/restaurants"]["get"]

    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    for name in ("name", "cuisine"):
        parameter = parameters[name]
        assert parameter["in"] == "query"
        assert parameter["required"] is False
        assert parameter["description"]

    assert "substring" in parameters["name"]["description"]
    assert "exact" in parameters["cuisine"]["description"]
    assert "both must match" in operation["description"]

    result_schema = operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert result_schema["type"] == "array"
    assert result_schema["items"]["$ref"].endswith(
        "/RestaurantRead"
    )
    assert "500" in operation["responses"]