#!/bin/bash
# run.sh — Process all CCTV clips and emit events to data/events.jsonl
# Usage: bash pipeline/run.sh
# Requirements: pip install ultralytics supervision opencv-python-headless

set -e

echo "=== Store Intelligence Detection Pipeline ==="
echo "Starting at $(date)"

# Run detection
python pipeline/detect.py

echo ""
echo "=== Detection complete ==="
echo "Events saved to data/events.jsonl"
echo ""

# Ingest into API if running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "=== API detected — ingesting events ==="
    python scripts/ingest_events.py data/events.jsonl
    echo "=== Ingest complete ==="
else
    echo "API not running — start with 'docker compose up' then run:"
    echo "  python scripts/ingest_events.py data/events.jsonl"
fi

echo "Done at $(date)"