# ALL event emission code goes here

import uuid
from datetime import datetime, timedelta

session_seq_counter = {}

def get_next_seq(visitor_id):
    session_seq_counter[visitor_id] = session_seq_counter.get(visitor_id, 0) + 1
    return session_seq_counter[visitor_id]

def compute_confidence(raw_conf, bbox, frame_shape):
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = bbox
    edge_penalty = 0.15 if (x1<20 or x2>w-20 or y1<20 or y2>h-20) else 0.0
    size_ratio = (x2-x1)*(y2-y1) / (w*h)
    size_penalty = 0.1 if size_ratio < 0.005 else 0.0
    return round(max(0.1, raw_conf - edge_penalty - size_penalty), 2)

def get_embedding(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return [0.0] * 512
    crop_resized = cv2.resize(crop, (64, 128))
    return (crop_resized.flatten() / 255.0).tolist()

def emit_event(event_type, visitor_id, camera_id, store_id,
               zone_id=None, dwell_ms=0, is_staff=False,
               confidence=1.0, timestamp=None, metadata=None,
               session_seq=1):
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") if timestamp else "",
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": metadata or {
            "queue_depth": None,
            "sku_zone": zone_id,
            "session_seq": session_seq
        }
    }