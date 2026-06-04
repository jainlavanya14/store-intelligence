from .database import get_conn

def get_metrics(store_id: str):
    store_alt = "ST" + store_id.split("_")[-1]

    with get_conn() as conn:
        # Check both store_code and store_id formats for entry events
        unique_visitors = conn.execute("""
            SELECT COUNT(DISTINCT id_token) FROM entry_exit_events
            WHERE (store_code=? OR store_code=?) AND event_type='entry' AND is_staff=0
        """, (store_id, store_alt)).fetchone()[0]

        billing_visitors = conn.execute("""
            SELECT COUNT(DISTINCT track_id) FROM queue_events
            WHERE store_id=? OR store_id=?
        """, (store_id, store_alt)).fetchone()[0]

        conversion_rate = round(min(billing_visitors / unique_visitors, 1.0), 3) if unique_visitors else 0.0

        zone_dwell = conn.execute("""
            SELECT zone_name, COUNT(*) as visits
            FROM zone_events
            WHERE (store_id=? OR store_id=?) AND event_type='zone_entered'
            GROUP BY zone_name
        """, (store_id, store_alt)).fetchall()

        queue_stats = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(abandoned) as abandoned,
                   AVG(wait_seconds) as avg_wait
            FROM queue_events
            WHERE store_id=? OR store_id=?
        """, (store_id, store_alt)).fetchone()

        total_q    = queue_stats["total"] or 0
        abandoned  = queue_stats["abandoned"] or 0
        avg_wait   = round(queue_stats["avg_wait"] or 0, 1)
        abandon_rate = round(abandoned / total_q, 3) if total_q else 0.0

        return {
            "store_id": store_id,
            "unique_visitors": unique_visitors,
            "conversion_rate": conversion_rate,
            "zone_visits": {row["zone_name"]: row["visits"] for row in zone_dwell},
            "queue_depth": total_q,
            "avg_wait_seconds": avg_wait,
            "abandonment_rate": abandon_rate,
        }