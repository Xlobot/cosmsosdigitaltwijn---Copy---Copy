"""
Mission Intelligence Standalone Server
Separate, independent server for Mission Intelligence module.
Connects to Digital Twin via REST API (read-only).
"""

import os
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mission_intelligence import get_mi_api

app = FastAPI(
    title="COSMOS Mission Intelligence API",
    description="Cognitive Decision Support System for Satellite Operations",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Digital Twin configuration
DIGITAL_TWIN_URL = os.getenv("DIGITAL_TWIN_URL", "http://127.0.0.1:8000")

# Initialize Mission Intelligence API
_mi_api = None


@app.on_event("startup")
async def startup_event():
    """Initialize Mission Intelligence on startup."""
    global _mi_api
    print("[Mission Intelligence] Initializing Mission Intelligence API...")
    _mi_api = await get_mi_api()
    print("[Mission Intelligence] Mission Intelligence API initialized.")
    print(f"[Mission Intelligence] Digital Twin URL: {DIGITAL_TWIN_URL}")


class MIAssessmentRequest(BaseModel):
    row_index: int = 0
    horizon_minutes: int = 60
    run_scenarios: bool = True


class MIDecisionRequest(BaseModel):
    recommendation_id: str
    decision: str  # "accepted", "rejected", "deferred"
    reasoning: str = None
    operator: str = "system"


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "COSMOS Mission Intelligence",
        "status": "ONLINE",
        "digital_twin_url": DIGITAL_TWIN_URL
    }


@app.get("/api/health")
async def health():
    """Check health of Mission Intelligence and Digital Twin connection."""
    try:
        if _mi_api:
            health = await _mi_api.check_health()
            return health
        else:
            return {
                "mission_intelligence_status": "INITIALIZING",
                "digital_twin_url": DIGITAL_TWIN_URL
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/assess")
async def assess(req: MIAssessmentRequest):
    """
    Get complete Mission Intelligence assessment.
    """
    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")

        assessment = await _mi_api.get_full_assessment(
            row_index=req.row_index,
            horizon_minutes=req.horizon_minutes,
            run_scenarios=req.run_scenarios
        )
        return assessment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")


@app.post("/api/decision")
async def submit_decision(req: MIDecisionRequest):
    """Submit operator decision on a recommendation."""
    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")

        result = await _mi_api.submit_decision(
            recommendation_id=req.recommendation_id,
            decision=req.decision,
            reasoning=req.reasoning,
            operator=req.operator
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {str(e)}")


@app.get("/api/history")
async def get_history(
    limit: int = Query(10, description="Maximum number of entries"),
    operator: str = Query(None, description="Filter by operator")
):
    """Get decision history."""
    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")

        history = _mi_api.get_decision_history(limit=limit, operator=operator)
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


if __name__ == "__main__":
    print("[Mission Intelligence] Starting Mission Intelligence Server...")
    print(f"[Mission Intelligence] Digital Twin URL: {DIGITAL_TWIN_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
