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
| GET | /docs | Opens the interactive API documentation |

Open these URLs while the server is running:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/restaurants
- http://127.0.0.1:8000/docs

## Data and Configuration

The restaurant-list endpoint reads `data/restaurants.json`.
This file contains two representative restaurants with `id`, `name`,
and `cuisine` fields.

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
- The restaurant-list endpoint.
- Restaurant repository data loading.
- Invalid JSON handling.
- Restaurant and menu data association.

Tests use temporary files created with pytest's `tmp_path`.
Backend tests use `monkeypatch` to temporarily set
`FOOD_DELIVERY_DATA_DIR`. Tests do not modify committed data.

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