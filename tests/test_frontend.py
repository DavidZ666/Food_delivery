import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.repositories import restaurant_repo

CASES_DIR = Path(__file__).parent / "frontend"
FORM_CASES = json.loads((CASES_DIR / "create-form-cases.json").read_text(encoding="utf-8"))
UPDATE_CASES = json.loads((CASES_DIR / "update-form-cases.json").read_text(encoding="utf-8"))
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class FormFieldParser(HTMLParser):
    # grabs input names (and if they're required), links and scripts

    def __init__(self):
        super().__init__()
        self.fields = {}
        self.links = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"input", "textarea"} and "name" in attributes:
            self.fields[attributes["name"]] = "required" in attributes
        if tag == "a":
            self.links.append(attributes.get("href"))
        if tag == "script":
            self.scripts.append(attributes.get("src"))


def parse(html):
    parser = FormFieldParser()
    parser.feed(html)
    return parser


def schema_fields(schemas, name, prefix=""):
    # e.g. {"name": True, "location.city": True, "description": False}
    schema = schemas[name]
    required = set(schema.get("required", []))
    fields = {}
    for field, definition in schema["properties"].items():
        refs = [definition.get("$ref")] + [option.get("$ref") for option in definition.get("anyOf", [])]
        nested = next((ref.rsplit("/", 1)[1] for ref in refs if ref), None)
        if nested:
            fields.update(schema_fields(schemas, nested, f"{prefix}{field}."))
        else:
            fields[f"{prefix}{field}"] = field in required
    return fields


def nullable_fields(schemas, name, prefix=""):
    # same idea but True means the field can be set to null
    fields = {}
    for field, definition in schemas[name]["properties"].items():
        options = definition.get("anyOf", [definition])
        nested = next((o["$ref"].rsplit("/", 1)[1] for o in options if "$ref" in o), None)
        if nested:
            fields.update(nullable_fields(schemas, nested, f"{prefix}{field}."))
        else:
            fields[f"{prefix}{field}"] = any(o.get("type") == "null" for o in options)
    return fields


def form_values(restaurant):
    # python version of restaurantToValues in restaurant-form.js
    values = {field: restaurant.get(field) or "" for field in ("name", "cuisine", "description", "logo_url")}
    for field, value in restaurant["location"].items():
        values[f"location.{field}"] = value
    for day in WEEKDAYS:
        values[f"hours.{day}"] = (restaurant.get("hours") or {}).get(day) or ""
    return values


def test_root_redirects_to_frontend(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"


def test_home_page_links_to_management_forms(client):
    response = client.get("/app/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    links = parse(response.text).links
    assert "create-restaurant.html" in links
    assert "edit-restaurant.html" in links


@pytest.mark.parametrize("path,content_type", [
    ("/app/create-restaurant.html", "text/html"),
    ("/app/edit-restaurant.html", "text/html"),
    ("/app/js/api.js", "text/javascript"),
    ("/app/js/restaurant-form.js", "text/javascript"),
    ("/app/js/create-restaurant.js", "text/javascript"),
    ("/app/js/edit-restaurant.js", "text/javascript"),
    ("/app/js/form-ui.js", "text/javascript"),
    ("/app/css/styles.css", "text/css"),
])
def test_frontend_assets_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_unknown_frontend_page_is_404(client):
    assert client.get("/app/missing.html").status_code == 404


def test_frontend_is_not_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert not any(path.startswith("/app") for path in paths)


def test_create_form_fields_match_api_request_schema(client):
    page = parse(client.get("/app/create-restaurant.html").text)
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert page.fields == schema_fields(schemas, "RestaurantCreate")
    assert "js/create-restaurant.js" in page.scripts


@pytest.mark.parametrize("case", FORM_CASES, ids=[case["name"] for case in FORM_CASES])
def test_form_payloads_are_accepted_by_the_api(client, data_dir, case):
    # node tests check toCreatePayload builds these same bodies
    response = client.post("/restaurants", json=case["payload"])
    assert response.status_code == 201
    created = response.json()
    assert {key: created[key] for key in case["payload"] if key != "hours"} == {
        key: value for key, value in case["payload"].items() if key != "hours"
    }
    for day, hours in case["payload"].get("hours", {}).items():
        assert created["hours"][day] == hours
    assert restaurant_repo.list_all()[-1] == created


def test_edit_form_fields_match_api_update_schema(client):
    page = parse(client.get("/app/edit-restaurant.html").text)
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    nullable = nullable_fields(schemas, "RestaurantUpdate")
    assert set(page.fields) == set(nullable)
    # anything the API won't let you clear should be required on the form
    assert page.fields == {field: not clearable for field, clearable in nullable.items()}
    assert "js/edit-restaurant.js" in page.scripts


@pytest.mark.parametrize(
    "case",
    [case for case in UPDATE_CASES if case["payload"]],
    ids=[case["name"] for case in UPDATE_CASES if case["payload"]],
)
def test_update_payloads_save_the_form_values(client, data_dir, case):
    # node tests check toUpdatePayload builds these same bodies
    (data_dir / "restaurants.json").write_text(json.dumps([case["original"]]))
    response = client.patch(f"/restaurants/{case['original']['id']}", json=case["payload"])
    assert response.status_code == 200
    expected = {field: value.strip() for field, value in case["values"].items()}
    assert form_values(response.json()) == expected
    [stored] = restaurant_repo.list_all()
    assert form_values(stored) == expected


def test_unchanged_form_is_not_sent_because_api_rejects_empty_updates(client, data_dir):
    path = data_dir / "restaurants.json"
    original = path.read_bytes()
    assert client.patch("/restaurants/101", json={}).status_code == 422
    assert path.read_bytes() == original
