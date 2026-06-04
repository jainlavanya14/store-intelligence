from .database import get_conn
from datetime import datetime, timedelta

def get_health():
    try:
        with get_conn() as conn:
            # Get distinct stores from all three tables
            stores = set()

            for row in conn.execute("SELECT DISTINCT store_code as sid FROM entry_exit_events").fetchall():
                stores.add(row["sid"])
            for row in conn.execute("SELECT DISTINCT store_id as sid FROM zone_events").fetchall():
                stores.add(row["sid"])
            for row in conn.execute("SELECT DISTINCT store_id as sid FROM queue_events").fetchall():
                stores.add(row["sid"])

            store_status = {}
            for sid in stores:
                # Get last event timestamp across all tables
                last_entry = conn.execute(
                    "SELECT MAX(event_timestamp) as ts FROM entry_exit_events WHERE store_code=?", (sid,)
                ).fetchone()["ts"]

                last_zone = conn.execute(
                    "SELECT MAX(event_time) as ts FROM zone_events WHERE store_id=?", (sid,)
                ).fetchone()["ts"]

                last_queue = conn.execute(
                    "SELECT MAX(queue_exit_ts) as ts FROM queue_events WHERE store_id=?", (sid,)
                ).fetchone()["ts"]

                # Pick the most recent
                timestamps = [t for t in [last_entry, last_zone, last_queue] if t]
                last_ts = max(timestamps) if timestamps else None

                stale = False
                if last_ts:
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", ""))
                    stale = (datetime.utcnow() - last_dt) > timedelta(minutes=10)

                store_status[sid] = {
                    "last_event_timestamp": last_ts,
                    "stale_feed": stale
                }

        return {"status": "ok", "stores": store_status}

    except Exception as e:
        return {"status": "degraded", "error": str(e)}