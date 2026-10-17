"""OpenAPI examples and response metadata; never used as application data."""
from copy import deepcopy

from fastapi.routing import APIRoute

RESTAURANT_CREATE = {
    "name": "Example Café", "cuisine": "Fusion", "description": "Lunch and dinner",
    "location": {"address": "3 Main St", "city": "Kelowna", "province": "BC", "postal_code": "V1V 1V3"},
}
RESTAURANT_READ = {"id": 1, **RESTAURANT_CREATE, "logo_url": None, "hours": None}
RESTAURANT_UPDATED = {
    **RESTAURANT_READ, "name": "Downtown Café", "description": None,
    "location": {**RESTAURANT_CREATE["location"], "city": "Vancouver"},
}
ITEM_CREATE = {
    "name": "Soup", "description": "Vegetable soup", "price": 5.0,
    "category": "Main", "image": "", "is_available": True,
}
ITEM_READ = {"product_id": 1, "restaurant_id": 1, **ITEM_CREATE}
ITEM_PATCH = {"price": 6.5, "is_available": False}

STORAGE_FAILURE = {
    "description": (
        "File access, JSON parsing or write failure, or a stored-data error "
        "detected while handling the request. Stored records are not uniformly validated."
    ),
    "content": {"text/plain": {
        "schema": {"type": "string"}, "example": "Internal Server Error",
    }},
}


def json_response(example, description="Successful response"):
    return {"description": description, "content": {"application/json": {"example": example}}}


def resource_error(model, *, item=False):
    examples = {"restaurant": {"value": {"detail": "Restaurant not found"}}}
    if item:
        examples["item"] = {"summary": "Unknown item or item owned by another restaurant",
                            "value": {"detail": "Menu item not found"}}
    return {"model": model, "description": "Requested resource does not exist in this restaurant context.",
            "content": {"application/json": {"examples": examples}}}


def validation_example(*, body=False, path=True):
    # openapi_extra merges with FastAPI's generated HTTPValidationError schema.
    # Do not replace the schema or change runtime validation behavior.
    body_error = {"type": "string_too_short", "loc": ["body", "name"],
              "msg": "String should have at least 1 character", "input": "", "ctx": {"min_length": 1}}
    path_error = {"type": "int_parsing", "loc": ["path", "restaurant_id"],
                  "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}
    examples = {}
    if body:
        examples["invalidName"] = {"value": {"detail": [body_error]}}
    if path:
        examples["invalidId"] = {"value": {"detail": [path_error]}}
    return {"responses": {"422": {
        "description": "Request validation failed before mutation. detail lists field locations, types and messages; input/context may also appear.",
        "content": {"application/json": {"examples": examples}},
    }}}


def preserve_literal_openapi_examples(app, *routers):
    """Restore literal example values after FastAPI's exclude_none serialization.

    A null in a PATCH example is a meaningful value, not missing documentation.
    Only example payloads are restored; generated schemas and routes are intact.
    """
    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        # Use the supplied routers rather than FastAPI private inclusion wrappers.
        for route in (route for router in routers for route in router.routes):
            if not isinstance(route, APIRoute) or not route.include_in_schema:
                continue
            for method in route.methods:
                operation = schema["paths"][route.path_format][method.lower()]
                if route.body_field:
                    examples = getattr(route.body_field.field_info, "openapi_examples", None)
                    if examples:
                        operation["requestBody"]["content"]["application/json"]["examples"] = deepcopy(examples)
                for status, response in route.responses.items():
                    for media_type, media in response.get("content", {}).items():
                        for key in ("example", "examples"):
                            if key in media:
                                operation["responses"][str(status)]["content"][media_type][key] = deepcopy(media[key])
        return schema

    app.openapi = openapi
