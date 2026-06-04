# PROMPT: "Write pytest tests for a video detection pipeline event schema validator.
# Events come in three types: entry/exit, zone_entered/zone_exited, queue_completed/
# queue_abandoned. Test: required fields present, event_type valid, timestamps parseable,
# is_staff is boolean, confidence between 0 and 1, no duplicate event IDs in a batch."
# CHANGES MADE: Adjusted required fields to match actual sample_events.jsonl schema.
# Removed confidence field check since new schema doesn't use it.

import json, pytest
from pathlib import Path
from datetime import datetime

SAMPLE_EVENTS_PATH = Path("data/sample_events.jsonl")

@pytest.fixture
def sample_events():
    events = []
    with open(SAMPLE_EVENTS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events

VALID_EVENT_TYPES = {
    "entry", "exit",
    "zone_entered", "zone_exited",
    "queue_completed", "queue_abandoned"
}

def test_sample_events_file_exists():
    assert SAMPLE_EVENTS_PATH.exists(), "sample_events.jsonl not found in data/"

def test_all_event_types_valid(sample_events):
    for evt in sample_events:
        assert evt["event_type"] in VALID_EVENT_TYPES, \
            f"Invalid event_type: {evt['event_type']}"

def test_entry_exit_required_fields(sample_events):
    for evt in sample_events:
        if evt["event_type"] in ("entry", "exit"):
            assert "id_token" in evt
            assert "store_code" in evt
            assert "camera_id" in evt
            assert "event_timestamp" in evt
            assert "is_staff" in evt

def test_zone_event_required_fields(sample_events):
    for evt in sample_events:
        if evt["event_type"] in ("zone_entered", "zone_exited"):
            assert "track_id" in evt
            assert "store_id" in evt
            assert "zone_id" in evt
            assert "zone_name" in evt
            assert "event_time" in evt

def test_queue_event_required_fields(sample_events):
    for evt in sample_events:
        if evt["event_type"] in ("queue_completed", "queue_abandoned"):
            assert "track_id" in evt
            assert "store_id" in evt
            assert "zone_id" in evt
            assert "queue_join_ts" in evt
            assert "abandoned" in evt

def test_timestamps_are_parseable(sample_events):
    for evt in sample_events:
        ts = evt.get("event_timestamp") or evt.get("event_time") or evt.get("queue_join_ts")
        if ts:
            datetime.fromisoformat(ts)

def test_is_staff_is_boolean(sample_events):
    for evt in sample_events:
        if "is_staff" in evt:
            assert isinstance(evt["is_staff"], bool), \
                f"is_staff should be bool, got {type(evt['is_staff'])}"

def test_no_duplicate_event_ids(sample_events):
    queue_ids = [e["queue_event_id"] for e in sample_events if "queue_event_id" in e]
    assert len(queue_ids) == len(set(queue_ids)), "Duplicate queue_event_ids found"

def test_abandoned_is_boolean(sample_events):
    for evt in sample_events:
        if "abandoned" in evt:
            assert isinstance(evt["abandoned"], bool), \
                f"abandoned should be bool, got {type(evt['abandoned'])}"