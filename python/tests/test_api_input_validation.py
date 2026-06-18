def test_alerts_rejects_non_integer_limit(client):
    resp = client.get('/api/alerts?limit=not-a-number')
    assert resp.status_code == 400


def test_alerts_accepts_valid_limit(client):
    resp = client.get('/api/alerts?limit=5')
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_connect_rejects_non_integer_baud(client):
    resp = client.post('/api/connect', json={'port': '/dev/fake', 'baud': 'fast'})
    assert resp.status_code == 400


def test_connect_rejects_missing_port(client):
    resp = client.post('/api/connect', json={'baud': 9600})
    assert resp.status_code == 400


def test_history_falls_back_to_default_range_on_unknown_value(client):
    resp = client.get('/api/history?range=not-a-real-range')
    assert resp.status_code == 200
    assert resp.get_json() == []
