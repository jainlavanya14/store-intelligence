# Store Intelligence

End-to-end retail analytics pipeline — from raw CCTV footage to a live store metrics API.

## What It Does

Processes CCTV clips from physical retail stores, detects and tracks visitors, emits structured behavioural events, and exposes a REST API for real-time analytics including conversion rate, zone heatmaps, funnel analysis, and anomaly detection.

## Quick Start (5 commands)

```bash
git clone https://github.com/jainlavanya14/store-intelligence.git
cd store-intelligence
docker compose up --build
python scripts/ingest_events.py data/events.jsonl
curl http://localhost:8000/stores/store_1076/metrics
```

## Project Structure

store-intelligence/
├── pipeline/
│   ├── detect.py        # YOLOv8 + ByteTrack detection pipeline
│   ├── tracker.py       # Re-ID and visitor session tracking
│   ├── emit.py          # Event schema and emission helpers
│   └── run.sh           # One command to process all clips
├── app/
│   ├── main.py          # FastAPI entrypoint
│   ├── models.py        # Pydantic event schema
│   ├── database.py      # SQLite setup and connection
│   ├── ingestion.py     # Ingest and deduplication
│   ├── metrics.py       # Real-time metric computation
│   ├── funnel.py        # Funnel and session logic
│   ├── anomalies.py     # Anomaly detection
│   └── health.py        # Health check endpoint
├── data/
│   ├── events.jsonl          # Generated events from detection
│   ├── sample_events.jsonl   # Sample events for testing
│   ├── pos_transactions.csv  # POS transaction data
│   └── store_layout.json     # Store and zone definitions
├── tests/
│   ├── test_metrics.py    # Metrics endpoint tests
│   ├── test_anomalies.py  # Anomaly detection tests
│   └── test_pipeline.py   # Pipeline schema tests
├── docs/
│   ├── DESIGN.md    # Architecture and AI-assisted decisions
│   └── CHOICES.md   # Three key architectural decisions
├── docker-compose.yml
├── Dockerfile
└── requirements.txt

## Running the Detection Pipeline

The detection pipeline requires a GPU. Run it in Google Colab:

```bash
# 1. Mount Google Drive with video clips
# 2. Clone repo in Colab
git clone https://github.com/jainlavanya14/store-intelligence.git
cd store-intelligence

# 3. Install dependencies
pip install ultralytics supervision opencv-python-headless

# 4. Run detection on all clips
python pipeline/detect.py

# Output: data/events.jsonl
```

Video clips should be placed in Google Drive at:
MyDrive/purplle/Store1/Store 1/   ← CAM 1 - zone.mp4, CAM 2 - zone.mp4, CAM 3 - entry.mp4, CAM 5 - billing.mp4
MyDrive/purplle/Store2/Store 2/   ← entry 1.mp4, entry 2.mp4, zone.mp4, billing_area.mp4

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /events/ingest` | Ingest batch of up to 500 events |
| `GET /stores/{id}/metrics` | Unique visitors, conversion rate, zone dwell, queue stats |
| `GET /stores/{id}/funnel` | Entry → Zone → Billing → Purchase funnel |
| `GET /stores/{id}/heatmap` | Zone visit frequency normalised 0-100 |
| `GET /stores/{id}/anomalies` | Active anomalies with severity and suggested action |
| `GET /health` | Service status and last event timestamp per store |

## Testing

```bash
# Run all tests
py -3.11 -m pytest tests/ -v

# Expected: 22 passed
```

## Ingesting Events

After `docker compose up --build`:

```bash
# Ingest generated events
python scripts/ingest_events.py data/events.jsonl

# Or ingest sample events for testing
python scripts/ingest_events.py data/sample_events.jsonl
```

## Tech Stack

- **Detection**: YOLOv8n + ByteTrack (Ultralytics + Supervision)
- **API**: FastAPI + Uvicorn
- **Storage**: SQLite (mounted as Docker volume)
- **Validation**: Pydantic v2
- **Tests**: pytest + httpx
- **Container**: Docker + docker-compose

## Store IDs

| Store | store_code | store_id |
|-------|------------|----------|
| Brigade Bangalore Store 1 | store_1076 | ST1076 |
| Brigade Bangalore Store 2 | store_1077 | ST1077 |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `store_intelligence.db` | Path to SQLite database file |

