import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import json_store, restaurant_repo
from app.schemas.restaurant import RestaurantCreate, RestaurantUpdate
from app.services import restaurant_service


def test_update_preserves_records_metadata_products_and_reads(client, data_dir):
    path = data_dir / 'restaurants.json'
    records = json.loads(path.read_text())
    records[0]['future_metadata'] = {'enabled': True}
    path.write_text(json.dumps(records))
    products = data_dir / 'products.json'
    products.write_text(json.dumps([{
        'product_id': 1, 'restaurant_id': 101, 'name': 'Taco',
        'description': 'Bean taco', 'price': 4.5, 'category': 'Main',
        'image': '', 'is_available': True,
    }]))
    original_products = products.read_bytes()
    response = client.patch('/restaurants/101', json={
        'name': '  Updated Café  ', 'cuisine': ' Fusion ',
        'location': {'city': ' Vancouver '},
        'hours': {'monday': '10:00-18:00', 'tuesday': None},
        'description': None, 'logo_url': 'https://example.com/new.png',
    })
    assert response.status_code == 200
    saved = json.loads(path.read_text())
    expected = {**records[0], 'name': 'Updated Café', 'cuisine': 'Fusion',
                'description': None, 'logo_url': 'https://example.com/new.png',
                'location': {**records[0]['location'], 'city': 'Vancouver'},
                'hours': {**records[0]['hours'], 'monday': '10:00-18:00', 'tuesday': None}}
    assert saved == [expected, records[1]]
    assert response.json()['id'] == 101
    assert client.get('/restaurants/101').json() == response.json()
    assert client.get('/restaurants', params={'name': 'updated café'}).json() == [response.json()]
    assert products.read_bytes() == original_products
    assert client.get('/restaurants/101/menu/1').status_code == 200


def test_clear_and_initialize_optional_fields(client):
    response = client.patch('/restaurants/101', json={
        'description': None, 'logo_url': None, 'hours': None,
    })
    assert response.status_code == 200
    assert all(response.json()[field] is None for field in ('description', 'logo_url', 'hours'))
    for identifier in (101, 102):
        response = client.patch(f'/restaurants/{identifier}', json={'hours': {'monday': '09:00-17:00'}})
        assert response.status_code == 200
        assert response.json()['hours']['monday'] == '09:00-17:00'
        assert response.json()['hours']['tuesday'] is None


@pytest.mark.parametrize('payload', [
    {}, {'id': 999}, {'rating': 5}, {'name': ''}, {'name': '  '},
    {'name': None}, {'name': 42}, {'cuisine': None}, {'cuisine': '\t'},
    {'location': None}, {'location': {}}, {'location': {'city': None}},
    {'location': {'city': ' '}}, {'location': {'country': 'Canada'}},
    {'hours': {}}, {'hours': {'holiday': 'closed'}}, {'hours': {'monday': 12}},
    {'description': []}, {'logo_url': 12}, [], None,
])
def test_invalid_requests_preserve_storage(client, data_dir, payload):
    path = data_dir / 'restaurants.json'
    before = path.read_bytes()
    response = client.patch('/restaurants/101', json=payload)
    assert response.status_code == 422
    assert path.read_bytes() == before


@pytest.mark.parametrize('identifier', [999, 0, -1])
def test_unknown_integer_id(client, data_dir, identifier):
    path = data_dir / 'restaurants.json'
    before = path.read_bytes()
    response = client.patch(f'/restaurants/{identifier}', json={'name': 'New'})
    assert response.status_code == 404
    assert response.json() == {'detail': 'Restaurant not found'}
    assert path.read_bytes() == before


@pytest.mark.parametrize('identifier', ['abc', '101.5'])
def test_invalid_path(client, identifier):
    assert client.patch(f'/restaurants/{identifier}', json={'name': 'New'}).status_code == 422


def test_empty_store_returns_404(client, data_dir):
    path = data_dir / 'restaurants.json'
    path.write_text('[]')
    assert client.patch('/restaurants/101', json={'name': 'New'}).status_code == 404
    assert path.read_text() == '[]'


@pytest.mark.parametrize('stored', ['{invalid', '{}', '[{"id":101}]'])
def test_invalid_store_preserved(data_dir, stored):
    path = data_dir / 'restaurants.json'
    path.write_text(stored)
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.patch('/restaurants/101', json={'name': 'New'}).status_code == 500
    assert path.read_text() == stored


@pytest.mark.parametrize('identifier', [0, -1, True, '101', 101.0, 102])
def test_bad_stored_ids_preserved(data_dir, identifier):
    path = data_dir / 'restaurants.json'
    records = json.loads(path.read_text())
    records[0]['id'] = identifier
    path.write_text(json.dumps(records))
    before = path.read_bytes()
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.patch('/restaurants/101', json={'name': 'New'}).status_code == 500
    assert path.read_bytes() == before


def test_missing_store_is_not_created(data_dir):
    path = data_dir / 'restaurants.json'
    path.rename(data_dir / 'backup.json')
    with TestClient(app, raise_server_exceptions=False) as http:
        assert http.patch('/restaurants/101', json={'name': 'New'}).status_code == 500
    assert not path.exists()


@pytest.mark.parametrize('failure', ['serialize', 'sync', 'replace', 'temporary'])
def test_write_failure_preserves_original_and_products(data_dir, monkeypatch, failure):
    path = data_dir / 'restaurants.json'
    before = path.read_bytes()
    products = data_dir / 'products.json'
    products.write_text('[{"product_id":1,"restaurant_id":101}]')
    before_products = products.read_bytes()

    def fail(*args, **kwargs):
        raise OSError('simulated write failure')

    target, attribute = {
        'serialize': (json_store.json, 'dump'),
        'sync': (json_store.os, 'fsync'),
        'replace': (json_store.os, 'replace'),
        'temporary': (json_store, 'NamedTemporaryFile'),
    }[failure]
    monkeypatch.setattr(target, attribute, fail)
    with TestClient(app, raise_server_exceptions=False) as http:
        response = http.patch('/restaurants/101', json={'name': 'New'})
    assert response.status_code == 500
    assert path.read_bytes() == before
    assert products.read_bytes() == before_products
    assert not list(data_dir.glob('.restaurants.json.*.tmp'))


def test_fresh_process_reads_updated_list_and_detail(client, data_dir):
    response = client.patch('/restaurants/101', json={'name': 'Persistent Café'})
    assert response.status_code == 200
    script = '''
import json
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    print(json.dumps([client.get('/restaurants').json(), client.get('/restaurants/101').json()]))
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, 'FOOD_DELIVERY_DATA_DIR': str(data_dir)},
        capture_output=True, text=True, check=True, timeout=15,
    )
    listed, detail = json.loads(result.stdout)
    assert listed[0] == detail == response.json()


def test_concurrent_creation_and_nested_updates_share_transaction(data_dir):
    barrier = Barrier(3)
    original = restaurant_repo.get_by_id(101)
    created_fields = {key: value for key, value in original.items() if key != 'id'}

    def update(fields):
        barrier.wait(timeout=5)
        return restaurant_service.update_restaurant(101, RestaurantUpdate(**fields))

    def create():
        barrier.wait(timeout=5)
        return restaurant_service.create_restaurant(RestaurantCreate(**created_fields))

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(update, {'location': {'city': 'Vancouver'}}),
                   pool.submit(update, {'location': {'address': '99 New St'}}),
                   pool.submit(create)]
        for future in futures:
            future.result(timeout=10)
    records = restaurant_repo.list_all()
    assert len(records) == 3
    assert records[0]['location'] == {**original['location'], 'city': 'Vancouver', 'address': '99 New St'}
    assert [record['id'] for record in records] == [101, 102, 103]


def test_service_delegates_only_supplied_fields(monkeypatch):
    observed = []
    def update(identifier, changes):
        observed.append((identifier, changes))
        return {'id': identifier}
    monkeypatch.setattr(restaurant_repo, 'update_by_id', update)
    assert restaurant_service.update_restaurant(101, RestaurantUpdate(description=None)) == {'id': 101}
    assert observed == [(101, {'description': None})]


def test_openapi_matches_partial_request_contract(client):
    schema = client.get('/openapi.json').json()
    operation = schema['paths']['/restaurants/{restaurant_id}']['patch']
    assert operation['summary'] and operation['description']
    assert set(operation['responses']) == {'200', '404', '422', '500'}
    assert operation['parameters'][0]['schema']['type'] == 'integer'
    assert operation['requestBody']['required']
    body = operation['requestBody']['content']['application/json']
    assert body['schema']['$ref'].endswith('/RestaurantUpdate')
    example = body['examples']['partial']['value']
    assert client.patch('/restaurants/101', json=example).status_code == 200
    models = schema['components']['schemas']
    for name in ('RestaurantUpdate', 'LocationUpdate', 'HoursUpdate'):
        assert models[name]['additionalProperties'] is False
        assert models[name]['minProperties'] == 1
        assert not models[name].get('required')
    assert 'id' not in models['RestaurantUpdate']['properties']
    assert models['RestaurantUpdate']['properties']['name']['type'] == 'string'
    assert operation['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/RestaurantRead')