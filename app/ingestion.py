from .database import get_conn
from .models import IngestRequest, IngestResponse
import uuid

EVENT_TYPE_MAP = {
    "ENTRY": "entry",
    "EXIT": "exit",
    "ZONE_ENTER": "zone_entered",
    "ZONE_EXIT": "zone_exited",
    "ZONE_DWELL": "zone_entered",
    "REENTRY": "entry",
    "BILLING_QUEUE_JOIN": "queue_completed",
    "BILLING_QUEUE_ABANDON": "queue_abandoned",
}

def ingest_events(req: IngestRequest) -> IngestResponse:
    accepted = rejected = duplicate = 0
    errors = []

    with get_conn() as conn:
        for evt in req.events:
            try:
                # Normalize event type
                etype = evt.get("event_type", "")
                etype = EVENT_TYPE_MAP.get(etype, etype)
                evt["event_type"] = etype

                # Normalize field names from old format
                if "visitor_id" in evt and "id_token" not in evt:
                    evt["id_token"] = evt["visitor_id"]
                if "store_id" in evt and "store_code" not in evt:
                    evt["store_code"] = evt["store_id"].lower().replace("store_blr_", "store_")
                if "timestamp" in evt and "event_timestamp" not in evt:
                    evt["event_timestamp"] = evt["timestamp"]
                if "timestamp" in evt and "event_time" not in evt:
                    evt["event_time"] = evt["timestamp"]
                if "track_id" not in evt:
                    evt["track_id"] = abs(hash(evt.get("id_token", ""))) % 100000

                if etype in ("entry", "exit", "reentry"):
                    conn.execute("""
                        INSERT OR IGNORE INTO entry_exit_events
                        (id_token,event_type,store_code,camera_id,event_timestamp,
                         is_staff,gender_pred,age_pred,age_bucket,is_face_hidden,
                         group_id,group_size)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        evt.get("id_token"),
                        etype,
                        evt.get("store_code", "store_1076"),
                        evt.get("camera_id"),
                        evt.get("event_timestamp"),
                        int(evt.get("is_staff", False)),
                        evt.get("gender_pred"),
                        evt.get("age_pred"),
                        evt.get("age_bucket"),
                        int(evt.get("is_face_hidden", False)),
                        evt.get("group_id"),
                        evt.get("group_size")
                    ))

                elif etype in ("zone_entered", "zone_exited"):
                    conn.execute("""
                        INSERT OR IGNORE INTO zone_events
                        (track_id,event_type,store_id,camera_id,zone_id,zone_name,
                         zone_type,is_revenue_zone,event_time,gender,age,age_bucket)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        evt.get("track_id"),
                        etype,
                        evt.get("store_id", evt.get("store_code", "store_1076")),
                        evt.get("camera_id"),
                        evt.get("zone_id", "MAIN_FLOOR"),
                        evt.get("zone_name", evt.get("zone_id", "MAIN_FLOOR")),
                        evt.get("zone_type", "SHELF"),
                        evt.get("is_revenue_zone", "Yes"),
                        evt.get("event_time", evt.get("event_timestamp")),
                        evt.get("gender"),
                        evt.get("age"),
                        evt.get("age_bucket")
                    ))

                elif etype in ("queue_completed", "queue_abandoned"):
                    conn.execute("""
                        INSERT OR IGNORE INTO queue_events
                        (queue_event_id,event_type,track_id,store_id,camera_id,zone_id,
                         queue_join_ts,queue_served_ts,queue_exit_ts,wait_seconds,
                         queue_position_at_join,abandoned,gender,age,age_bucket)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        evt.get("queue_event_id", str(uuid.uuid4())),
                        etype,
                        evt.get("track_id"),
                        evt.get("store_id", evt.get("store_code", "store_1076")),
                        evt.get("camera_id"),
                        evt.get("zone_id", "BILLING"),
                        evt.get("queue_join_ts", evt.get("event_timestamp")),
                        evt.get("queue_served_ts"),
                        evt.get("queue_exit_ts", evt.get("event_timestamp")),
                        evt.get("wait_seconds", 0),
                        evt.get("queue_position_at_join", 1),
                        int(evt.get("abandoned", etype == "queue_abandoned")),
                        evt.get("gender"),
                        evt.get("age"),
                        evt.get("age_bucket")
                    ))

                else:
                    rejected += 1
                    errors.append({
                        "event": str(evt)[:100],
                        "reason": f"Unknown event_type: {etype}"
                    })
                    continue

                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    duplicate += 1
                else:
                    accepted += 1

            except Exception as e:
                rejected += 1
                errors.append({"event": str(evt)[:100], "reason": str(e)})

    return IngestResponse(accepted=accepted, rejected=rejected,
                          duplicate=duplicate, errors=errors)