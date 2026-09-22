import json
from pathlib import Path


def read_json(file_path: Path):
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)