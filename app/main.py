from fastapi import FastAPI
from app.routes import health, menu, restaurants

app = FastAPI()

app.include_router(health.router)
app.include_router(restaurants.router)
app.include_router(menu.router)
