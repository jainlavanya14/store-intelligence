# System Design — Store Intelligence

## Overview

Store Intelligence is an end-to-end retail analytics pipeline that processes raw CCTV footage and exposes a queryable REST API for real-time store metrics. The system converts raw video into structured behavioural events, ingests them into a database, and serves analytics across six endpoints.

## Architecture

CCTV Clips → Detection Pipeline → events.jsonl → POST /events/ingest → SQLite → REST API

The system has five layers:

**1. Detection Layer** (`pipeline/`)
YOLOv8n detects people in each frame. ByteTrack assigns persistent track IDs across frames. A custom `VisitorTracker` maps track IDs to visitor session tokens and handles re-entry detection via position similarity. Events are emitted in three schemas: entry/exit, zone, and queue.

**2. Event Stream** (`data/events.jsonl`)
Structured JSONL file with three event types matching the sample schema provided. Entry/exit events carry `id_token`, `store_code`, `is_staff`, `group_id`. Zone events carry `track_id`, `zone_id`, `zone_name`. Queue events carry timing fields for wait time and abandonment detection.

**3. Intelligence API** (`app/`)
FastAPI application with SQLite storage. Three tables map to the three event types. All endpoints handle both `store_1076` and `ST1076` ID formats. Idempotent ingest via primary key constraints. Structured JSON logging on every request.

**4. Browser Dashboard** (`streamlit_dashboard.py`)
A Streamlit frontend that queries the API and renders interactive store metrics, funnel tables, heatmaps, anomalies, and store health in the browser. This provides a reviewer-friendly UI alternative to the terminal dashboard.

**5. Storage**
SQLite chosen for simplicity and zero-dependency deployment. The DB file is mounted as a Docker volume so data persists across container restarts. For production scale (40 stores), PostgreSQL would replace SQLite with connection pooling.

## Edge Cases Handled

**Group entry**: People entering within 2 seconds of each other are assigned the same `group_id`. Each person still gets a unique `id_token` so group count doesn't inflate visitor numbers.

**Staff detection**: Tracks present in more than 200 frames are classified as staff (`is_staff=true`) and excluded from all customer metrics. Staff move continuously through all zones unlike customers who dwell.

**Re-entry**: `VisitorTracker` stores exit positions and timestamps. When a new track appears near a recently exited visitor's last position within a 5-minute window, it's flagged as `reentry` instead of a new `entry`.

**Partial occlusion**: Detection confidence threshold lowered to 0.30. Low-confidence detections (below 0.45) are flagged with `is_low_conf=true` rather than dropped silently. This preserves data while allowing downstream filtering.

**Empty store periods**: All API endpoints return zero values when no events exist for a store. No null returns, no crashes.

**Billing queue**: Queue depth tracked by counting simultaneous tracks in billing zone. Abandonment detected when a visitor leaves billing zone and no `queue_served_ts` follows within the wait window.

## API Design Decisions

**SQLite over PostgreSQL**: For a single-store demo with batch-ingested events, SQLite is sufficient and removes infrastructure complexity. Noted in CHOICES.md.

**Three-table schema**: Separating entry/exit, zone, and queue events into dedicated tables avoids nullable columns and makes queries cleaner. Each table has composite primary keys for idempotency.

**store_id normalisation**: The detection pipeline emits `store_code` (e.g. `store_1076`) for entry events and `store_id` (e.g. `ST1076`) for zone/queue events. The API normalises both formats at query time using `store_alt = "ST" + store_id.split("_")[-1]`.

## AI-Assisted Decisions

**1. ByteTrack vs DeepSORT**: Asked Claude to compare tracking algorithms for retail CCTV. Claude recommended ByteTrack for its speed and robustness to occlusion. Agreed — ByteTrack handles crowded billing areas better than DeepSORT's appearance-based matching which struggles with face-blurred footage.

**2. Three-table schema design**: Claude initially suggested a single events table with nullable columns. Overrode this — separate tables give cleaner queries and enforce schema at the DB level rather than in application code.

**3. Store ID normalisation**: Claude suggested normalising IDs at ingest time. Chose to normalise at query time instead — preserves the original event data exactly as emitted by the pipeline, making debugging easier.