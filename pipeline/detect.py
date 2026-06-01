# PROMPT: Write a YOLOv8 + ByteTrack detection pipeline for retail CCTV
# CHANGES MADE: Added direction detection, confidence penalty, empty-frame guard

import cv2, json, argparse
from ultralytics import YOLO
import supervision as sv
from tracker import VisitorTracker
from emit import emit_event, get_next_seq

def process_clip(clip_path, camera_id, store_id, store_layout, clip_start_time, pos_df):
    model = YOLO("yolov8m.pt")
    tracker = VisitorTracker(store_layout, pos_df)
    byte_tracker = sv.ByteTrack()
    
    cap = cv2.VideoCapture(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    events = []
    frame_num = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # --- Empty frame guard ---
        results = model(frame, classes=[0], verbose=False)
        detections = sv.Detections.from_ultralytics(results[0])

        if len(detections) == 0:
            frame_num += 1
            continue  # empty period — no crash, just skip

        tracked = byte_tracker.update_with_detections(detections)
        timestamp = clip_start_time + timedelta(seconds=frame_num / fps)

        for i, track_id in enumerate(tracked.tracker_id):
            bbox = tracked.xyxy[i].astype(int)
            raw_conf = float(tracked.confidence[i])
            conf = compute_confidence(raw_conf, bbox, frame.shape)
            crop_emb = get_embedding(frame, bbox)

            # Get or create visitor_id (cross-camera dedup here)
            visitor_id = tracker.get_or_create_visitor(
                crop_emb, camera_id, timestamp, track_id
            )

            # Direction detection
            tracker.update_position(track_id, bbox, timestamp)
            direction = tracker.detect_direction(track_id, camera_id)

            if direction == "ENTRY":
                events.append(emit_event("ENTRY", visitor_id, camera_id,
                    store_id, timestamp=timestamp, confidence=conf,
                    session_seq=get_next_seq(visitor_id)))

            elif direction == "EXIT":
                events.append(emit_event("EXIT", visitor_id, camera_id,
                    store_id, timestamp=timestamp, confidence=conf,
                    session_seq=get_next_seq(visitor_id)))

            # Zone events
            zone = tracker.get_zone(bbox, camera_id)
            if zone:
                new_events = tracker.update_zone(
                    visitor_id, zone, timestamp, camera_id, store_id, conf
                )
                events.extend(new_events)

        frame_num += 1

    cap.release()
    return events

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips_dir")
    parser.add_argument("--store_layout")
    parser.add_argument("--output")
    args = parser.parse_args()

    import pandas as pd
    from datetime import datetime, timedelta
    from pathlib import Path
    import json

    layout = json.load(open(args.store_layout))
    pos_df = pd.read_csv("pos_transactions.csv", parse_dates=["timestamp"])

    all_events = []
    for clip_path in Path(args.clips_dir).glob("*.mp4"):
        # Parse store_id + camera_id from filename e.g. STORE_BLR_002_CAM_ENTRY_01.mp4
        parts = clip_path.stem.split("_CAM_")
        store_id = parts[0]
        camera_id = "CAM_" + parts[1]
        clip_start = datetime(2026, 3, 3, 10, 0, 0)  # from dataset metadata

        events = process_clip(str(clip_path), camera_id, store_id,
                              layout, clip_start, pos_df)
        all_events.extend(events)

    with open(args.output, "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")

    print(f"Done. {len(all_events)} events written to {args.output}")