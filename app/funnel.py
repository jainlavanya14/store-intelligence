from .database import get_conn

def get_funnel(store_id: str):
    store_alt = "ST" + store_id.split("_")[-1]

    with get_conn() as conn:
        entries = conn.execute("""
            SELECT COUNT(DISTINCT id_token) FROM entry_exit_events
            WHERE store_code=? AND event_type='entry' AND is_staff=0
        """, (store_id,)).fetchone()[0]

        zone_visits = conn.execute("""
            SELECT COUNT(DISTINCT track_id) FROM zone_events
            WHERE (store_id=? OR store_id=?) AND event_type='zone_entered'
        """, (store_id, store_alt)).fetchone()[0]

        billing = conn.execute("""
            SELECT COUNT(DISTINCT track_id) FROM queue_events
            WHERE store_id=? OR store_id=?
        """, (store_id, store_alt)).fetchone()[0]

        completed = conn.execute("""
            SELECT COUNT(DISTINCT track_id) FROM queue_events
            WHERE (store_id=? OR store_id=?) AND abandoned=0
        """, (store_id, store_alt)).fetchone()[0]

       def drop(a, b):
    if not a or b > a:
        return 0.0
    return round((a - b) / a * 100, 1)

        return {
            "store_id": store_id,
            "funnel": [
                {"stage": "Entry",         "visitors": entries,     "drop_off_pct": 0.0},
                {"stage": "Zone Visit",    "visitors": zone_visits, "drop_off_pct": drop(entries, zone_visits)},
                {"stage": "Billing Queue", "visitors": billing,     "drop_off_pct": drop(zone_visits, billing)},
                {"stage": "Purchase",      "visitors": completed,   "drop_off_pct": drop(billing, completed)},
            ]
        }