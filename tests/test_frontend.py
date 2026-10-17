import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.repositories import restaurant_repo

FORM_CASES = json.loads(
    (Path(__file__).parent / "frontend" / "create-form-cases.json").read_text(encoding="utf-8")
)


class FormFieldParser(HTMLParser):
    """Collects the name and required flag of every input and textarea."""

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
    """Flatten a request schema into dotted names mapped to whether they are required."""
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


def test_root_redirects_to_frontend(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"


def test_home_page_links_to_create_form(client):
    response = client.get("/app/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "create-restaurant.html" in parse(response.text).links


@pytest.mark.parametrize("path,content_type", [
    ("/app/create-restaurant.html", "text/html"),
    ("/app/js/api.js", "text/javascript"),
    ("/app/js/restaurant-form.js", "text/javascript"),
    ("/app/js/create-restaurant.js", "text/javascript"),
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
    # The same payloads are produced by toCreatePayload in tests/frontend/.
    response = client.post("/restaurants", json=case["payload"])
    assert response.status_code == 201
    created = response.json()
    assert {key: created[key] for key in case["payload"] if key != "hours"} == {
        key: value for key, value in case["payload"].items() if key != "hours"
    }
    for day, hours in case["payload"].get("hours", {}).items():
        assert created["hours"][day] == hours
    assert restaurant_repo.list_all()[-1] == created
