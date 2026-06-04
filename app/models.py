from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

# Entry/Exit event
class EntryExitEvent(BaseModel):
    event_type: str               # "entry" or "exit"
    id_token: str                 # visitor ID
    store_code: str
    camera_id: str
    event_timestamp: datetime
    is_staff: bool = False
    gender_pred: Optional[str] = None
    age_pred: Optional[int] = None
    age_bucket: Optional[str] = None
    is_face_hidden: bool = False
    group_id: Optional[str] = None
    group_size: Optional[int] = None

# Zone event
class ZoneEvent(BaseModel):
    event_type: str               # "zone_entered" or "zone_exited"
    track_id: int
    store_id: str
    camera_id: str
    zone_id: str
    zone_name: str
    zone_type: str
    is_revenue_zone: Optional[str] = None
    event_time: datetime
    zone_hotspot_x: Optional[float] = None
    zone_hotspot_y: Optional[float] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    age_bucket: Optional[str] = None

# Queue event
class QueueEvent(BaseModel):
    queue_event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str               # "queue_completed" or "queue_abandoned"
    track_id: int
    store_id: str
    camera_id: str
    zone_id: str
    zone_name: str
    zone_type: str
    queue_join_ts: datetime
    queue_served_ts: Optional[datetime] = None
    queue_exit_ts: Optional[datetime] = None
    wait_seconds: Optional[int] = None
    queue_position_at_join: Optional[int] = None
    abandoned: bool = False
    gender: Optional[str] = None
    age: Optional[int] = None
    age_bucket: Optional[str] = None

# Generic ingest — accepts any of the above
from typing import Union, Any
class IngestRequest(BaseModel):
    events: list[dict]

class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    duplicate: int
    errors: list[dict] = []