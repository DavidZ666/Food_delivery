from fastapi import APIRouter

from app.core.api_contract import json_response
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check process liveness",
    description="Return ok when the application can serve a request. Does not check JSON storage or external services.",
    responses={200: json_response({"status": "ok"}, "Application is responding.")},
)
def health():
    return {"status": "ok"}
