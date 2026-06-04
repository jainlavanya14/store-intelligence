import uuid, time, logging, json
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from .database import init_db, get_conn
from .models import IngestRequest
from .ingestion import ingest_events
from .metrics import get_metrics
from .funnel import get_funnel
from .anomalies import get_anomalies
from .health import get_health

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("store-intelligence")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Store Intelligence API", lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    store_id = request.path_params.get("store_id", "-")
    start    = time.time()
    response = await call_next(request)
    latency  = int((time.time() - start) * 1000)
    logger.info(json.dumps({
        "trace_id": trace_id, "store_id": store_id,
        "endpoint": str(request.url.path),
        "latency_ms": latency, "status_code": response.status_code
    }))
    return response

@app.post("/events/ingest")
async def ingest(req: IngestRequest):
    if len(req.events) > 500:
        raise HTTPException(status_code=422, detail="Batch exceeds 500 events")
    return ingest_events(req)

@app.get("/stores/{store_id}/metrics")
async def metrics(store_id: str):
    return get_metrics(store_id)

@app.get("/stores/{store_id}/funnel")
async def funnel(store_id: str):
    return get_funnel(store_id)

@app.get("/stores/{store_id}/heatmap")
async def heatmap(store_id: str):
    try:
        # handle both formats: store_1076 and ST1076
        store_alt = store_id.replace("store_", "ST").upper()
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT zone_id, zone_name, zone_type,
                       COUNT(*) as visits
                FROM zone_events
                WHERE (store_id=? OR store_id=?) AND event_type='zone_entered'
                GROUP BY zone_id, zone_name, zone_type
            """, (store_id, store_alt)).fetchall()
        zones = [{"zone_id": r["zone_id"], "zone_name": r["zone_name"],
                   "zone_type": r["zone_type"], "visits": r["visits"]} for r in rows]
        max_v = max((z["visits"] for z in zones), default=1)
        for z in zones:
            z["normalised"] = round(z["visits"] / max_v * 100)
        data_confidence = "LOW" if sum(z["visits"] for z in zones) < 20 else "OK"
        return {"store_id": store_id, "data_confidence": data_confidence, "zones": zones}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.get("/stores/{store_id}/anomalies")
async def anomalies(store_id: str):
    return get_anomalies(store_id)

@app.get("/health")
async def health():
    return get_health()