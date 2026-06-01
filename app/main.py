from fastapi import FastAPI
from app.ingestion import router as ingest_router
from app.metrics import router as metrics_router
from app.funnel import router as funnel_router
from app.anomalies import router as anomalies_router
from app.health import router as health_router
import logging, uuid

app = FastAPI(title="Store Intelligence API")

# Structured logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    import time
    start = time.time()
    response = await call_next(request)
    latency = round((time.time() - start) * 1000)
    logging.info(f"trace_id={trace_id} endpoint={request.url.path} "
                 f"latency_ms={latency} status={response.status_code}")
    return response

app.include_router(ingest_router)
app.include_router(metrics_router)
app.include_router(funnel_router)
app.include_router(anomalies_router)
app.include_router(health_router)