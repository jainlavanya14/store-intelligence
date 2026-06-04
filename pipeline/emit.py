"""
emit.py — Event schema and emission helpers.
Centralises all event construction to ensure schema consistency.
"""
import uuid
from datetime import datetime

def emit_entry(store_code: str, camera_id: str, id_token: str,
               timestamp: datetime, is_staff: bool,
               group_id: str = None, group_size: int = None) -> dict:
    return {
        "event_type":       "entry",
        "id_token":         id_token,
        "store_code":       store_code,
        "camera_id":        camera_id,
        "event_timestamp":  _ts(timestamp),
        "is_staff":         is_staff,
        "gender_pred":      None,
        "age_pred":         None,
        "age_bucket":       None,
        "is_face_hidden":   False,
        "group_id":         group_id,
        "group_size":       group_size,
    }

def emit_exit(store_code: str, camera_id: str, id_token: str,
              timestamp: datetime, is_staff: bool) -> dict:
    return {
        "event_type":       "exit",
        "id_token":         id_token,
        "store_code":       store_code,
        "camera_id":        camera_id,
        "event_timestamp":  _ts(timestamp),
        "is_staff":         is_staff,
        "gender_pred":      None,
        "age_pred":         None,
        "age_bucket":       None,
        "is_face_hidden":   False,
        "group_id":         None,
        "group_size":       None,
    }

def emit_reentry(store_code: str, camera_id: str, id_token: str,
                 timestamp: datetime) -> dict:
    evt = emit_entry(store_code, camera_id, id_token, timestamp, False)
    evt["event_type"] = "reentry"
    return evt

def emit_zone_entered(store_id: str, camera_id: str, track_id: int,
                       zone_id: str, zone_name: str, zone_type: str,
                       timestamp: datetime) -> dict:
    return {
        "event_type":       "zone_entered",
        "track_id":         track_id,
        "store_id":         store_id,
        "camera_id":        camera_id,
        "zone_id":          zone_id,
        "zone_name":        zone_name,
        "zone_type":        zone_type,
        "is_revenue_zone":  "Yes",
        "event_time":       _ts(timestamp),
        "gender":           None,
        "age":              None,
        "age_bucket":       None,
    }

def emit_zone_exited(store_id: str, camera_id: str, track_id: int,
                      zone_id: str, zone_name: str, zone_type: str,
                      timestamp: datetime) -> dict:
    evt = emit_zone_entered(store_id, camera_id, track_id,
                             zone_id, zone_name, zone_type, timestamp)
    evt["event_type"] = "zone_exited"
    return evt

def emit_queue_completed(store_id: str, camera_id: str, track_id: int,
                          zone_id: str, join_ts: datetime, exit_ts: datetime,
                          wait_seconds: int, position: int) -> dict:
    return {
        "queue_event_id":        str(uuid.uuid4()),
        "event_type":            "queue_completed",
        "track_id":              track_id,
        "store_id":              store_id,
        "camera_id":             camera_id,
        "zone_id":               zone_id,
        "zone_name":             "Billing Counter Queue",
        "zone_type":             "BILLING",
        "queue_join_ts":         _ts(join_ts),
        "queue_served_ts":       _ts(exit_ts),
        "queue_exit_ts":         _ts(exit_ts),
        "wait_seconds":          wait_seconds,
        "queue_position_at_join": position,
        "abandoned":             False,
        "gender":                None,
        "age":                   None,
        "age_bucket":            None,
    }

def emit_queue_abandoned(store_id: str, camera_id: str, track_id: int,
                          zone_id: str, join_ts: datetime, exit_ts: datetime,
                          wait_seconds: int, position: int) -> dict:
    evt = emit_queue_completed(store_id, camera_id, track_id,
                                zone_id, join_ts, exit_ts, wait_seconds, position)
    evt["event_type"]    = "queue_abandoned"
    evt["queue_served_ts"] = None
    evt["abandoned"]     = True
    return evt

def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000000")