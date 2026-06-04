import json, requests, sys

EVENTS_FILE = sys.argv[1] if len(sys.argv) > 1 else "data/events.jsonl"
API_URL     = "http://localhost:8000/events/ingest"
BATCH_SIZE  = 500

with open(EVENTS_FILE) as f:
    events = [json.loads(line) for line in f if line.strip()]

print(f"Total events to ingest: {len(events)}")

# Normalize old store IDs
def normalize(evt):
    # Old format used STORE_BLR_001, new format uses store_1076/ST1076
    sid = evt.get("store_id", "")
    if sid == "STORE_BLR_001":
        evt["store_id"]   = "ST1076"
        evt["store_code"] = "store_1076"
    return evt

events = [normalize(e) for e in events]

for i in range(0, len(events), BATCH_SIZE):
    batch = events[i:i+BATCH_SIZE]
    r = requests.post(API_URL, json={"events": batch})
    result = r.json()
    print(f"Batch {i//BATCH_SIZE + 1}: accepted={result['accepted']} rejected={result['rejected']} duplicate={result['duplicate']}")