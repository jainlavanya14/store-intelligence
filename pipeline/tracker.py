"""
tracker.py — Re-ID and visitor session tracking logic.
Wraps ByteTrack and adds cross-frame identity persistence.
"""
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

class VisitorTracker:
    """
    Manages track_id → visitor_id mapping with re-entry detection.
    Uses bounding box trajectory similarity for Re-ID when a track is lost.
    """
    def __init__(self, reentry_window_seconds=300):
        self.track_to_visitor   = {}       # track_id → visitor_id
        self.visitor_exits      = {}       # visitor_id → exit timestamp
        self.track_history      = defaultdict(list)  # track_id → [(frame, cx, cy)]
        self.exit_trajectories  = {}       # visitor_id → last known (cx, cy)
        self.reentry_window     = reentry_window_seconds

    def get_or_create_visitor(self, track_id: int, cx: float, cy: float,
                               frame_no: int, current_ts: datetime) -> tuple[str, bool]:
        """
        Returns (visitor_id, is_reentry).
        Checks if this track matches a recently exited visitor via position similarity.
        """
        self.track_history[track_id].append((frame_no, cx, cy))

        if track_id in self.track_to_visitor:
            return self.track_to_visitor[track_id], False

        # Check for re-entry: find recently exited visitor near this position
        reentry_vid = self._find_reentry_candidate(cx, cy, current_ts)
        if reentry_vid:
            self.track_to_visitor[track_id] = reentry_vid
            del self.visitor_exits[reentry_vid]  # no longer exited
            return reentry_vid, True

        # New visitor
        vid = f"ID_{uuid.uuid4().hex[:6]}"
        self.track_to_visitor[track_id] = vid
        return vid, False

    def record_exit(self, track_id: int, current_ts: datetime):
        """Mark a visitor as exited — needed for re-entry detection."""
        vid = self.track_to_visitor.get(track_id)
        if vid:
            self.visitor_exits[vid] = current_ts
            if track_id in self.track_history and self.track_history[track_id]:
                last = self.track_history[track_id][-1]
                self.exit_trajectories[vid] = (last[1], last[2])  # cx, cy

    def _find_reentry_candidate(self, cx: float, cy: float,
                                 current_ts: datetime, dist_threshold=100) -> str | None:
        """
        Find a recently exited visitor whose last position is close to (cx, cy).
        Returns visitor_id if found, else None.
        """
        for vid, exit_ts in list(self.visitor_exits.items()):
            age = (current_ts - exit_ts).total_seconds()
            if age > self.reentry_window:
                del self.visitor_exits[vid]
                continue
            last_pos = self.exit_trajectories.get(vid)
            if last_pos:
                dist = ((cx - last_pos[0])**2 + (cy - last_pos[1])**2) ** 0.5
                if dist < dist_threshold:
                    return vid
        return None

    def is_staff(self, track_id: int, staff_threshold=200) -> bool:
        """
        Heuristic: tracks present in >200 frames are likely staff.
        Staff move through all zones continuously unlike customers.
        """
        return len(self.track_history.get(track_id, [])) > staff_threshold

    def get_session_length(self, track_id: int) -> int:
        """Returns number of frames this track has been active."""
        return len(self.track_history.get(track_id, []))