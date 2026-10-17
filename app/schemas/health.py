from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Process liveness only; does not probe data files or external services."""

    status: Literal["ok"]
