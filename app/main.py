from math import isfinite

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import PROJECT_ROOT
from app.core.api_contract import preserve_literal_openapi_examples
from app.routes import auth, cart, customers, health, menu, restaurants

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_error_response(_request: Request, exc: RequestValidationError):
    # Invalid numeric input can itself be unrepresentable in a JSON error body.
    errors = exc.errors()
    if getattr(_request.scope.get("route"), "path", None) in {"/customers", "/auth/login"}:
        # A model-level validation error can echo the entire credential body.
        errors = [{key: value for key, value in error.items() if key not in {"input", "ctx"}}
                  for error in errors]
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(
            errors,
            custom_encoder={float: lambda value: value if isfinite(value) else str(value)},
        )},
    )


app.include_router(health.router)
app.include_router(restaurants.router)
app.include_router(menu.router)
app.include_router(customers.router)
app.include_router(auth.router)
app.include_router(cart.router)


@app.get("/", include_in_schema=False)
def frontend_home():
    return RedirectResponse(url="/app/")


# Mounted last so API routes take precedence. Same origin, so no CORS needed.
app.mount("/app", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")

preserve_literal_openapi_examples(app, health.router, restaurants.router, menu.router)
