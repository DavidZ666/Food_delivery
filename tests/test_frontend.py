import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.core import customer_auth
from app.repositories import customer_repo, restaurant_repo

CASES_DIR = Path(__file__).parent / "frontend"
FORM_CASES = json.loads((CASES_DIR / "create-form-cases.json").read_text(encoding="utf-8"))
UPDATE_CASES = json.loads((CASES_DIR / "update-form-cases.json").read_text(encoding="utf-8"))
ACCOUNT_CASES = json.loads((CASES_DIR / "account-form-cases.json").read_text(encoding="utf-8"))
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
    assert "account.html" in links


@pytest.mark.parametrize("path,content_type", [
    ("/app/create-restaurant.html", "text/html"),
    ("/app/edit-restaurant.html", "text/html"),
    ("/app/js/api.js", "text/javascript"),
    ("/app/js/restaurant-form.js", "text/javascript"),
    ("/app/js/create-restaurant.js", "text/javascript"),
    ("/app/js/edit-restaurant.js", "text/javascript"),
    ("/app/js/form-ui.js", "text/javascript"),
    ("/app/register.html", "text/html"),
    ("/app/sign-in.html", "text/html"),
    ("/app/account.html", "text/html"),
    ("/app/js/session.js", "text/javascript"),
    ("/app/js/account-form.js", "text/javascript"),
    ("/app/js/register.js", "text/javascript"),
    ("/app/js/sign-in.js", "text/javascript"),
    ("/app/js/account.js", "text/javascript"),
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
    (data_dir / "restaurants.json").write_text(json.dumps([case["original"]]), encoding="utf-8")
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


@pytest.mark.parametrize("page_name,schema,script", [
    ("register.html", "CustomerCreate", "js/register.js"),
    ("sign-in.html", "LoginRequest", "js/sign-in.js"),
    ("account.html", "CustomerUpdate", "js/account.js"),
])
def test_account_form_fields_match_api_schemas(client, page_name, schema, script):
    page = parse(client.get(f"/app/{page_name}").text)
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    # none of these fields can be blank or cleared, so the forms require them all
    assert page.fields == dict.fromkeys(schema_fields(schemas, schema), True)
    assert script in page.scripts
    assert {"sign-in.html", "register.html"} - {page_name} <= set(page.links)


@pytest.mark.parametrize(
    "case", ACCOUNT_CASES["registration"], ids=[case["name"] for case in ACCOUNT_CASES["registration"]],
)
def test_registration_payloads_create_accounts_that_can_sign_in(anonymous_client, case):
    # node tests check toRegistrationPayload builds these same bodies
    payload = case["payload"]
    response = anonymous_client.post("/customers", json=payload)
    assert response.status_code == 201
    expected = {key: value for key, value in payload.items() if key != "password"}
    expected["email"] = payload["email"].lower()
    assert {key: response.json()[key] for key in expected} == expected
    login = anonymous_client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    assert login.json()["customer"] == response.json()


def profile_values(customer):
    # python version of customerToValues in account-form.js
    values = {"name": customer["name"], "phone": customer["phone"]}
    values.update({f"delivery_address.{field}": value for field, value in customer["delivery_address"].items()})
    return values


@pytest.mark.parametrize(
    "case", ACCOUNT_CASES["profile"], ids=[case["name"] for case in ACCOUNT_CASES["profile"]],
)
def test_profile_payloads_save_the_form_values(anonymous_client, data_dir, case):
    # node tests check toProfileUpdatePayload builds these same bodies
    original = case["original"]
    path = data_dir / "customers.json"
    records = [*json.loads(path.read_text(encoding="utf-8")),
               {**original, "password_hash": customer_auth.hash_password("example-password")}]
    path.write_text(json.dumps(records), encoding="utf-8")
    headers = {"Authorization": f"Bearer {customer_auth.issue_token(original['id'])}"}
    response = anonymous_client.patch(f"/customers/{original['id']}", json=case["payload"], headers=headers)
    if not case["payload"]:
        # the form does not send an unchanged profile because the API rejects empty updates
        assert response.status_code == 422
        assert json.loads(path.read_text(encoding="utf-8")) == records
        return
    assert response.status_code == 200
    expected = {field: value.strip() for field, value in case["values"].items()}
    assert profile_values(response.json()) == expected
    assert profile_values(customer_repo.get_by_id(original["id"])) == expected
