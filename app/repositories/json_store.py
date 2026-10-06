import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any, Callable, TypeVar


T = TypeVar("T")
# Covers the entire transaction, not just replacement. One application process.
_write_lock = Lock()


def read_json(file_path: Path):
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def update_json(file_path: Path, transform: Callable[[Any], tuple[Any, T]]) -> T:
    """Serialize a read/transform/replace transaction on a local filesystem.

    The transform returns the new document and the caller's result. Failures
    before replacement leave the original untouched. Readers see either the
    old or new document. Multiple application processes are not supported.
    """
    with _write_lock:
        updated, result = transform(read_json(file_path))
        mode = stat.S_IMODE(file_path.stat().st_mode)
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
