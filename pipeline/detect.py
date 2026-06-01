"""
Detection pipeline using YOLOv8 + ByteTrack.
Run in Colab (GPU). Outputs events.jsonl per video clip.
"""
import cv2, json, uuid, time
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from ultralytics import YOLO
import supervision as sv

# ── Config ────────────────────────────────────────────────────────────────────
DRIVE_BASE   = "/content/drive/MyDrive/purplle/clips/CCTV Footage"
OUTPUT_DIR   = "/content/store-intelligence/data"
STORE_ID     = "STORE_BLR_001"
MODEL_PATH   = "yolov8n.pt"          # downloads automatically
CONF_THRESH  = 0.35
FRAME_SKIP   = 3                     # process every 3rd frame (speeds up 3x)
DWELL_WINDOW = 30                    # seconds before emitting ZONE_DWELL

# Camera → zone mapping (fill from your store_layout.json)
CAMERA_META = {
    "entry":   {"camera_id": "CAM_ENTRY_01",   "zone": None},
    "floor":   {"camera_id": "CAM_FLOOR_01",   "zone": "MAIN_FLOOR"},
    "billing": {"camera_id": "CAM_BILLING_01", "zone": "BILLING"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_event(store_id, camera_id, visitor_id, event_type,
               timestamp, zone_id, dwell_ms, is_staff, confidence, metadata):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   is_staff,
        "confidence": round(confidence, 3),
        "metadata":   metadata,
    }

def classify_staff(bbox, frame_h, frame_w, track_history):
    """
    Heuristic staff detection:
    - Staff appear in >60% of frames (high presence ratio)
    - Staff bbox often in lower region (behind counter)
    This is a simple baseline; can be replaced with a VLM call.
    """
    if len(track_history) > 200:   # seen in many frames → likely staff
        return True
    return False

def get_direction(prev_cy, curr_cy, camera_type):
    """Entry camera: person moving INTO store = y increases (top→bottom)"""
    if camera_type == "entry":
        return "ENTRY" if curr_cy > prev_cy else "EXIT"
    return None

# ── Core processor ────────────────────────────────────────────────────────────
def process_video(video_path: str, camera_type: str, clip_start_time: datetime):
    model   = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack()
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    
    camera_id  = CAMERA_META[camera_type]["camera_id"]
    zone_id    = CAMERA_META[camera_type]["zone"]
    
    events         = []
    track_history  = {}   # track_id → list of (frame_no, cx, cy)
    zone_enter_ts  = {}   # track_id → datetime they entered zone
    last_dwell_ts  = {}   # track_id → last ZONE_DWELL emit time
    visitor_map    = {}   # track_id → visitor_id
    exited_ids     = {}   # visitor_id → exit timestamp (for re-entry)
    session_seq    = {}   # visitor_id → event count
    
    frame_no = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_no += 1
        if frame_no % FRAME_SKIP != 0:
            continue
        
        current_ts = clip_start_time + timedelta(seconds=frame_no / fps)
        
        # ── Detect people only (class 0) ──────────────────────────────────────
        results  = model(frame, classes=[0], conf=CONF_THRESH, verbose=False)[0]
        dets     = sv.Detections.from_ultralytics(results)
        dets     = tracker.update_with_detections(dets)
        
        frame_h, frame_w = frame.shape[:2]
        ENTRY_LINE_Y = frame_h * 0.5   # horizontal line at midpoint
        
        tracker_ids = dets.tracker_id if dets.tracker_id is not None else []
        for i, track_id in enumerate(tracker_ids):
            if track_id is None:
                continue
            
            bbox       = dets.xyxy[i]
            confidence = float(dets.confidence[i]) if dets.confidence is not None else 0.5
            x1,y1,x2,y2 = bbox
            cx, cy = (x1+x2)/2, (y1+y2)/2
            
            # Track history
            if track_id not in track_history:
                track_history[track_id] = []
            track_history[track_id].append((frame_no, cx, cy))
            
            # Staff classification
            is_staff = classify_staff(bbox, frame_h, frame_w, track_history[track_id])
            
            # Assign visitor_id
            if track_id not in visitor_map:
                visitor_map[track_id] = f"VIS_{uuid.uuid4().hex[:6]}"
                session_seq[visitor_map[track_id]] = 0
            
            vid = visitor_map[track_id]
            
            def emit(event_type, dwell_ms=0, extra_meta=None):
                session_seq[vid] += 1
                meta = {"queue_depth": None, "sku_zone": zone_id, "session_seq": session_seq[vid]}
                if extra_meta:
                    meta.update(extra_meta)
                events.append(make_event(
                    STORE_ID, camera_id, vid, event_type,
                    current_ts, zone_id, dwell_ms, is_staff, confidence, meta
                ))
            
            # ── Entry/Exit detection (entry camera only) ──────────────────────
            if camera_type == "entry" and len(track_history[track_id]) >= 2:
                prev_cy = track_history[track_id][-2][2]
                
                # Crossed entry line downward = ENTRY
                if prev_cy < ENTRY_LINE_Y <= cy:
                    # Check for re-entry
                    if vid in exited_ids:
                        emit("REENTRY")
                    else:
                        emit("ENTRY")
                
                # Crossed entry line upward = EXIT
                elif prev_cy > ENTRY_LINE_Y >= cy:
                    emit("EXIT")
                    exited_ids[vid] = current_ts
            
            # ── Zone dwell (floor/billing cameras) ────────────────────────────
            if camera_type in ("floor", "billing") and zone_id:
                if track_id not in zone_enter_ts:
                    zone_enter_ts[track_id] = current_ts
                    emit("ZONE_ENTER")
                
                dwell_secs = (current_ts - zone_enter_ts[track_id]).total_seconds()
                last_dwell = last_dwell_ts.get(track_id)
                
                if dwell_secs >= DWELL_WINDOW:
                    if last_dwell is None or (current_ts - last_dwell).total_seconds() >= DWELL_WINDOW:
                        emit("ZONE_DWELL", dwell_ms=int(dwell_secs*1000))
                        last_dwell_ts[track_id] = current_ts
            
            # ── Billing queue ─────────────────────────────────────────────────
            if camera_type == "billing":
                billing_count = len([t for t in dets.tracker_id if t is not None])
                if billing_count > 2:
                    emit("BILLING_QUEUE_JOIN", extra_meta={"queue_depth": billing_count})
        
        # Emit ZONE_EXIT for tracks that disappeared
        active_ids = set(dets.tracker_id) if dets.tracker_id is not None else set()
        for track_id, enter_ts in list(zone_enter_ts.items()):
            if track_id not in active_ids and camera_type in ("floor", "billing"):
                vid      = visitor_map.get(track_id, f"VIS_{track_id}")
                dwell_ms = int((current_ts - enter_ts).total_seconds() * 1000)
                session_seq[vid] = session_seq.get(vid, 0) + 1
                events.append(make_event(
                    STORE_ID, camera_id, vid, "ZONE_EXIT",
                    current_ts, zone_id, dwell_ms, False, 0.8,
                    {"queue_depth": None, "sku_zone": zone_id, "session_seq": session_seq[vid]}
                ))
                del zone_enter_ts[track_id]
        
        if frame_no % 300 == 0:
            print(f"  Frame {frame_no} | Events so far: {len(events)}")
    
    cap.release()
    return events


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import glob
    
    videos = glob.glob(f"{DRIVE_BASE}/*.mp4")
    print(f"Found {len(videos)} videos")
    
    all_events = []
    clip_start = datetime(2026, 4, 10, 10, 0, 0)   # assume store opens 10am
    
    for video_path in videos:
        name = Path(video_path).stem.lower()
        if   "entry" in name: cam_type = "entry"
        elif "billing" in name or "bill" in name: cam_type = "billing"
        else: cam_type = "floor"
        
        print(f"\nProcessing: {video_path} → type={cam_type}")
        evts = process_video(video_path, cam_type, clip_start)
        all_events.extend(evts)
        print(f"  → {len(evts)} events emitted")
    
    out = f"{OUTPUT_DIR}/events.jsonl"
    with open(out, "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")
    
    print(f"\n✅ Total events: {len(all_events)} → {out}")
    
    # Copy to Drive for persistence
    import shutil
    shutil.copy(out, f"{DRIVE_BASE}/events.jsonl")
    print(f"✅ Saved to Drive: {DRIVE_BASE}/events.jsonl")