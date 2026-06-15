from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime
import uuid
import os

app = FastAPI(title="Medallion Staging API", version="1.0.0")

# ── In-memory staging store ───────────────────────────────────────────────────
# Holds batches until FDF Web Activity pulls them.
# Key = batch_id, Value = batch payload dict
staging_store: Dict[str, dict] = {}

# ── Auth ──────────────────────────────────────────────────────────────────────
API_KEY = os.getenv("API_KEY", "change-me-in-render-env")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


# ── Schemas ───────────────────────────────────────────────────────────────────
class Record(BaseModel):
    """Single record produced by the Python generator."""
    id: str
    payload: Dict[str, Any]
    generated_at: Optional[str] = None


class BatchPush(BaseModel):
    """Envelope the Python script sends every 50 minutes."""
    source: str               # e.g. "python-generator-v1"
    records: List[Record]


class BatchResponse(BaseModel):
    batch_id: str
    record_count: int
    received_at: str
    status: str


# ── POST /batches — Python generator pushes data here ─────────────────────────
@app.post("/batches", response_model=BatchResponse, dependencies=[Depends(verify_api_key)])
def push_batch(batch: BatchPush):
    """
    Called by the Python generator every 50 minutes.
    Stages the batch in memory so FDF can pull it later.
    """
    batch_id = str(uuid.uuid4())
    received_at = datetime.utcnow().isoformat()

    staging_store[batch_id] = {
        "batch_id": batch_id,
        "source": batch.source,
        "records": [r.dict() for r in batch.records],
        "record_count": len(batch.records),
        "received_at": received_at,
        "pulled": False,          # FDF marks this True after pulling
    }

    return BatchResponse(
        batch_id=batch_id,
        record_count=len(batch.records),
        received_at=received_at,
        status="staged",
    )


# ── GET /batches — FDF Web Activity calls this every 1 hour ──────────────────
@app.get("/batches", dependencies=[Depends(verify_api_key)])
def pull_batches(mark_pulled: bool = True):
    """
    Called by FDF Web Activity as part of the pipeline.
    Returns all un-pulled batches. FDF Copy Activity then
    writes the records into OneLake Bronze.
    """
    unpulled = {
        bid: b for bid, b in staging_store.items() if not b["pulled"]
    }

    if not unpulled:
        return {"batches": [], "total_records": 0, "message": "No new data"}

    total_records = sum(b["record_count"] for b in unpulled.values())

    if mark_pulled:
        for bid in unpulled:
            staging_store[bid]["pulled"] = True

    return {
        "batches": list(unpulled.values()),
        "total_records": total_records,
        "pulled_at": datetime.utcnow().isoformat(),
    }


# ── GET /batches/{batch_id} — inspect a specific batch ───────────────────────
@app.get("/batches/{batch_id}", dependencies=[Depends(verify_api_key)])
def get_batch(batch_id: str):
    if batch_id not in staging_store:
        raise HTTPException(status_code=404, detail="Batch not found")
    return staging_store[batch_id]


# ── GET /health — Render health check + FDF connectivity test ─────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "staged_batches": len(staging_store),
        "unpulled_batches": sum(1 for b in staging_store.values() if not b["pulled"]),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── DELETE /batches — optional cleanup ───────────────────────────────────────
@app.delete("/batches", dependencies=[Depends(verify_api_key)])
def clear_pulled_batches():
    """Remove already-pulled batches to free memory."""
    before = len(staging_store)
    pulled_ids = [bid for bid, b in staging_store.items() if b["pulled"]]
    for bid in pulled_ids:
        del staging_store[bid]
    return {"deleted": len(pulled_ids), "remaining": len(staging_store)}
