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
| File access, JSON parsing or write failure, or a detected stored-data error | 500, plain text `Internal Server Error` |

422 entries include `loc`, `msg`, `type`, and may include `input`/`ctx`. An invalid
restaurant path ID has location `["path","restaurant_id"]`; a bad price has
`["body","price"]`. Nonfinite numeric inputs are serialized safely in errors.
Request validation runs before resource lookup, so an invalid body can produce
422 even when its restaurant ID does not exist. For valid menu requests the
restaurant is checked before item lookup. File access and JSON parsing errors are
not converted to empty lists. Restaurant and product collection reads require a
top-level JSON array: objects (including `{}`), strings, numbers, booleans and
null return 500 before filtering or lookup. A valid empty array `[]` retains
normal empty-list/404 behavior. Rejected validation/ownership requests must not
alter stored records.

Menu writes validate the stored product collection, response fields and
creation field rules without coercing persisted types. Nonpositive, non-integer
or duplicate product IDs are rejected with 500 before writing. Existing records,
including extra metadata, are preserved. The top-level array check on reads is
not full per-record validation: records excluded by a filter may not be validated
by the response model. These checks do not establish integrity of every
stored relationship.

Writes retain Route → Service → Repository → JSON. `FOOD_DELIVERY_DATA_DIR` chooses
the directory; required files must exist, and are not silently initialized.
Restaurant and menu writes serialize read/modify/write and atomically
replace files using the shared transaction. Concurrent creation requests within
one process allocate unique product IDs and preserve records; concurrent updates
preserve changes to fields they omit. Deletions preserve concurrent creations and
updates through the same lock. Atomic replacement alone is not a transaction.
Use one application worker on a local filesystem, with no external writers.
See [the JSON write decision](decisions/json-writes.md) for durability limits.

## Verification

Run `python -m pytest tests/test_api_contract.py -v`, then the full pytest suite.
The contract tests call every documented success example, compare real 404/422/500
responses with the published examples, verify bodyless 204, null-clearing, item
ownership, no-op updates, ID reuse and health behavior with missing storage.
Existing restaurant/menu tests cover the remaining search and write edge cases.
All writes target temporary files; representative `data/` files stay unchanged.

# M2 customer and auth contract (#72)

Schemas (`app/schemas/customer.py`, `app/schemas/auth.py`) and storage
(`app/repositories/customer_repo.py`, `data/customers.json`) are implemented.
Registration and sign-in endpoints are implemented by #73. Profile and
deactivation endpoints remain planned for #75; bearer authentication guards and
role enforcement remain planned for #77/#78. The table includes these planned
operations; only POST `/customers` and POST `/auth/login` are implemented here.

| Method and path | Inputs | Success body | Status codes |
|---|---|---|---|
| POST `/customers` | `CustomerCreate` | `CustomerRead` | 201, 409, 422, 500 |
| POST `/auth/login` | `LoginRequest` | `TokenResponse` | 200, 401, 403, 422, 500 |
| GET `/customers/{customer_id}` | Bearer token | `CustomerRead` | 200, 401, 403, 404, 422, 500 |
| PATCH `/customers/{customer_id}` | Bearer token, `CustomerUpdate` | `CustomerRead` | 200, 401, 403, 404, 422, 500 |
| POST `/customers/{customer_id}/deactivate` | Bearer token | `CustomerRead` | 200, 401, 403, 404, 422, 500 |

| Situation | Result |
|---|---|
| Email already registered (trimmed, case-insensitive) | 409 `{"detail":"Email is already registered"}` |
| Wrong email or password; missing or invalid token | 401 `{"detail":"Invalid credentials"}` |
| Deactivated account, or another customer's profile without `admin` role | 403 `{"detail":"Forbidden"}` |
| Unknown customer ID | 404 `{"detail":"Customer not found"}` |

## Models

- `CustomerCreate`: `name`, `phone` (trimmed, nonblank), `email` (trimmed,
  lowercased, `local@domain.tld`, at most 254 characters), `password` (8–128
  characters) and `delivery_address` (`address`, `city`, `province`,
  `postal_code`, trimmed and nonblank). Unknown fields, `id`, `role` and
  `is_active` are rejected; the server assigns `role: "customer"` and
  `is_active: true`.
- `CustomerUpdate`: optional `name`, `phone`, `delivery_address`; the address
  merges by subfield. Empty objects, nulls and other fields return 422.
- `CustomerRead`: `id`, `name`, `email`, `phone`, `delivery_address`, `role`
  (`customer`, `restaurant_owner` or `admin`), `is_active`. Never includes the password hash.
- `LoginRequest`: `email`, `password`. `TokenResponse`: `access_token`,
  `token_type: "bearer"`, `customer` (`CustomerRead`).

## Storage

Each stored record is a `CustomerRead` plus `password_hash`; plaintext
passwords are never stored. IDs start at 1, then the maximum stored ID + 1;
accounts are deactivated, not deleted, so IDs are not reused. Writes use the
shared transaction and preserve other records and extra metadata. Malformed
storage (invalid JSON, non-array, invalid records or roles, nonpositive or
duplicate IDs, duplicate emails) is rejected with 500 without overwriting the
file. Duplicate-email and unknown-ID writes leave the file unchanged.

# M2 cart contract (#81)

Schemas (`app/schemas/cart.py`) and storage (`app/repositories/cart_repo.py`,
`data/carts.json`) are implemented. Endpoints are implemented by #82 (create,
read), #84 (add item) and #86 (update, remove, clear). All require the cart
owner's bearer token and an active account.

| Method and path | Inputs | Success body | Status codes |
|---|---|---|---|
| POST `/customers/{customer_id}/cart` | Bearer token | `CartRead` | 200 (existing), 201, 401, 403, 404, 422, 500 |
| GET `/customers/{customer_id}/cart` | Bearer token | `CartRead` | 200, 401, 403, 404, 422, 500 |
| POST `/customers/{customer_id}/cart/items` | Bearer token, `CartItemAdd` | `CartRead` | 200, 401, 403, 404, 409, 422, 500 |
| PATCH `/customers/{customer_id}/cart/items/{product_id}` | Bearer token, `CartItemUpdate` | `CartRead` | 200, 401, 403, 404, 422, 500 |
| DELETE `/customers/{customer_id}/cart/items/{product_id}` | Bearer token | `CartRead` | 200, 401, 403, 404, 422, 500 |
| DELETE `/customers/{customer_id}/cart/items` | Bearer token | `CartRead` | 200, 401, 403, 404, 422, 500 |

| Situation | Result |
|---|---|
| Customer has no cart, or the cart has no such item | 404 `{"detail":"Cart not found"}` / `{"detail":"Cart item not found"}` |
| Unknown menu item | 404 `{"detail":"Menu item not found"}` |
| Unavailable item, or item from another restaurant while the cart is not empty | 409 `{"detail":"Menu item is unavailable"}` / `{"detail":"Cart contains items from another restaurant"}` |

## Models and calculation

- `CartItemAdd`: `product_id` (positive integer), `quantity` (default 1).
  `CartItemUpdate`: `quantity`. Quantities are JSON integers `>= 1`; strings,
  booleans and decimals return 422. Prices, names and restaurant come from the
  menu item, never the client. Unknown fields return 422.
- `CartRead`: `cart_id`, `customer_id`, `restaurant_id`, `items`, `subtotal`,
  `total`. Each item has `product_id`, `name`, `unit_price`, `quantity`,
  `line_total`. `restaurant_id` is null exactly when `items` is empty; a product
  appears at most once (adding it again increases its quantity).
- `line_total` = `unit_price` × `quantity`, `subtotal` = sum of line totals,
  each rounded to 2 decimals. `total` = `subtotal` (no tax, fees or delivery
  charge). Totals are calculated on every read and never stored. Checkout (#90)
  recalculates from current menu prices.

## Storage

Each record is a `CartRead` without the calculated totals. A customer has at
most one cart, which is their active cart; clearing it keeps its `cart_id`.
IDs start at 1, then the maximum stored ID + 1; carts are not deleted, so IDs
are not reused. Writes use the shared transaction and preserve other records
and extra metadata. Malformed storage (invalid JSON, non-array, invalid
records or quantities, inconsistent `restaurant_id`, duplicate products,
nonpositive or duplicate cart IDs, more than one cart per customer) is
rejected with 500 without overwriting the file.
## Registration and sign-in (#73)

POST `/customers` with this JSON body returns 201 and `CustomerRead`:

```json
{
  "name": "Ada", "email": "ada@example.com", "password": "example-password",
  "phone": "250-555-0100",
  "delivery_address": {
    "address": "1 Main St", "city": "Kelowna",
    "province": "BC", "postal_code": "V1V 1V1"
  }
}
```

POST `/auth/login` with `{"email":"ada@example.com","password":"example-password"}`
returns 200 with `{"access_token":"<opaque token>","token_type":"bearer","customer":{...}}`.
Registration does not issue a token. Email matching ignores surrounding whitespace
and case; passwords are exact, including whitespace and Unicode. Wrong passwords
and unknown accounts return the same 401 error with `WWW-Authenticate: Bearer`.
A correct password for a deactivated account returns 403. Login does not write
customer storage. Credential request validation returns 422 without `input` or
`ctx` fields, preventing passwords from being echoed in errors.

Passwords use salted scrypt, stored as
`scrypt$16384$8$1$<16-byte salt hex>$<64-byte digest hex>` (N=16384, r=8, p=1).
Each registration generates a fresh salt. Verification uses constant-time digest
comparison. Malformed or unsupported stored password hashes return 500.

### Bearer credential contract for #77

- Send `Authorization: Bearer <access_token>` to future protected operations.
- Tokens are opaque, generated from 32 random bytes using URL-safe encoding.
  They are not JWTs and contain no client-readable identity or role claims.
- Sessions expire one hour after issuance, with no sliding renewal. Sign in
  again to obtain a new token. Each login creates an independent session.
- The single application process holds only SHA-256 token digests, customer IDs
  and expiry times in memory. Restarting the server invalidates all tokens;
  persisted accounts can still sign in after restart. Multiple workers are
  unsupported, consistent with the JSON storage model.
- `app.core.customer_auth.resolve_token(token)` returns the customer ID or
  `None` for unknown/expired tokens. Downstream guards must re-read the customer
  on every request and enforce active status, roles and ownership. Resolving a
  token alone does not authorize access. This task does not protect existing
  restaurant/menu endpoints or implement logout/refresh endpoints.

Verification: `python -m pytest tests/test_customer_auth.py tests/test_customer_repo.py -q`.
Tests use temporary storage and cover real-process restart/login, duplicate and
invalid registration, inactive accounts, storage failures, token expiry and
tampering, password secrecy, and generated OpenAPI request/response contracts.

### Authentication and authorization guards (#77)

`app/core/auth.py` provides reusable FastAPI dependencies:

| Dependency | Behavior |
|---|---|
| `get_current_customer` | Resolve the bearer token and reload the active account from storage; return `CustomerRead` without its password hash. Accepts any supported role. |
| `require_roles(*roles)` | Require one of the explicitly allowed roles: `customer`, `restaurant_owner`, `admin`. No role inheritance; an empty allowlist denies everyone. |
| `require_customer_owner` | Require the `customer` role and a matching `customer_id` path parameter. No admin bypass; endpoints allowing administrators must define that policy separately. |

Compose the dependencies with `Depends`, for example:

```python
from typing import Annotated
from fastapi import Depends
from app.core.auth import require_roles
from app.schemas.customer import CustomerRead

def manage_menu(
    account: Annotated[CustomerRead, Depends(require_roles("restaurant_owner", "admin"))],
):
    ...
```

Missing, malformed, unknown, expired or tampered credentials, and tokens for
removed accounts, return 401 `{"detail":"Invalid credentials"}` with
`WWW-Authenticate: Bearer`. Tokens must be sent in the `Authorization` header;
query parameters and cookies do not authenticate a request. Inactive accounts,
disallowed roles and failed ownership checks return 403 `{"detail":"Forbidden"}`.
Account state and role changes apply on the next request, including to existing
tokens. Storage failures remain 500; the guards do not write account data.

Composed routes declare HTTP bearer security in OpenAPI. This issue provides the
guards; #78 applies them to restaurant/menu writes and #75 to customer operations.

Verification: `python -m pytest tests/test_auth_guards.py -q`. Isolated tests cover
the full role matrix, ownership, deactivation and role changes after sign-in,
token rejection, storage errors, secret exclusion and OpenAPI composition.
Implementation references (retrieved through Exa):
[FastAPI HTTPBearer](https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer),
[current-user dependencies](https://fastapi.tiangolo.com/tutorial/security/get-current-user/),
[dependency composition](https://fastapi.tiangolo.com/reference/dependencies/).
