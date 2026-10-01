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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Returns HTTP 200 and `{"status": "ok"}` |
| GET | /restaurants | Returns the restaurant list |
| GET | /restaurants/{restaurant_id}/menu | Returns the restaurant menu |
| GET | /restaurants/{restaurant_id}/menu/{product_id} | Returns a menu item belonging to the restaurant |
| GET | /docs | Opens the interactive API documentation |

Open these URLs while the server is running:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/restaurants
- http://127.0.0.1:8000/docs

## Data and Configuration

The restaurant-list endpoint reads `data/restaurants.json`.
This file contains two representative restaurants. Each restaurant has a required `id (int)`, `name`, `cuisine`, and `location` (address, city, province, postal code). Each restaurant also has optional fields `description`, `logo_url`, and weekly `hours`. The model is defined in `app/schemas/restaurant.py`.

The default data directory is the repository's `data` directory.
Set the `FOOD_DELIVERY_DATA_DIR` environment variable to use a
different directory. That directory must contain `restaurants.json`.

The restaurant request follows this path:

Route → Service → Repository → JSON file

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

Tests cover:

- The health endpoint.
- The restaurant-list endpoint, including optional field support.
- Restaurant repository data loading.
- Failure cases: missing data file, invalid JSON, and missing required fields.

Tests use temporary files created with pytest's `tmp_path`.
Backend tests use `monkeypatch` to temporarily set
`FOOD_DELIVERY_DATA_DIR`. Tests do not modify committed data.

## Continuous Integration

Pull requests and pushes to `main` automatically install the project
dependencies and run the complete pytest suite using GitHub Actions.

## Repository Structure

```text
app/
├── main.py           # FastAPI application and router registration
├── routes/           # HTTP endpoints
├── services/         # Application logic
├── repositories/     # JSON data access
├── schemas/          # Pydantic response models
└── core/             # Data-directory configuration
data/                 # Representative JSON data
tests/                # Automated tests
requirements.txt      # Python dependencies
README.md             # Setup, usage, and collaboration instructions
```

## Restaurant Menus

`GET /restaurants/1/menu` returns the selected restaurant's products in stored
order, including unavailable items. `GET /restaurants/1/menu/1` returns one
item belonging to that restaurant. Responses preserve `product_id`,
`restaurant_id`, `name`, `description`, `price`, `category`, `image` and
`is_available` from `products.json`. Prices are JSON numbers.

An existing restaurant with no products returns HTTP 200 with `[]`. An unknown
restaurant returns HTTP 404 with `{"detail": "Restaurant not found"}`. Unknown
products and products belonging to another restaurant return HTTP 404 with
`{"detail": "Menu item not found"}`. Non-integer IDs return HTTP 422. Storage
failures remain server errors; they are not treated as missing resources.

Both `restaurants.json` and `products.json` must be present in the configured
data directory. Requests follow Route → Service → Repository → JSON and do
not change stored data. The service checks restaurant existence before loading
products, distinguishing an empty menu from a missing restaurant without
depending on the restaurant-details endpoint. Menu items use the existing
product IDs and restaurant relationships rather than a separate menu entity.
Preference filtering and menu writes are outside this feature.

Isolated tests cover menu order and fields, unavailable items, empty menus,
missing resources, ownership, invalid IDs, storage failures, response validation,
unchanged files and OpenAPI documentation.
