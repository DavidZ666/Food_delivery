import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Callable, TypeVar


T = TypeVar("T")
# Covers the entire transaction, not just replacement. One application process.
# Reentrant so a transaction may update a companion file (the product ID sequence).
_write_lock = RLock()
_REQUIRED = object()


def storage_lock():
    """Coordinate a snapshot spanning JSON files with their write transactions."""
    return _write_lock


def read_json(file_path: Path):
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_json_array(file_path: Path) -> list:
    """Reject non-array storage before filtering can disguise it as no results."""
    records = read_json(file_path)
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON array in {file_path.name}")
    return records

def update_json(file_path: Path, transform: Callable[[Any], tuple[Any, T]], default: Any = _REQUIRED) -> T:
    """Serialize a read/transform/replace transaction on a local filesystem.

    The transform returns the new document and the caller's result. Failures
    before replacement leave the original untouched. Readers see either the
    old or new document. Multiple application processes are not supported.
    A missing file raises unless a default document is given, which is then
    transformed and created.
    """
    with _write_lock:
        try:
            current = read_json(file_path)
            mode = stat.S_IMODE(file_path.stat().st_mode)
        except FileNotFoundError:
            if default is _REQUIRED:
                raise
            current, mode = default, 0o644
        updated, result = transform(current)
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=file_path.parent,
                prefix=f".{file_path.name}.", suffix=".tmp", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(updated, temporary, ensure_ascii=False, indent=2, allow_nan=False)
                temporary.write("\n")
                temporary.flush()
                os.chmod(temporary.name, mode)
                os.fsync(temporary.fileno())
            os.replace(temporary_path, file_path)
            return result
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
