import sqlite3, os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "store_intelligence.db")

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS entry_exit_events (
            id_token        TEXT,
            event_type      TEXT,
            store_code      TEXT,
            camera_id       TEXT,
            event_timestamp TEXT,
            is_staff        INTEGER DEFAULT 0,
            gender_pred     TEXT,
            age_pred        INTEGER,
            age_bucket      TEXT,
            is_face_hidden  INTEGER DEFAULT 0,
            group_id        TEXT,
            group_size      INTEGER,
            PRIMARY KEY (id_token, event_type, event_timestamp)
        );

        CREATE TABLE IF NOT EXISTS zone_events (
            track_id        INTEGER,
            event_type      TEXT,
            store_id        TEXT,
            camera_id       TEXT,
            zone_id         TEXT,
            zone_name       TEXT,
            zone_type       TEXT,
            is_revenue_zone TEXT,
            event_time      TEXT,
            gender          TEXT,
            age             INTEGER,
            age_bucket      TEXT,
            PRIMARY KEY (track_id, event_type, zone_id, event_time)
        );

        CREATE TABLE IF NOT EXISTS queue_events (
            queue_event_id       TEXT PRIMARY KEY,
            event_type           TEXT,
            track_id             INTEGER,
            store_id             TEXT,
            camera_id            TEXT,
            zone_id              TEXT,
            queue_join_ts        TEXT,
            queue_served_ts      TEXT,
            queue_exit_ts        TEXT,
            wait_seconds         INTEGER,
            queue_position_at_join INTEGER,
            abandoned            INTEGER DEFAULT 0,
            gender               TEXT,
            age                  INTEGER,
            age_bucket           TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_entry_store ON entry_exit_events(store_code, event_timestamp);
        CREATE INDEX IF NOT EXISTS idx_zone_store  ON zone_events(store_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_queue_store ON queue_events(store_id, queue_join_ts);
        """)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()