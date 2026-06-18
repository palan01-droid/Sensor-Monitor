def test_ingest_rejects_missing_api_key(client):
    resp = client.post('/api/ingest', json={'temp': 25.3})
    assert resp.status_code == 401


def test_ingest_rejects_wrong_api_key(client):
    resp = client.post(
        '/api/ingest', json={'temp': 25.3}, headers={'X-API-Key': 'wrong'}
    )
    assert resp.status_code == 401


def test_ingest_accepts_correct_api_key(client):
    resp = client.post(
        '/api/ingest',
        json={'temp': 25.3},
        headers={'X-API-Key': 'test-device-key'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


def test_ingest_rejects_non_object_payload(client):
    resp = client.post(
        '/api/ingest',
        json=[1, 2, 3],
        headers={'X-API-Key': 'test-device-key'},
    )
    assert resp.status_code == 400


def test_ingest_rejects_empty_object(client):
    resp = client.post(
        '/api/ingest', json={}, headers={'X-API-Key': 'test-device-key'}
    )
    assert resp.status_code == 400
