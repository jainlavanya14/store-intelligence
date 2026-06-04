# Architectural Choices

## Decision 1 — Detection Model: YOLOv8n + ByteTrack

### Options Considered
- **YOLOv8n** (chose this)
- YOLOv8s / YOLOv8m — heavier, more accurate but too slow for Colab free tier on 20-min clips
- MediaPipe — fast but weaker on partial occlusions and group scenarios
- RT-DETR — transformer-based, excellent accuracy but requires more GPU memory
- DeepSORT — appearance-based tracking, struggles with face-blurred footage

### What AI Suggested
Claude was asked to compare detection+tracking combinations for retail CCTV with face blur. It recommended YOLOv8n + ByteTrack as the best balance of speed and accuracy for this use case, noting that DeepSORT's re-identification relies heavily on face/appearance features which are unavailable when faces are blurred.

### What I Chose and Why
YOLOv8n + ByteTrack. ByteTrack uses motion-based tracking (IoU matching) rather than appearance matching, which makes it robust to face-blurred footage. YOLOv8n runs at ~30fps on Colab T4 GPU which is fast enough to process 20-minute clips in under 10 minutes per video. The nano model trades some accuracy for speed — acceptable since we flag low-confidence detections rather than dropping them.

**Where I disagreed with AI**: Claude suggested using YOLOv8s for better accuracy. Overrode this because the time cost on free Colab GPU was too high for 8 video files totalling ~900MB. Accuracy difference on person detection (the only class we use) is marginal between nano and small.

---

## Decision 2 — Event Schema Design

### Options Considered
- **Single unified event table** with nullable columns for all event types
- **Three separate tables** — entry_exit_events, zone_events, queue_events (chose this)
- **Single JSONB column** storing raw event payload (PostgreSQL only)

### What AI Suggested
Claude initially suggested a single events table with an `event_type` column and nullable fields for all possible attributes. Argument was simpler ingest logic and easier cross-event queries.

### What I Chose and Why
Three separate tables matching the three event schemas in `sample_events.jsonl`. Reasons:

1. **Schema enforcement at DB level** — each table only has columns relevant to its event type, no nulls for irrelevant fields
2. **Query clarity** — `SELECT COUNT(DISTINCT id_token) FROM entry_exit_events` is clearer than `SELECT COUNT(DISTINCT id_token) FROM events WHERE event_type='entry'`
3. **Idempotency** — composite primary keys per table are more precise. Entry events deduplicate on `(id_token, event_type, event_timestamp)`. Queue events deduplicate on `queue_event_id`
4. **Matches sample schema** — the provided `sample_events.jsonl` uses different field names per event type (e.g. `event_timestamp` for entry vs `event_time` for zone). A single table would require aliasing

**Tradeoff accepted**: Cross-event queries (e.g. funnel) require joining or separate queries per table. This is acceptable since funnel stages map cleanly to one table each.

---

## Decision 3 — Storage Engine: SQLite over PostgreSQL

### Options Considered
- **SQLite** (chose this)
- **PostgreSQL** — production-grade, better concurrency, JSONB support
- **DuckDB** — excellent for analytical queries, columnar storage
- **In-memory dict** — fastest but no persistence

### What AI Suggested
Claude recommended PostgreSQL for production-readiness, noting that the problem statement says "build as if it will be operated by a team." It suggested adding a postgres service to docker-compose.yml.

### What I Chose and Why
SQLite for this submission. Reasons:

1. **Zero infrastructure** — `docker compose up` starts one container, not two. The acceptance gate requires no manual steps beyond `git clone`
2. **Sufficient for the data volume** — 1134 events from 8 video clips. SQLite handles millions of rows without performance issues for read-heavy analytics workloads
3. **Simpler debugging** — DB file is directly inspectable with any SQLite browser. No connection strings, no auth, no port conflicts
4. **Volume persistence** — DB file mounted as Docker volume (`./data:/app/data`) so data survives container restarts

**What I would change for production**: At 40 live stores sending events in real time, SQLite's single-writer lock becomes a bottleneck. Would switch to PostgreSQL with connection pooling (asyncpg) and add a Redis layer for real-time queue depth metrics. The API code requires minimal changes — only `database.py` needs updating since all queries use standard SQL.

**Where I disagreed with AI**: Claude suggested adding PostgreSQL now "for production-readiness points." Disagreed — a broken two-service docker-compose that fails the acceptance gate scores zero. A working single-service SQLite submission scores more than a broken PostgreSQL one.

---

## Decision 4 — Dashboard Interface: Terminal vs Browser

### Options Considered
- **Terminal dashboard** using `rich` (`dashboard.py`)
- **Streamlit browser dashboard** using `streamlit_dashboard.py`
- **React/SPA frontend** with a separate web app

### What I Chose and Why
Chose to include both the terminal dashboard and the Streamlit dashboard. The terminal dashboard is lightweight and fast for developers, while the Streamlit app provides a browser-based UI that is easier for reviewers and non-technical stakeholders.

### Why not React
React would require a separate build pipeline, more dependencies, and more time to wire up. Streamlit gives a simple, single-file browser dashboard with minimal additional overhead.

### Practical tradeoff
- Terminal dashboard: no extra install beyond `rich` and `requests`.
- Browser dashboard: requires `streamlit`, but gives a more accessible review experience and richer visual layout.
