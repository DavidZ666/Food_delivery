from copy import deepcopy

from pydantic import TypeAdapter

from app.core.config import get_data_dir
from app.repositories.json_store import read_json_array, update_json
from app.schemas.customer import CustomerRecord


class CustomerRecordNotFoundError(LookupError):
    pass


class DuplicateEmailError(ValueError):
    pass


_MUTABLE_FIELDS = {"name", "phone", "delivery_address", "is_active"}


def _path():
    return get_data_dir() / "customers.json"


def _validate_records(records) -> None:
    """Reject malformed storage before reads or writes rely on it."""
    validated = TypeAdapter(list[CustomerRecord]).validate_python(records, strict=True)
    ids = [record["id"] for record in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Stored customer IDs must be unique")
    emails = [record.email for record in validated]
    if len(set(emails)) != len(emails):
        raise ValueError("Stored customer emails must be unique")


def list_all() -> list[dict]:
    records = read_json_array(_path())
    _validate_records(records)
    return records


def get_by_id(customer_id: int) -> dict | None:
    return next((r for r in list_all() if r["id"] == customer_id), None)


def get_by_email(email: str) -> dict | None:
    email = email.strip().lower()
    return next((r for r in list_all() if r["email"].strip().lower() == email), None)


def create(fields: dict) -> dict:
    """Check email uniqueness, allocate an ID and append in one transaction."""
    def append(records):
        _validate_records(records)
        ids = [record["id"] for record in records]
        created = CustomerRecord.model_validate(
            {**fields, "id": max(ids, default=0) + 1}, strict=True,
        ).model_dump()
        email = created["email"].lower()
        if any(record["email"].strip().lower() == email for record in records):
            raise DuplicateEmailError("Email is already registered")
        return [*records, created], created

    return update_json(_path(), append)


def update_by_id(customer_id: int, changes: dict) -> dict:
    """Apply mutable field changes, merging delivery_address by subfield."""
    if not changes or changes.keys() - _MUTABLE_FIELDS:
        raise ValueError("Only mutable customer fields may be updated")

    def apply(records):
        _validate_records(records)
        for index, record in enumerate(records):
            if record["id"] == customer_id:
                updated = deepcopy(record)
                for field, value in changes.items():
                    if field == "delivery_address" and isinstance(value, dict):
                        value = {**updated[field], **value}
                    updated[field] = value
                validated = CustomerRecord.model_validate(updated, strict=True).model_dump()
                updated.update({field: validated[field] for field in changes})
                return [*records[:index], updated, *records[index + 1:]], updated
        raise CustomerRecordNotFoundError("Customer not found")

    return update_json(_path(), apply)
