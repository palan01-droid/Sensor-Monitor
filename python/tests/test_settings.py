def test_get_settings_returns_defaults(client):
    resp = client.get('/api/settings')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['default_baud'] == 115200
    assert body['retention_days'] == 30


def test_post_settings_valid_value_persists(client):
    resp = client.post('/api/settings', json={'retention_days': 10})
    assert resp.status_code == 200
    assert resp.get_json()['settings']['retention_days'] == 10


def test_post_settings_rejects_out_of_range_value(client):
    resp = client.post('/api/settings', json={'retention_days': 9999})
    assert resp.status_code == 400
    assert 'retention_days' in resp.get_json()['errors'][0]


def test_post_settings_rejects_wrong_type(client):
    resp = client.post('/api/settings', json={'auto_analysis': 'not-a-bool'})
    assert resp.status_code == 400


def test_post_settings_ignores_unknown_key(client):
    resp = client.post('/api/settings', json={'unknown_setting': 1})
    assert resp.status_code == 200
