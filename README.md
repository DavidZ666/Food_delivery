## Team

ByteBites

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

## Frontend

The frontend is in `frontend/` and gets served by the same FastAPI server, so
you don't need to run anything extra. Start the server like normal and go to
http://127.0.0.1:8000/app/ (or just http://127.0.0.1:8000/, it redirects).

It's plain HTML and JavaScript. The pages call the API with paths like
`/restaurants`, and since they're on the same server we didn't need any CORS
setup. All the restaurant data comes from the API, nothing is hard-coded.

| Page | Path | API calls |
|------|------|------|
| Home | /app/ | none, just links |
| Create a restaurant | /app/create-restaurant.html | `POST /restaurants` |
| Edit a restaurant | /app/edit-restaurant.html?id={restaurant_id} | `GET /restaurants`, `GET` + `PATCH /restaurants/{restaurant_id}` |

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

The JS is split up so most of it can be tested:
- `js/api.js` makes the requests and turns errors into an `ApiError`
- `js/restaurant-form.js` has the validation and builds the request bodies (no DOM code, so the node tests can use it)
- `js/form-ui.js` shows status messages and field errors

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Returns HTTP 200 and `{"status": "ok"}` |
| GET | /restaurants | Returns the restaurant list; optional `name` searches by name |
| POST | /restaurants | Creates a restaurant; returns HTTP 201 |
| GET | /restaurants/{restaurant_id}/menu | Returns the restaurant menu |
| GET | /restaurants/{restaurant_id}/menu/{product_id} | Returns a menu item belonging to the restaurant |
| GET | /restaurants/{restaurant_id} | Returns details for a stored restaurant ID |
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

The restaurant request follows this path:

Route → Service → Repository → JSON file

Writes serialize the complete read/modify/write operation within one process.
They sync a temporary file in the data directory before atomically replacing
`restaurants.json`; failures before replacement preserve the original file.
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
- The frontend pages get served, and the form fields match the API's
  `RestaurantCreate`/`RestaurantUpdate` models (`tests/test_frontend.py`).
- The frontend JS: request bodies, validation, and 422/404/500/network errors
  (`tests/frontend/`). The JSON files in `tests/frontend/` are used by both the
  node tests and pytest, so if the form and the API stop matching a test fails.

Tests use temporary files created with pytest's `tmp_path`.
Backend tests use `monkeypatch` to temporarily set
`FOOD_DELIVERY_DATA_DIR`. Tests do not modify committed data.

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
