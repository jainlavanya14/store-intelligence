# ALL tracking code goes here:
# - get_or_create_visitor()     (cross-camera dedup)
# - detect_direction()          (entry vs exit)
# - update_zone()               (zone enter/exit/dwell)
# - handle_billing_zone()       (queue depth + abandon)
# - is_staff()                  (uniform detection)

import cv2, uuid
import numpy as np
from datetime import datetime, timedelta
from sklearn.metrics.pairwise import cosine_similarity
from emit import emit_event, get_next_seq

ENTRY_LINE_CONFIG = {
    "CAM_ENTRY_01": {"axis": "y", "threshold": 300, "inward": "greater"}
    # load rest from store_layout.json
}

class VisitorTracker:
    def __init__(self, store_layout, pos_df):
        self.layout = store_layout
        self.pos_df = pos_df
        self.visitor_registry = {}      # cross-camera dedup
        self.track_positions = {}       # {track_id: [positions]}
        self.visitor_zones = {}         # {visitor_id: current_zone}
        self.zone_entry_times = {}      # {(visitor_id, zone): entry_time}
        self.zone_dwell_last_emit = {}  # {(visitor_id, zone): last_emit_time}
        self.billing_visitors = {}      # {visitor_id: billing_entry_time}
        self.exited_visitors = {}       # for re-entry detection

    def get_or_create_visitor(self, embedding, camera_id, timestamp, track_id):
        # Check re-entry from exited visitors first
        for vid, data in self.exited_visitors.items():
            gap = (timestamp - data["exit_time"]).seconds
            if gap < 300:  # within 5 minutes
                sim = cosine_similarity([embedding], [data["embedding"]])[0][0]
                if sim > 0.72:
                    del self.exited_visitors[vid]
                    self.visitor_registry[vid] = {
                        "embedding": embedding,
                        "last_seen_camera": camera_id,
                        "last_seen_time": timestamp,
                        "is_reentry": True
                    }
                    return vid, True  # (visitor_id, is_reentry)

        # Check cross-camera dedup
        for vid, data in self.visitor_registry.items():
            if data["last_seen_camera"] == camera_id:
                continue
            gap = abs((timestamp - data["last_seen_time"]).seconds)
            if gap > 30:
                continue
            sim = cosine_similarity([embedding], [data["embedding"]])[0][0]
            if sim > 0.75:
                data["last_seen_camera"] = camera_id
                data["last_seen_time"] = timestamp
                return vid, False

        new_id = f"VIS_{uuid.uuid4().hex[:6]}"
        self.visitor_registry[new_id] = {
            "embedding": embedding,
            "last_seen_camera": camera_id,
            "last_seen_time": timestamp,
            "is_reentry": False
        }
        return new_id, False

    def update_position(self, track_id, bbox, timestamp):
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        if track_id not in self.track_positions:
            self.track_positions[track_id] = []
        self.track_positions[track_id].append((cx, cy, timestamp))
        if len(self.track_positions[track_id]) > 30:
            self.track_positions[track_id].pop(0)

    def detect_direction(self, track_id, camera_id):
        positions = self.track_positions.get(track_id, [])
        if len(positions) < 8:
            return None
        config = ENTRY_LINE_CONFIG.get(camera_id, {})
        threshold = config.get("threshold", 300)
        first_y = positions[0][1]
        last_y = positions[-1][1]
        crossed = (first_y < threshold) != (last_y < threshold)
        if not crossed:
            return None
        return "ENTRY" if last_y > first_y else "EXIT"

    def get_zone(self, bbox, camera_id):
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        for zone in self.layout.get("zones", []):
            if camera_id not in zone.get("cameras", []):
                continue
            poly = np.array(zone["polygon"], dtype=np.int32)
            if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
                return zone["zone_id"]
        return None

    def update_zone(self, visitor_id, zone_id, timestamp, camera_id, store_id, conf):
        events = []
        prev_zone = self.visitor_zones.get(visitor_id)

        if prev_zone and prev_zone != zone_id:
            events.append(emit_event("ZONE_EXIT", visitor_id, camera_id,
                store_id, zone_id=prev_zone, timestamp=timestamp, confidence=conf,
                session_seq=get_next_seq(visitor_id)))
            if prev_zone == "BILLING":
                events += self.handle_billing_exit(visitor_id, timestamp, camera_id, store_id, conf)

        if zone_id != prev_zone:
            self.visitor_zones[visitor_id] = zone_id
            self.zone_entry_times[(visitor_id, zone_id)] = timestamp
            self.zone_dwell_last_emit[(visitor_id, zone_id)] = timestamp
            events.append(emit_event("ZONE_ENTER", visitor_id, camera_id,
                store_id, zone_id=zone_id, timestamp=timestamp, confidence=conf,
                session_seq=get_next_seq(visitor_id)))
            if zone_id == "BILLING":
                events += self.handle_billing_entry(visitor_id, timestamp, camera_id, store_id, conf)

        # ZONE_DWELL — every 30s
        last_emit = self.zone_dwell_last_emit.get((visitor_id, zone_id), timestamp)
        elapsed = (timestamp - last_emit).seconds
        if elapsed >= 30:
            events.append(emit_event("ZONE_DWELL", visitor_id, camera_id,
                store_id, zone_id=zone_id, dwell_ms=elapsed*1000,
                timestamp=timestamp, confidence=conf,
                session_seq=get_next_seq(visitor_id)))
            self.zone_dwell_last_emit[(visitor_id, zone_id)] = timestamp

        return events

    def handle_billing_entry(self, visitor_id, timestamp, camera_id, store_id, conf):
        self.billing_visitors[visitor_id] = timestamp
        return [emit_event("BILLING_QUEUE_JOIN", visitor_id, camera_id, store_id,
            zone_id="BILLING", timestamp=timestamp, confidence=conf,
            metadata={"queue_depth": len(self.billing_visitors)},
            session_seq=get_next_seq(visitor_id))]

    def handle_billing_exit(self, visitor_id, timestamp, camera_id, store_id, conf):
        self.billing_visitors.pop(visitor_id, None)
        window_end = timestamp + timedelta(minutes=5)
        txns = self.pos_df[
            (self.pos_df["timestamp"] >= timestamp) &
            (self.pos_df["timestamp"] <= window_end)
        ]
        if txns.empty:
            return [emit_event("BILLING_QUEUE_ABANDON", visitor_id, camera_id,
                store_id, timestamp=timestamp, confidence=conf,
                session_seq=get_next_seq(visitor_id))]
        return []

    def is_staff(self, frame, bbox, uniform_hsv_range):
        x1, y1, x2, y2 = bbox
        torso = frame[y1 + (y2-y1)//3 : y1 + 2*(y2-y1)//3, x1:x2]
        if torso.size == 0:
            return False
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, uniform_hsv_range[0], uniform_hsv_range[1])
        return (mask > 0).mean() > 0.40