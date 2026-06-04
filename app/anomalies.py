from .database import get_conn

def get_anomalies(store_id: str):
    store_alt = "ST" + store_id.split("_")[-1]
    anomalies = []

    with get_conn() as conn:
        q = conn.execute("""
            SELECT COUNT(*) as depth FROM queue_events
            WHERE (store_id=? OR store_id=?) AND abandoned=0
        """, (store_id, store_alt)).fetchone()["depth"]

        if q >= 5:
            anomalies.append({
                "type": "BILLING_QUEUE_SPIKE",
                "severity": "CRITICAL" if q >= 8 else "WARN",
                "value": q,
                "suggested_action": "Open additional billing counter immediately." if q >= 8 else "Monitor queue."
            })

        visited = conn.execute("""
            SELECT DISTINCT zone_name FROM zone_events
            WHERE (store_id=? OR store_id=?) AND event_type='zone_entered'
        """, (store_id, store_alt)).fetchall()

        total_q = conn.execute("""
            SELECT COUNT(*) FROM queue_events
            WHERE store_id=? OR store_id=?
        """, (store_id, store_alt)).fetchone()[0]

        abandoned = conn.execute("""
            SELECT COUNT(*) FROM queue_events
            WHERE (store_id=? OR store_id=?) AND abandoned=1
        """, (store_id, store_alt)).fetchone()[0]

        if total_q > 0 and abandoned / total_q > 0.3:
            anomalies.append({
                "type": "HIGH_ABANDONMENT",
                "severity": "WARN",
                "value": round(abandoned / total_q, 2),
                "suggested_action": "Queue abandonment above 30%. Open more counters or deploy staff."
            })

    return {"store_id": store_id, "anomalies": anomalies}