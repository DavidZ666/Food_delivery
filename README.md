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
| GET | /restaurants/{restaurant_id} | Returns details for a stored restaurant ID |
| GET | /docs | Opens the interactive API documentation |

Open these URLs while the server is running:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/restaurants
- http://127.0.0.1:8000/docs

Use an integer `id` from the restaurant list to retrieve its details:

```bash
curl http://127.0.0.1:8000/restaurants/1
```

`GET /restaurants/{restaurant_id}` returns HTTP 200 with the same
`RestaurantRead` fields as the list endpoint. An unknown integer ID returns
HTTP 404 with `{"detail": "Restaurant not found"}`, including when the stored
collection is empty. A non-integer ID returns HTTP 422 with FastAPI validation
details. Reads do not modify stored data. `/docs` documents these responses.

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
- Restaurant details, unknown IDs, empty collections, invalid IDs, and OpenAPI.
- Restaurant repository data loading.
- Failure cases: missing data file, invalid JSON, and missing required fields.

Tests use temporary files created with pytest's `tmp_path`.
Backend tests use `monkeypatch` to temporarily set
`FOOD_DELIVERY_DATA_DIR`. Tests do not modify committed data.

## Continuous Integration

Pull requests and pushes to `main` automatically install the project
dependencies and run the complete pytest suite using GitHub Actions.

Open the repository's **Actions** tab and select a CI run to view its
**Automated test results** summary. It shows total, passed, failed, error,
and skipped counts, plus names of failing tests. If tests could not run
or the report cannot be read, the summary explains that results are unavailable.

Download `pytest-results-python-3.14` from the run's **Artifacts** section
to inspect the JUnit XML report. Reports are retained for 7 days and are
published even when tests fail; failing tests still fail the CI job.
Publishing requires no secrets or write permissions, including for fork PRs.

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
