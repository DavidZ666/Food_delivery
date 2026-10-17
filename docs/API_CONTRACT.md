# M1 API contract (#27)

This documents the implemented M1 behavior. `/openapi.json` is the machine-readable
contract and `/docs` is its interactive view. Examples in those operations are
executed by `tests/test_api_contract.py` using temporary JSON files. They are
illustrative data, not extra restaurants or products loaded into the application.

## Transport and operations

Default origin: `http://127.0.0.1:8000`. Requests with bodies use
`Content-Type: application/json`. Successful bodies and 404/422 errors are JSON;
500 storage errors are plain text. DELETE success has no response body.

| Method and path | Inputs | Success body | Status codes |
|---|---|---|---|
| GET `/health` | None | `HealthResponse` | 200 |
| GET `/restaurants` | Optional `name`, `cuisine` query strings | `RestaurantRead[]` | 200, 422 (framework validation), 500 |
| POST `/restaurants` | `RestaurantCreate` | `RestaurantRead` | 201, 422, 500 |
| GET `/restaurants/{restaurant_id}` | Integer restaurant ID | `RestaurantRead` | 200, 404, 422, 500 |
| PATCH `/restaurants/{restaurant_id}` | Integer restaurant ID, `RestaurantUpdate` | Complete `RestaurantRead` | 200, 404, 422, 500 |
| GET `/restaurants/{restaurant_id}/menu` | Integer restaurant ID | `MenuItemRead[]` | 200, 404, 422, 500 |
| POST `/restaurants/{restaurant_id}/menu` | Integer restaurant ID, `MenuItemCreate` | `MenuItemRead` | 201, 404, 422, 500 |
| GET `/restaurants/{restaurant_id}/menu/{product_id}` | Integer restaurant and product IDs | `MenuItemRead` | 200, 404, 422, 500 |
| PATCH `/restaurants/{restaurant_id}/menu/{product_id}` | Integer IDs, `MenuItemUpdate` | Complete `MenuItemRead` | 200, 404, 422, 500 |
| DELETE `/restaurants/{restaurant_id}/menu/{product_id}` | Integer restaurant and product IDs | No body | 204, 404, 422, 500 |

`/` redirects to `/app/` (307). Static frontend pages under `/app/` and framework
documentation routes are not business API operations and are excluded from the
generated business-operation schema. There is no restaurant DELETE endpoint.

`/health` returns `{"status":"ok"}` with a literal `ok` response model. It is a
liveness check, not a storage-readiness check; it still returns 200 if JSON files
are unavailable. Authentication and authorization are not implemented in M1.

## Search and reads

- `name`: case-insensitive literal substring of the restaurant name, with
  surrounding query whitespace ignored. Punctuation is not a regex or wildcard.
- `cuisine`: case-insensitive exact match, also trimming query whitespace.
- Omitted/blank filters impose no restriction. Both supplied filters must match.
- Restaurant and menu lists retain storage order; no pagination is implemented.
- No matching restaurants, an empty restaurant store, or an existing restaurant
  with an empty menu returns 200 with `[]`. A missing restaurant returns 404.
- Menu reads include unavailable items. Item reads require ownership by the
  restaurant in the path; unknown and wrong-owner items both return 404.
- Path IDs must parse as integers (otherwise 422). Unknown integer IDs, including
  zero/negative values absent from storage, return 404 rather than validation errors.

Example: `GET /restaurants?name=caf%C3%A9&cuisine=Fusion`.

## Models and field rules

### Restaurants

`RestaurantCreate` requires `name`, `cuisine` and `location`. `location` requires
`address`, `city`, `province`, `postal_code`. These required strings are trimmed
and must remain nonblank. Optional `description` and `logo_url` accept strings or
null. `hours` is null or an object whose optional weekday fields (`monday` through
`sunday`) are strings or null. Hours and URL strings are not validated as business
time ranges or URL formats. Unknown fields and client-supplied `id` are rejected,
including unknown fields inside location/hours.

`RestaurantRead` returns `id`, `name`, `cuisine`, `location`, `description`,
`logo_url`, `hours`. Missing optional data appears as null. A non-null hours object
includes all seven weekday fields, with null for unspecified weekdays.

```json
{
  "name": "Example Café",
  "cuisine": "Fusion",
  "description": "Lunch and dinner",
  "location": {
    "address": "3 Main St", "city": "Kelowna",
    "province": "BC", "postal_code": "V1V 1V3"
  }
}
```

POST this body to `/restaurants`. On empty restaurant storage, 201 returns the
same values plus `"id":1`, `"logo_url":null`, `"hours":null`.

`RestaurantUpdate` accepts only supplied fields. Location/hours merge by subfield;
omitted fields remain unchanged. Required strings and location cannot be null.
`description`, `logo_url`, the entire `hours` object, and individual weekday values
can be cleared with null. Empty top-level or nested update objects return 422.

```json
{"name":"Downtown Café","location":{"city":"Vancouver"},"description":null}
```

PATCH `/restaurants/1` returns the complete updated restaurant, preserving ID,
street, province, postal code, cuisine and any omitted fields. Nulls in the
published OpenAPI examples are preserved explicitly because they mean clearing
data; they must not disappear during schema generation.

### Menu items

`MenuItemCreate` requires `name`, `category` (strings of length at least one), and
`price` (positive, finite number). It defaults `description` and `image` to empty
strings, and `is_available` to true. Unlike restaurant required text, item name
and category currently are not trimmed: whitespace-only nonempty strings are
accepted. Prices use the existing floating-point representation; no currency or
decimal rounding policy is enforced. Input uses Pydantic's existing coercion
rules, not strict scalar types (for example a numeric price string can parse).

Unknown fields, including supplied IDs, are ignored. The server assigns
`product_id` and derives `restaurant_id` from the path. `MenuItemRead` returns
both IDs plus all six editable fields; none of its fields accept null.

```json
{"name":"Soup","description":"Vegetable soup","price":5.0,"category":"Main","image":"","is_available":true}
```

POST `/restaurants/1/menu` returns 201 with these values and the assigned IDs.
On empty product storage the generated product ID is 1.

`MenuItemUpdate` uses the same editable fields and preserves omitted values.
Explicit nulls, empty name/category strings, nonpositive/nonfinite prices and
invalid scalar values return 422. `{}` or an unknown-only body is a no-op for an
existing item and returns its current full representation (200). It may still
rewrite the file; it is not guaranteed to preserve file bytes or timestamps.

```json
{"price":6.5,"is_available":false}
```

PATCH `/restaurants/1/menu/1` changes only price/availability, retaining IDs,
ownership and other fields. DELETE on that same path returns 204 with no body;
repeating the DELETE returns 404. No restaurant cascade operation is implemented.

## IDs, errors and storage limits

Restaurant IDs use 1 for an empty collection, otherwise the maximum stored ID + 1.
Product IDs use the same rule across all restaurants, not separately per menu.
Updates and process restarts retain existing IDs and product ownership. IDs are
not historical identifiers: deleting the greatest product ID can allow a later
creation to reuse it. There is no tombstone or monotonic sequence allocator.

| Situation | Result |
|---|---|
| Missing restaurant | 404 `{"detail":"Restaurant not found"}` |
| Missing item or item belonging to a different restaurant | 404 `{"detail":"Menu item not found"}` |
| Invalid body/path | 422 with a `detail` array of validation errors |
| Missing/malformed files, invalid persisted data or I/O failure | 500, plain text `Internal Server Error` |

422 entries include `loc`, `msg`, `type`, and may include `input`/`ctx`. An invalid
restaurant path ID has location `["path","restaurant_id"]`; a bad price has
`["body","price"]`. Nonfinite numeric inputs are serialized safely in errors.
Request validation runs before resource lookup, so an invalid body can produce
422 even when its restaurant ID does not exist. For valid menu requests the
restaurant is checked before item lookup. Reads never turn storage errors into
empty lists. Rejected validation/ownership requests must not alter stored records.

Writes retain Route → Service → Repository → JSON. `FOOD_DELIVERY_DATA_DIR` chooses
the directory; required files must exist, and are not silently initialized.
Restaurant transactions serialize read/modify/write and atomically replace files.
Menu mutations currently read/modify in the service and then replace the product
file through the repository; concurrent menu writes can lose updates or choose
the same new ID. Atomic replacement alone is not a transaction. Shared transaction
work belongs to #46/#48; this documentation does not claim it is implemented.
Use one application worker on a local filesystem, with no external writers.
See [the JSON write decision](decisions/json-writes.md) for durability limits.

## Verification and agreement

Run `python -m pytest tests/test_api_contract.py -v`, then the full pytest suite.
The contract tests call every documented success example, compare real 404/422/500
responses with the published examples, verify bodyless 204, null-clearing, item
ownership, no-op updates, ID reuse and health behavior with missing storage.
Existing restaurant/menu tests cover the remaining search and write edge cases.
All writes target temporary files; representative `data/` files stay unchanged.

The team should review these existing semantics in the #27 PR. A code/test pass
does not stand in for team agreement. Any later change to the merged behavior
must update the models, documentation and isolated tests together.
