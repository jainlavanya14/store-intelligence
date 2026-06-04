import json, requests, sys

EVENTS_FILE = sys.argv[1] if len(sys.argv) > 1 else "data/events.jsonl"
API_URL     = "http://localhost:8000/events/ingest"
BATCH_SIZE  = 500

with open(EVENTS_FILE) as f:
    events = [json.loads(line) for line in f if line.strip()]

print(f"Total events to ingest: {len(events)}")

for i in range(0, len(events), BATCH_SIZE):
    batch = events[i:i+BATCH_SIZE]
    r = requests.post(API_URL, json={"events": batch})
    print(f"Batch {i//BATCH_SIZE + 1}: {r.json()}")