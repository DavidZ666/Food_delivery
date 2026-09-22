import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    custom_dir = os.getenv("FOOD_DELIVERY_DATA_DIR")

    if custom_dir:
        return Path(custom_dir)

    return PROJECT_ROOT / "data"