import json, tempfile, os
from pathlib import Path


def read_json(file_path: Path):
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)

def write_json(path, data):
    path = Path(path)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_path, path)