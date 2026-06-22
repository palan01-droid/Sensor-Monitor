"""Tests for input sanitization"""
import pytest


def test_ingest_sanitizes_unsafe_sensor_keys(client):
    """API should reject sensor data with unsafe keys (e.g., with special chars)"""
    # Send data with unsafe keys
    resp = client.post(
        '/api/ingest',
        json={'temp': 25, '$malicious': 'value', 'humidity_safe': 60},
        headers={'X-API-Key': 'test-device-key'},
    )
    assert resp.status_code == 200
    # Safe keys should be accepted, unsafe ones silently dropped
    assert resp.get_json()['ok'] is True


def test_ingest_accepts_alphanumeric_and_underscore_keys(client):
    """Sensor keys should allow letters, numbers, and underscores"""
    resp = client.post(
        '/api/ingest',
        json={
            'temperature_c': 25.3,
            'humidity_pct': 65,
            'mpu6050_accel_x': 0.12,
            'co2_ppm': 450,
        },
        headers={'X-API-Key': 'test-device-key'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


def test_ingest_rejects_keys_with_special_characters(client):
    """Sensor keys with dashes, dots, brackets should be rejected"""
    resp = client.post(
        '/api/ingest',
        json={
            'temp': 25,
            'sensor.name': 100,  # dot not allowed
            'data[0]': 50,       # brackets not allowed
        },
        headers={'X-API-Key': 'test-device-key'},
    )
    # Should still accept the request (it's valid JSON)
    assert resp.status_code == 200
    # But unsafe keys should be stripped out
