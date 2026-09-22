from fastapi import FastAPI
from app.routes import health, restaurants

app = FastAPI()

app.include_router(health.router)
app.include_router(restaurants.router)