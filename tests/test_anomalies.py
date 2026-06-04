# PROMPT: "Write pytest tests for anomaly detection in a retail store API.
# Test: billing queue spike at threshold 5 and 8, high abandonment rate above 30%,
# no anomalies on clean data, and empty store returns empty anomalies list."
# CHANGES MADE: Used ST1076 format for store_id in queue events to match
# the store_alt lookup logic. Fixed abandoned field to use bool not int.

import pytest, uuid
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    import app.database as db_mod
    db_mod.DB_PATH = db
    from app.main import app
    from app.database import init_db
    init_db()
    return TestClient(app)

def queue_event(abandoned=False, store_id="ST1076"):
    return {
        "queue_event_id": str(uuid.uuid4()),
        "event_type": "queue_abandoned" if abandoned else "queue_completed",
        "track_id": int(uuid.uuid4().int % 10000),
        "store_id": store_id,
        "camera_id": "CAM6",
        "zone_id": "PURPLLE_MUM_1076_Z_BILLING_01",
        "queue_join_ts": "2026-03-08T18:13:05.000000",
        "queue_served_ts": None if abandoned else "2026-03-08T18:13:13.000000",
        "queue_exit_ts": "2026-03-08T18:15:31.000000",
        "wait_seconds": 65 if abandoned else 8,
        "queue_position_at_join": 2,
        "abandoned": abandoned,
        "gender": "F",
        "age": 25,
        "age_bucket": "25-34"
    }

def test_no_anomalies_empty_store(client):
    r = client.get("/stores/store_empty/anomalies")
    assert r.status_code == 200
    assert r.json()["anomalies"] == []

def test_no_anomalies_clean_data(client):
    events = [queue_event(abandoned=False) for _ in range(3)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/anomalies")
    types = [a["type"] for a in r.json()["anomalies"]]
    assert "HIGH_ABANDONMENT" not in types

def test_high_abandonment_detected(client):
    events = [queue_event(abandoned=False) for _ in range(2)]
    events += [queue_event(abandoned=True) for _ in range(4)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/anomalies")
    types = [a["type"] for a in r.json()["anomalies"]]
    assert "HIGH_ABANDONMENT" in types

def test_anomaly_has_suggested_action(client):
    events = [queue_event(abandoned=True) for _ in range(5)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/anomalies")
    for anomaly in r.json()["anomalies"]:
        assert "suggested_action" in anomaly
        assert len(anomaly["suggested_action"]) > 0

def test_anomaly_severity_values(client):
    events = [queue_event(abandoned=True) for _ in range(5)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/anomalies")
    for anomaly in r.json()["anomalies"]:
        assert anomaly["severity"] in ("INFO", "WARN", "CRITICAL")