# PROMPT: "Write pytest tests for a store analytics REST API built with FastAPI.
# The API has three SQLite tables: entry_exit_events, zone_events, queue_events.
# Test: unique visitor count, staff exclusion, conversion rate, zone visits,
# queue stats, zero-traffic store, and idempotent ingest. Use TestClient and
# tmp_path for isolated DB per test."
# CHANGES MADE: Fixed store_alt logic to use ST+number format. Added fixture to
# reset DB_PATH env var. Changed conversion_rate assertion to handle zero case.

import pytest, uuid, json
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

def entry_event(store_code="store_1076", is_staff=False, token=None):
    return {
        "event_type": "entry",
        "id_token": token or f"ID_{uuid.uuid4().hex[:6]}",
        "store_code": store_code,
        "camera_id": "cam1",
        "event_timestamp": "2026-03-08T18:10:05.000000",
        "is_staff": is_staff,
        "gender_pred": "F",
        "age_pred": 25,
        "age_bucket": "25-34",
        "is_face_hidden": False,
        "group_id": None,
        "group_size": None
    }

def zone_event(store_id="ST1076", event_type="zone_entered", track_id=None):
    return {
        "event_type": event_type,
        "track_id": track_id or int(uuid.uuid4().int % 10000),
        "store_id": store_id,
        "camera_id": "CAM2",
        "zone_id": "PURPLLE_MUM_1076_Z01",
        "zone_name": "Left Shelf",
        "zone_type": "SHELF",
        "is_revenue_zone": "Yes",
        "event_time": "2026-03-08T18:10:45.000000",
        "gender": "F",
        "age": 25,
        "age_bucket": "25-34"
    }

def queue_event(store_id="ST1076", abandoned=False, track_id=None):
    return {
        "queue_event_id": str(uuid.uuid4()),
        "event_type": "queue_abandoned" if abandoned else "queue_completed",
        "track_id": track_id or int(uuid.uuid4().int % 10000),
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

# ── Tests ─────────────────────────────────────────────────────────────────────

def test_zero_traffic_store(client):
    r = client.get("/stores/store_empty/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0

def test_unique_visitor_count(client):
    events = [entry_event() for _ in range(5)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/metrics")
    assert r.json()["unique_visitors"] == 5

def test_staff_excluded_from_metrics(client):
    events = [entry_event(is_staff=True) for _ in range(3)]
    events += [entry_event(is_staff=False) for _ in range(2)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/metrics")
    assert r.json()["unique_visitors"] == 2

def test_idempotent_ingest(client):
    evt = entry_event(token="ID_FIXED")
    r1 = client.post("/events/ingest", json={"events": [evt]})
    r2 = client.post("/events/ingest", json={"events": [evt]})
    assert r1.json()["accepted"] == 1
    assert r2.json()["duplicate"] == 1

def test_zone_visits_in_metrics(client):
    events = [entry_event() for _ in range(3)]
    events += [zone_event() for _ in range(3)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/metrics")
    assert "Left Shelf" in r.json()["zone_visits"]

def test_conversion_rate(client):
    entries = [entry_event() for _ in range(4)]
    queues  = [queue_event() for _ in range(2)]
    client.post("/events/ingest", json={"events": entries + queues})
    r = client.get("/stores/store_1076/metrics")
    assert r.json()["conversion_rate"] == 0.5

def test_abandonment_rate(client):
    events = [queue_event(abandoned=False) for _ in range(3)]
    events += [queue_event(abandoned=True) for _ in range(1)]
    client.post("/events/ingest", json={"events": events})
    r = client.get("/stores/store_1076/metrics")
    assert r.json()["abandonment_rate"] == 0.25

def test_batch_limit(client):
    events = [entry_event() for _ in range(501)]
    r = client.post("/events/ingest", json={"events": events})
    assert r.status_code == 422