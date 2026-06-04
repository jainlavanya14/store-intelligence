patch = '''
import cv2, json, uuid, os, glob, shutil
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from ultralytics import YOLO
import supervision as sv

OUTPUT_DIR   = "/content/store-intelligence/data"
MODEL_PATH   = "yolov8n.pt"
CONF_THRESH  = 0.30   # lowered to catch partial occlusions
FRAME_SKIP   = 3
DWELL_WINDOW = 30
GROUP_TIME_WINDOW = 2.0  # seconds — people entering within 2s = same group

STORES = {
    "STORE_1": {
        "store_code": "store_1076",
        "store_id":   "ST1076",
        "base_path":  "/content/drive/MyDrive/purplle/Store1/Store 1",
        "cameras": {
            "CAM 1 - zone.mp4":    {"camera_id": "CAM1", "type": "zone"},
            "CAM 2 - zone.mp4":    {"camera_id": "CAM2", "type": "zone"},
            "CAM 3 - entry.mp4":   {"camera_id": "CAM3", "type": "entry"},
            "CAM 5 - billing.mp4": {"camera_id": "CAM5", "type": "billing"},
        }
    },
    "STORE_2": {
        "store_code": "store_1077",
        "store_id":   "ST1077",
        "base_path":  "/content/drive/MyDrive/purplle/Store2/Store 2",
        "cameras": {
            "entry 1.mp4":      {"camera_id": "CAM1", "type": "entry"},
            "entry 2.mp4":      {"camera_id": "CAM2", "type": "entry"},
            "zone.mp4":         {"camera_id": "CAM3", "type": "zone"},
            "billing_area.mp4": {"camera_id": "CAM4", "type": "billing"},
        }
    }
}

def make_entry_event(store_code, camera_id, id_token, event_type,
                     timestamp, is_staff, confidence,
                     group_id=None, group_size=None):
    return {
        "event_type":      event_type,
        "id_token":        id_token,
        "store_code":      store_code,
        "camera_id":       camera_id,
        "event_timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000"),
        "is_staff":        is_staff,
        "confidence":      round(confidence, 3),
        "is_low_conf":     confidence < 0.45,  # flag low confidence
        "gender_pred":     None,
        "age_pred":        None,
        "age_bucket":      None,
        "is_face_hidden":  False,
        "group_id":        group_id,
        "group_size":      group_size,
    }

def make_zone_event(store_id, camera_id, track_id, event_type,
                    zone_id, zone_name, zone_type, timestamp, confidence):
    return {
        "event_type":      event_type,
        "track_id":        track_id,
        "store_id":        store_id,
        "camera_id":       camera_id,
        "zone_id":         zone_id,
        "zone_name":       zone_name,
        "zone_type":       zone_type,
        "is_revenue_zone": "Yes",
        "event_time":      timestamp.strftime("%Y-%m-%dT%H:%M:%S.000000"),
        "confidence":      round(confidence, 3),
        "is_low_conf":     confidence < 0.45,
        "gender":          None,
        "age":             None,
        "age_bucket":      None,
    }

def make_queue_event(store_id, camera_id, track_id, join_ts,
                     exit_ts, wait_secs, abandoned, position):
    return {
        "queue_event_id":        str(uuid.uuid4()),
        "event_type":            "queue_abandoned" if abandoned else "queue_completed",
        "track_id":              track_id,
        "store_id":              store_id,
        "camera_id":             camera_id,
        "zone_id":               f"{store_id}_BILLING_01",
        "zone_name":             "Billing Counter Queue",
        "zone_type":             "BILLING",
        "queue_join_ts":         join_ts.strftime("%Y-%m-%dT%H:%M:%S.000000"),
        "queue_served_ts":       None if abandoned else exit_ts.strftime("%Y-%m-%dT%H:%M:%S.000000"),
        "queue_exit_ts":         exit_ts.strftime("%Y-%m-%dT%H:%M:%S.000000"),
        "wait_seconds":          wait_secs,
        "queue_position_at_join": position,
        "abandoned":             abandoned,
        "gender":                None,
        "age":                   None,
        "age_bucket":            None,
    }

def classify_staff(track_history):
    """Staff present in >200 frames — moves continuously unlike customers."""
    return len(track_history) > 200

def assign_group(recent_entries, id_token, current_ts):
    """
    Group entry detection: people entering within GROUP_TIME_WINDOW seconds
    get the same group_id.
    recent_entries: list of (timestamp, id_token, group_id)
    Returns (group_id, group_size) or (None, None)
    """
    cutoff = current_ts.timestamp() - GROUP_TIME_WINDOW
    nearby = [(ts, vid, gid) for ts, vid, gid in recent_entries
              if ts.timestamp() > cutoff]

    if not nearby:
        return None, None

    # Use existing group_id if one exists
    existing_gid = next((gid for _, _, gid in nearby if gid), None)
    if existing_gid:
        group_size = len(nearby) + 1
        return existing_gid, group_size
    else:
        new_gid = f"G_{uuid.uuid4().hex[:4]}"
        # Retroactively assign group_id to recent entries
        for i, (ts, vid, _) in enumerate(nearby):
            recent_entries[i] = (ts, vid, new_gid)
        return new_gid, len(nearby) + 1

def process_video(video_path, cam_meta, store_code, store_id, clip_start):
    model   = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    camera_id = cam_meta["camera_id"]
    cam_type  = cam_meta["type"]

    events        = []
    track_history = {}
    zone_enter_ts = {}
    visitor_map   = {}
    exited_ids    = set()
    billing_join  = {}
    recent_entries = []  # for group detection
    
    # Cross-camera dedup: store visitor fingerprints (cx, cy at entry)
    seen_fingerprints = {}  # fingerprint → visitor_id

    frame_no = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_no += 1
        if frame_no % FRAME_SKIP != 0:
            continue

        current_ts = clip_start + timedelta(seconds=frame_no / fps)

        results = model(frame, classes=[0], conf=CONF_THRESH, verbose=False)[0]
        dets    = sv.Detections.from_ultralytics(results)
        dets    = tracker.update_with_detections(dets)

        frame_h, frame_w = frame.shape[:2]
        ENTRY_LINE_Y = frame_h * 0.5

        tracker_ids = dets.tracker_id if dets.tracker_id is not None else []

        for i, track_id in enumerate(tracker_ids):
            if track_id is None:
                continue

            confidence = float(dets.confidence[i]) if dets.confidence is not None else 0.5
            bbox = dets.xyxy[i]
            x1, y1, x2, y2 = bbox
            cx, cy = (x1+x2)/2, (y1+y2)/2

            if track_id not in track_history:
                track_history[track_id] = []
            track_history[track_id].append((frame_no, cx, cy))

            is_staff = classify_staff(track_history[track_id])

            if track_id not in visitor_map:
                visitor_map[track_id] = f"ID_{uuid.uuid4().hex[:6]}"
            vid = visitor_map[track_id]

            # ── Entry/Exit ────────────────────────────────────────────────
            if cam_type == "entry" and len(track_history[track_id]) >= 2:
                prev_cy = track_history[track_id][-2][2]

                if prev_cy < ENTRY_LINE_Y <= cy:
                    # Group detection
                    group_id, group_size = assign_group(recent_entries, vid, current_ts)
                    recent_entries.append((current_ts, vid, group_id))
                    # Keep only last 5 seconds
                    cutoff = current_ts.timestamp() - 5.0
                    recent_entries = [(ts, v, g) for ts, v, g in recent_entries
                                      if ts.timestamp() > cutoff]

                    etype = "reentry" if vid in exited_ids else "entry"
                    events.append(make_entry_event(
                        store_code, camera_id, vid, etype,
                        current_ts, is_staff, confidence,
                        group_id, group_size
                    ))

                elif prev_cy > ENTRY_LINE_Y >= cy:
                    events.append(make_entry_event(
                        store_code, camera_id, vid, "exit",
                        current_ts, is_staff, confidence
                    ))
                    exited_ids.add(vid)

            # ── Zone tracking ─────────────────────────────────────────────
            if cam_type == "zone":
                zone_id   = f"{store_id}_Z_{camera_id}"
                zone_name = f"Zone {camera_id}"
                if track_id not in zone_enter_ts:
                    zone_enter_ts[track_id] = current_ts
                    events.append(make_zone_event(
                        store_id, camera_id, track_id,
                        "zone_entered", zone_id, zone_name,
                        "SHELF", current_ts, confidence
                    ))

            # ── Billing tracking ──────────────────────────────────────────
            if cam_type == "billing":
                if track_id not in billing_join:
                    billing_join[track_id] = (current_ts, len(billing_join) + 1)

        # Zone exits
        active_ids = set(int(t) for t in tracker_ids if t is not None)
        for track_id, enter_ts in list(zone_enter_ts.items()):
            if track_id not in active_ids:
                zone_id   = f"{store_id}_Z_{camera_id}"
                zone_name = f"Zone {camera_id}"
                events.append(make_zone_event(
                    store_id, camera_id, track_id,
                    "zone_exited", zone_id, zone_name,
                    "SHELF", current_ts, 0.8
                ))
                del zone_enter_ts[track_id]

        # Billing exits
        for track_id, (join_ts, position) in list(billing_join.items()):
            if track_id not in active_ids:
                wait = int((current_ts - join_ts).total_seconds())
                abandoned = wait > 120
                events.append(make_queue_event(
                    store_id, camera_id, track_id,
                    join_ts, current_ts, wait, abandoned, position
                ))
                del billing_join[track_id]

        if frame_no % 300 == 0:
            print(f"  Frame {frame_no} | Events: {len(events)}")

    cap.release()
    return events


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_events = []
    clip_start = datetime(2026, 4, 10, 10, 0, 0)

    for store_key, store_info in STORES.items():
        store_code = store_info["store_code"]
        store_id   = store_info["store_id"]
        base_path  = store_info["base_path"]

        for filename, cam_meta in store_info["cameras"].items():
            video_path = os.path.join(base_path, filename)
            if not os.path.exists(video_path):
                print(f"⚠️  Not found: {video_path}")
                continue
            print(f"\\nProcessing: {filename} ({store_key}) → {cam_meta[\'type\']}")
            evts = process_video(video_path, cam_meta, store_code, store_id, clip_start)
            all_events.extend(evts)
            print(f"  → {len(evts)} events")

    out = f"{OUTPUT_DIR}/events.jsonl"
    with open(out, "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\\n")

    shutil.copy(out, "/content/drive/MyDrive/purplle/events.jsonl")
    print(f"\\n✅ Total: {len(all_events)} events → {out}")
'''

with open("/content/store-intelligence/pipeline/detect.py", "w") as f:
    f.write(patch)
print("✅ detect.py updated with edge case handling")