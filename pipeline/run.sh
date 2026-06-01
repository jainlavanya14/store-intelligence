#!/bin/bash
# Run this on Colab or any machine with GPU
# Usage: bash run.sh

set -e

echo "Installing dependencies..."
pip install ultralytics supervision scikit-learn opencv-python-headless pandas -q

echo "Running detection pipeline..."
python pipeline/detect.py \
  --clips_dir ./data/clips \
  --store_layout ./data/store_layout.json \
  --output ./data/events.jsonl

echo "Done! Events written to data/events.jsonl"
echo "Event count: $(wc -l < ./data/events.jsonl)"