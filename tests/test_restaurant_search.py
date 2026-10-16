import json

import pytest

from app.services import restaurant_service
from tests.conftest import SAMPLE_RESTAURANTS


@pytest.mark.parametrize('query,ids', [
    ('Test', [101, 102]),
    ('mCtEsT', [102]),
    ('  TESTAURANT\t', [101]),
    ('', [101, 102]),
    (' \t\n', [101, 102]),
    ('missing', []),
    ('Mexican', []),
    ('.*', []),
])
def test_name_search(client, data_dir, query, ids):
    path = data_dir / 'restaurants.json'
    original = path.read_bytes()
    response = client.get('/restaurants', params={'name': query})
    assert response.status_code == 200
    assert [item['id'] for item in response.json()] == ids
    assert path.read_bytes() == original
    if 101 in ids:
        assert response.json()[0]['hours']['sunday'] is None
    if 102 in ids:
        assert response.json()[-1]['description'] is None


def test_unicode_and_literal_punctuation(client, data_dir):
    records = [dict(SAMPLE_RESTAURANTS[0], name='Straße (Café)')]
    (data_dir / 'restaurants.json').write_text(json.dumps(records))
    for query in ['STRASSE', '(CAFÉ)']:
        response = client.get('/restaurants', params={'name': query})
        assert response.status_code == 200
        assert [item['id'] for item in response.json()] == [101]


def test_empty_storage(client, data_dir):
    (data_dir / 'restaurants.json').write_text('[]')
    response = client.get('/restaurants', params={'name': 'Test'})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize('query', [None, '', ' \t', 'TEST'])
def test_service_matches_without_mutating_repository(monkeypatch, query):
    records = [dict(item) for item in SAMPLE_RESTAURANTS]
    original = json.dumps(records)
    monkeypatch.setattr(restaurant_service.restaurant_repo, 'list_all', lambda: records)
    assert restaurant_service.list_restaurants(query) == records
    assert json.dumps(records) == original


@pytest.mark.parametrize('query', [None, 'mctest'])
def test_service_loads_repository_and_selects_names(monkeypatch, query):
    calls = []
    def load():
        calls.append(True)
        return SAMPLE_RESTAURANTS
    monkeypatch.setattr(restaurant_service.restaurant_repo, 'list_all', load)
    expected = SAMPLE_RESTAURANTS if query is None else SAMPLE_RESTAURANTS[1:]
    assert restaurant_service.list_restaurants(query) == expected
    assert calls == [True]


@pytest.mark.parametrize('failure', ['missing', 'invalid'])
def test_storage_failure_is_not_a_no_match(client, data_dir, failure):
    path = data_dir / 'restaurants.json'
    if failure == 'missing':
        path.rename(data_dir / 'restaurants.backup.json')
        error = FileNotFoundError
    else:
        path.write_text('{invalid')
        error = json.JSONDecodeError
    with pytest.raises(error):
        client.get('/restaurants', params={'name': 'missing'})


def test_search_openapi(client):
    operation = client.get('/openapi.json').json()['paths']['/restaurants']['get']
    parameter = next(p for p in operation['parameters'] if p['name'] == 'name')
    assert parameter['in'] == 'query'
    assert parameter['required'] is False
    assert 'substring' in parameter['description']
    schema = operation['responses']['200']['content']['application/json']['schema']
    assert schema['type'] == 'array'
    assert schema['items']['$ref'].endswith('/RestaurantRead')
    assert '422' in operation['responses']
