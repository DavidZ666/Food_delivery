from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import PROJECT_ROOT
from app.routes import health, menu, restaurants

app = FastAPI()

app.include_router(health.router)
app.include_router(restaurants.router)
app.include_router(menu.router)


@app.get("/", include_in_schema=False)
def frontend_home():
    return RedirectResponse(url="/app/")


# Mounted last so API routes take precedence. Same origin, so no CORS needed.
app.mount("/app", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
