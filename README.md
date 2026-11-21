## Team

ByteBites

## Milestone 2 submission

The integrated customer-to-order workflow is implemented. See the
[M2 submission and demo guide](docs/milestones/M2.md) for test results, review
evidence, the 15-minute demonstration and publication checks. Canvas requires the
`m2-integrated-system` **tag URL and its full commit SHA**, not the moving `main`
branch. Publish the tag only after the final documentation PR is reviewed and merged.

## Python Version

Use Python 3.14.7.

## Setup

Clone the repository and enter the project directory:

```bash
git clone https://github.com/DavidZ666/Food_delivery.git
cd Food_delivery
```

Create and activate a virtual environment.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the Application

From the project root, with the virtual environment activated:

```bash
python -m uvicorn app.main:app --reload
```

The application runs at http://127.0.0.1:8000.

Press Ctrl+C in the terminal to stop the server.

### Management accounts

Registration only creates customers, and restaurant and menu writes need a
restaurant owner or admin. Register an account, stop the server, then set its
role (`customer`, `restaurant_owner` or `admin`):

```bash
python -m scripts.set_role ada@example.com restaurant_owner
```

The role is stored in `data/customers.json` and applies from the next request.

## Frontend

The frontend is in `frontend/` and gets served by the same FastAPI server, so
you don't need to run anything extra. Start the server like normal and go to
http://127.0.0.1:8000/app/ (or just http://127.0.0.1:8000/, it redirects).

It's plain HTML and JavaScript. The pages call the API with paths like
`/restaurants`, and since they're on the same server we didn't need any CORS
setup. All the restaurant data comes from the API, nothing is hard-coded.

**Design (#111):** every page shares one header (ByteBites home link, primary
navigation with the current page marked, and a skip link). Colors, type and
spacing are CSS custom properties at the top of `frontend/css/styles.css`, with
a dark scheme that follows the system setting. Text colors meet WCAG AA contrast
in both schemes, keyboard focus is always visible, and reduced-motion settings
are respected. The Bricolage Grotesque typeface is self-hosted in
`frontend/fonts/` under the SIL Open Font License (`OFL.txt`). New views should
reuse the tokens rather than add new colors. `tests/test_frontend_design.py` and
`tests/browser/layout.spec.mjs` check page chrome, contrast, self-hosted assets
and mobile layout from 320px.

| Page | Path | API calls |
|------|------|------|
| Restaurant list | /app/ | `GET /restaurants`, name search and cuisine filtering |
| Create a restaurant | /app/create-restaurant.html | `POST /restaurants` |
| Restaurant details, menu and cart | /app/restaurant.html?id=1 | Restaurant details and menu GET endpoints, cart endpoints, `POST /customers/{customer_id}/checkout` |
| Menu item details | /app/menu-item.html?restaurantId=1&productId=1 | Selected restaurant/item GET endpoint |
| Edit a restaurant | /app/edit-restaurant.html?id={restaurant_id} | `GET /restaurants`, `GET` + `PATCH /restaurants/{restaurant_id}` |
| Create an account | /app/register.html | `POST /customers` |
| Sign in | /app/sign-in.html | `POST /auth/login` |
| Account | /app/account.html | `GET` + `PATCH /customers/{customer_id}`, `POST /customers/{customer_id}/deactivate` |
| Your orders | /app/orders.html (one order: ?id={order_id}) | `GET /customers/{customer_id}/orders[/{order_id}]`, `GET /restaurants` for names |

**Create form:** checks the required fields first, then sends the request. If
the API sends back a 422 the errors show up next to the fields they belong to.
Server/network errors show at the bottom. When it works it shows the saved
restaurant (with its new ID) and a link to edit it.

**Edit form:** pick a restaurant from the dropdown (or open it with `?id=`)
and it loads into the form. Only the fields you changed get sent in the PATCH.
If you clear an optional field (description, logo URL, or a day's hours) it
sends `null` so it gets removed. Required fields can't be blank, and if you
didn't change anything it just says so and doesn't send anything. Unknown IDs
and errors are shown without wiping what you typed.

**Accounts (#95):** register, then sign in. The session token is kept in
`sessionStorage` (it ends when the tab closes or the server restarts) and is
sent as a bearer token on every request, including the restaurant forms. The
account page loads the profile from the API, sends only the changed fields,
and can sign out or deactivate the account after a confirmation. A 401 clears
the stored session and asks you to sign in again; a 403 says the account is not
allowed to do that.

**Checkout and orders (#97):** the cart on the restaurant page has a Check out
button (disabled while the cart is empty). It calls the checkout endpoint, which
rechecks the menu and saves the order at current prices. The saved order then
shows above the cart with its items, delivery address and the total the backend
saved, and the cart reloads empty. If checkout is rejected (for example an item
became unavailable) the error is shown and the cart stays as it was, since the
backend didn't change anything. If the order is saved but the cart can't be
reloaded afterwards, the message still gives the order number and the cart
controls stay disabled until Reload cart works. The Orders page in the nav lists the signed-in
customer's orders newest first and `orders.html?id=N` shows one order. Unknown
order IDs show "Order not found".

The JS is split up so most of it can be tested:
- `js/api.js` makes the requests and turns errors into an `ApiError`
- `js/restaurant-form.js` has the validation and builds the request bodies (no DOM code, so the node tests can use it)
- `js/form-ui.js` shows status messages and field errors
- `js/session.js` stores the signed-in session
- `js/account-form.js` has the account validation and request bodies (no DOM code)
- `js/cart.js` has the cart and checkout requests and state (no DOM code), `js/cart-ui.js` draws the cart panel
- `js/orders.js` checks and loads orders (no DOM code), `js/order-view.js` draws one order for both the
  checkout confirmation and the orders page, `js/orders-page.js` runs the orders page

## API Endpoints

See [the M1 API contract](docs/API_CONTRACT.md) for field rules, request/response
examples, PATCH differences, errors, ID allocation and storage limits. `/docs` provides
executable examples; `/openapi.json` provides their machine-readable schemas.

The contract examples are exercised with isolated data:

```bash
python -m pytest tests/test_api_contract.py -v
```


| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Returns HTTP 200 and `{"status": "ok"}` |
| GET | /restaurants | Lists restaurants; optional `name` substring and `cuisine` exact-match filters |
| POST | /restaurants | Creates a restaurant; returns HTTP 201 |
| GET | /restaurants/{restaurant_id}/menu | Returns the restaurant menu |
| POST | /restaurants/{restaurant_id}/menu | Creates a menu item |
| PATCH | /restaurants/{restaurant_id}/menu/{product_id} | Updates a menu item |
| DELETE | /restaurants/{restaurant_id}/menu/{product_id} | Removes a menu item |
| GET | /restaurants/{restaurant_id}/menu/{product_id} | Returns a menu item belonging to the restaurant |
| GET | /restaurants/{restaurant_id} | Returns details for a stored restaurant ID |
| PATCH | /restaurants/{restaurant_id} | Partially updates a restaurant and returns its complete representation |
| GET | /docs | Opens the interactive API documentation |

Open these URLs while the server is running:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/restaurants
- http://127.0.0.1:8000/docs

### Create a restaurant

Send `POST /restaurants` with the required `name`, `cuisine` and `location`
(address, city, province, postal_code). Required text is trimmed and must be
nonblank. Optional `description`, `logo_url` and `hours` use the existing
restaurant response fields. Hours contain optional weekday strings.

```bash
curl -X POST http://127.0.0.1:8000/restaurants \
  -H 'Content-Type: application/json' \
  -d '{"name":"New Café","cuisine":"Fusion","location":{"address":"3 Main St","city":"Kelowna","province":"BC","postal_code":"V1V 1V3"}}'
```

Success returns HTTP 201 with the persisted restaurant and its generated `id`.
IDs start at 1 for empty storage and otherwise use the largest stored ID plus
one. Existing records and menu relationships are preserved. The new record
appears in `GET /restaurants`, including after an application restart.

Missing or invalid fields, unknown fields (including nested fields), and
client-supplied IDs return HTTP 422 without changing storage. Missing files,
invalid stored records or IDs, and write failures return HTTP 500; storage is
not silently initialized. See `/docs` for request and response schemas.

### Search and read restaurants

Search by a literal substring of the restaurant name:

```bash
curl --get --data-urlencode "name=Mc" http://127.0.0.1:8000/restaurants
```

Search matches restaurant names only, ignoring case and surrounding query
whitespace. Punctuation is literal. Omitted or blank queries return the full
list; no matches return HTTP 200 with `[]`.

Use an integer `id` from the restaurant list to retrieve its details:

```bash
curl http://127.0.0.1:8000/restaurants/1
```

The endpoint returns the same fields as the restaurant list. Unknown IDs
return HTTP 404; non-integer IDs return HTTP 422.

### Filter restaurants by cuisine

Use the optional `cuisine` query parameter to filter restaurants:

```bash
curl --get \
  --data-urlencode "cuisine=Fast Food" \
  http://127.0.0.1:8000/restaurants
```

Cuisine filtering uses a case-insensitive exact match. Surrounding
query whitespace is ignored. An omitted or blank cuisine parameter
does not restrict the results.

Name search and cuisine filtering can be combined:

```bash
curl --get \
  --data-urlencode "name=mc" \
  --data-urlencode "cuisine=Fast Food" \
  http://127.0.0.1:8000/restaurants
```

When both parameters are supplied, a restaurant must match both.
Name search remains a case-insensitive literal substring match.
Results retain storage order and the existing restaurant fields.

No matches or an empty restaurant collection return HTTP 200 with `[]`.
Reads do not modify stored data. Missing or malformed storage remains
a server error rather than an empty search result.

## Data and Configuration

The restaurant-list endpoint reads `data/restaurants.json`.
This file contains two representative restaurants. Each restaurant has a required `id (int)`, `name`, `cuisine`, and `location` (address, city, province, postal code). Each restaurant also has optional fields `description`, `logo_url`, and weekly `hours`. The model is defined in `app/schemas/restaurant.py`.

The default data directory is the repository's `data` directory.
Set the `FOOD_DELIVERY_DATA_DIR` environment variable to use a
different directory. That directory must contain `restaurants.json`.
Menu requests also require `products.json` in the same directory.
Customer accounts are stored in `customers.json` (initially `[]`).
Carts are stored in `carts.json` (initially `[]`).
Orders are stored in `orders.json` (initially `[]`) as append-only snapshots;
see [the order contract](docs/API_CONTRACT.md#m2-order-contract-89). Customers check
out their cart with `POST /customers/{customer_id}/checkout`, which saves the
order at current menu prices and consumes the cart in the same atomic order
write; cart edits wait for an in-progress checkout. Failed order writes leave
cart bytes unchanged ([checkout](docs/API_CONTRACT.md#checkout-90)). Cart reads
apply internal consumption receipts; raw cart files can retain purchased items
until the next successful mutation. Use the cart repository and back up/restore
`carts.json` and `orders.json` together.
They can list their orders or read one with `GET /customers/{customer_id}/orders[/{order_id}]`;
administrators can read any customer's orders ([order retrieval](docs/API_CONTRACT.md#order-retrieval-92)).

Customer registration (`POST /customers`) and sign-in (`POST /auth/login`) are
available. Registration stores a salted password hash and returns an active
customer account; sign-in returns an opaque bearer token valid for one hour.
Sessions are in memory and end on server restart; accounts persist and can sign
in again. Reusable authentication, role and customer-ownership guards are available
in `app/core/auth.py`; see [the guard contract](docs/API_CONTRACT.md#authentication-and-authorization-guards-77).
Restaurant and menu writes require a restaurant owner or admin token; browsing
stays public ([write authorization](docs/API_CONTRACT.md#restaurant-and-menu-write-authorization-78)).
Signed-in customers can read and update their profile and delivery address or
deactivate their account ([profile contract](docs/API_CONTRACT.md#profile-and-deactivation-75)).
Customers can create and retrieve their single active cart with backend-calculated
totals ([cart endpoints](docs/API_CONTRACT.md#active-cart-endpoints-82)) and add
available menu items from one restaurant ([add to cart](docs/API_CONTRACT.md#add-to-cart-84)),
then change quantities, remove items or clear the cart
([update, remove and clear](docs/API_CONTRACT.md#update-remove-and-clear-86)).
See [the customer/auth API contract](docs/API_CONTRACT.md#registration-and-sign-in-73)
for request examples, error codes and the credential contract.

The restaurant request follows this path:

Route → Service → Repository → JSON file

Restaurant and menu writes serialize the complete read/modify/write
operation within one process, and reads wait for any write in progress so
replacement also works on Windows (#117). They sync a temporary file in the data directory
before atomically replacing the target; failures before replacement preserve
the original file and clean up temporary files.
Run **one application worker** against a local data directory. Multiple
processes or external writers sharing that directory are unsupported.
Atomic replacement prevents partial JSON; power-loss durability of the
directory entry is not guaranteed. See [the write decision](docs/decisions/json-writes.md).

The route handles HTTP requests and declares the Pydantic response
model. The service delegates to the repository, which reads the
configured JSON file.

## Run Tests

From the project root, with dependencies installed and the virtual
environment activated:

```bash
python -m pytest -v
```

Starting the server separately is not required.

The frontend tests need Node.js 22+ (no npm install needed):

```bash
node --test "tests/frontend/*.test.mjs"
```

Tests cover:

- The health endpoint.
- The restaurant-list endpoint, including optional field support.
- Restaurant details and invalid or unknown IDs.
- Restaurant repository data loading.
- Name search and empty results.
- Menu browsing, item ownership and missing resources.
- Failure cases: missing data file, invalid JSON, and missing required fields.
- Restaurant creation, request validation, restart persistence, concurrent
  creation, invalid stored IDs, and failed writes that preserve original data.
- The whole customer to order workflow through the API, including a price
  change before checkout and a restart, and a check that add to cart and checkout
  reject the same menu items (`tests/test_m2_integration.py`).
- The shared menu item lookup used by the cart and checkout (`tests/test_catalog.py`).
- The frontend pages get served, and the form fields match the API's
  `RestaurantCreate`/`RestaurantUpdate` models (`tests/test_frontend.py`).
- The frontend JS: request bodies, validation, and 422/404/500/network errors
  (`tests/frontend/`). The JSON files in `tests/frontend/` are used by both the
  node tests and pytest, so if the form and the API stop matching a test fails.

Tests use temporary files created with pytest's `tmp_path`.
Backend tests use `monkeypatch` to temporarily set
`FOOD_DELIVERY_DATA_DIR`. Tests do not modify committed data.

Test file and subprocess text I/O must pass `encoding="utf-8"`, matching
storage, so results do not depend on the platform locale (#69). CI sets
`PYTHONWARNDEFAULTENCODING=1` and pytest turns the resulting `EncodingWarning`
into an error; run the same check locally with
`PYTHONWARNDEFAULTENCODING=1 python -m pytest`.

## Continuous Integration

Pull requests and pushes to `main` automatically install the project
dependencies and run the complete pytest suite (and the node frontend tests)
using GitHub Actions.

In **Actions**, select a CI run to view test counts and failing test names.
Download the JUnit report from **Artifacts** as `pytest-results-python-3.14`
(retained for 7 days). Available results are published even when tests fail;
unavailable results are reported explicitly.

## Repository Structure

```text
app/
├── main.py           # FastAPI application and router registration
├── routes/           # HTTP endpoints
├── services/         # Application logic
├── repositories/     # JSON data access
├── schemas/          # Pydantic response models
└── core/             # Data-directory configuration
frontend/             # HTML, CSS and JavaScript served at /app/
data/                 # Representative JSON data
tests/                # Automated tests (tests/frontend/ for JavaScript)
requirements.txt      # Python dependencies
README.md             # Setup, usage, and collaboration instructions
```

## Restaurant Menus

`GET /restaurants/1/menu` returns the restaurant's items in stored order,
including unavailable items. `GET /restaurants/1/menu/1` returns one item.
Existing restaurants with no items return `[]`. Unknown restaurants, unknown
items and items belonging to another restaurant return HTTP 404; non-integer
IDs return HTTP 422. See `/docs` for response fields.

### Create a menu item (#46)

```bash
curl -X POST http://127.0.0.1:8000/restaurants/1/menu \
  -H 'Content-Type: application/json' \
  -d '{"name":"Soup","category":"Main","price":5.5}'
```

Use an existing restaurant ID. Success returns the complete item (201), with
the next product ID across all restaurants; deleted IDs are never reissued
(the high-water mark is kept in `product_ids.json`). Keep this file with backups.
When absent, migration seeds it from live products and existing cart/order
references; IDs erased before migration and absent everywhere cannot be recovered.
Malformed references reject migration. Concurrent creation requests in
one process preserve all records and allocate unique IDs. Existing item fields
and positive, unique integer product IDs are validated before writing; invalid
storage returns 500 without replacement. Request fields retain the
[API contract](docs/API_CONTRACT.md), including ignored client-supplied IDs.

Run `python -m pytest tests/test_menu_creation.py -v` for isolated creation,
concurrency, validation and write-failure checks.
Run `python -m pytest tests/test_menu_creation_persistence.py -v` to verify new
items, ownership, defaults and subsequent ID allocation in a fresh process (#47).

## M1 browser acceptance (#29, #33, #41, #42)

The home page loads actual restaurants and cuisine choices from the API. Search
by name, select a cuisine, and click Search. Select a restaurant for its details
and menu, then select a menu item. Each page reports loading, empty and failure
states. Unavailable items remain visible. Restaurant details link to the existing
edit form; menu errors can be retried without losing restaurant details.
Submitted filters stay in the URL and are restored on reload and browser back.

Browser tests require Node.js 22+ and an installed Python environment:

```bash
npm ci
npx playwright install chromium
npm run test:e2e
```

The browser runner starts its own server using `.venv/bin/python`; set
`FOOD_DELIVERY_PYTHON` to another interpreter if needed. Each test uses temporary
data copies and checks the representative files remain unchanged. It also tests
creation/editing and persistence across an actual server restart.

Menu updates omit fields to preserve them. Explicit nulls and nonfinite prices
are rejected with 422 before writing, as these values cannot be represented by
the menu response schema. Empty updates remain no-ops; supplied IDs and unknown
fields remain ignored to preserve the existing API contract.

### Menu update persistence (#49)

```bash
curl -X PATCH http://127.0.0.1:8000/restaurants/1/menu/1 \
  -H 'Content-Type: application/json' \
  -d '{"price":6.5,"is_available":false}'
```

Use IDs returned by the API. A successful update returns the complete item
(200); menu and item reads retain the updated values, IDs and restaurant
ownership after restart. Unknown restaurants, items or wrong-owner items return
404. Invalid inputs return 422. Rejected requests and failures before file
replacement preserve both stored collections; storage failures return 500.
See [the API contract](docs/API_CONTRACT.md) for field rules and storage limits.

Run the focused acceptance checks with:

```bash
python -m pytest tests/test_menu_update_persistence.py tests/test_api_contract.py -v
```

The tests use temporary data, read back updates in a fresh Python process and
inject temporary-file, serialization and replacement failures. They also check
partial updates, no-ops, unchanged ownership and retry after a failed write.
All menu writes share the same transaction, preserving omitted fields and
concurrent changes within one process. Deletion preserves every other record.
