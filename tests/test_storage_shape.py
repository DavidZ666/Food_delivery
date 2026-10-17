"""Invalid collection shapes must not masquerade as empty or missing resources."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import product_repo, restaurant_repo


INVALID_COLLECTIONS = ["{}", '{"items": []}', '""', '"records"', "null", "0", "false"]
RESTAURANT_READS = [
    "/restaurants", "/restaurants?name=no-match", "/restaurants?cuisine=no-match",
    "/restaurants/101", "/restaurants/999",
    "/restaurants/101/menu", "/restaurants/101/menu/1",
]
MENU_READS = ["/restaurants/101/menu", "/restaurants/101/menu/1"]


@pytest.mark.parametrize("stored", INVALID_COLLECTIONS)
@pytest.mark.parametrize("filename,repository", [
    ("restaurants.json", restaurant_repo), ("products.json", product_repo),
])
def test_repository_rejects_non_array_storage(data_dir, stored, filename, repository):
    path = data_dir / filename
    path.write_text(stored)
    with pytest.raises(ValueError, match="Expected a JSON array"):
        repository.list_all()
    assert path.read_text() == stored


@pytest.mark.parametrize("stored", INVALID_COLLECTIONS)
@pytest.mark.parametrize("filename,paths", [
    ("restaurants.json", RESTAURANT_READS), ("products.json", MENU_READS),
])
def test_invalid_storage_is_500_for_list_filter_and_detail(data_dir, stored, filename, paths):
    (data_dir / "products.json").write_text("[]")
    (data_dir / filename).write_text(stored)
    files = [data_dir / name for name in ("restaurants.json", "products.json")]
    before = [path.read_bytes() for path in files]
    with TestClient(app, raise_server_exceptions=False) as client:
        for path in paths:
            response = client.get(path)
            assert response.status_code == 500, (path, response.text)
            assert response.headers["content-type"].startswith("text/plain")
            assert response.text == "Internal Server Error"
    assert [path.read_bytes() for path in files] == before


def test_valid_empty_arrays_keep_empty_and_missing_semantics(client, data_dir):
    (data_dir / "products.json").write_text("[]")
    assert product_repo.list_all() == []
    assert client.get("/restaurants/101/menu").json() == []
    assert client.get("/restaurants/101/menu/1").status_code == 404
    (data_dir / "restaurants.json").write_text("[]")
    assert restaurant_repo.list_all() == []
    response = client.get("/restaurants?name=no-match&cuisine=no-match")
    assert response.status_code == 200
    assert response.json() == []
    assert client.get("/restaurants/101").status_code == 404
    assert client.get("/restaurants/101/menu").status_code == 404
