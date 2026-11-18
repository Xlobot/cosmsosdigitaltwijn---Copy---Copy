"""
Mission Intelligence Standalone Server
Separate, independent server for Mission Intelligence module.
Connects to Digital Twin via REST API (read-only).
"""

import os
import uvicorn
from fastapi import FastAPI, Query, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mission_intelligence import get_mi_api
from cosmos_security import (
    require_role,
    require_service_key_or_admin,
    ROLE_VIEWER,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_ADMIN,
    log_access_denied
)

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

@app.get("/healthz", summary="Public Health Check")
async def healthz():
    """Minimal unauthenticated health check returning status ok."""
    return {"status": "ok"}

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
async def root(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Root endpoint."""
    return {
        "service": "COSMOS Mission Intelligence",
        "status": "ONLINE",
        "digital_twin_url": DIGITAL_TWIN_URL
    }


@app.get("/api/health")
async def health(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Check health of Mission Intelligence and Digital Twin connection."""
    try:
        if _mi_api:
            health_data = await _mi_api.check_health()
            return health_data
        else:
            return {
                "mission_intelligence_status": "INITIALIZING",
                "digital_twin_url": DIGITAL_TWIN_URL
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/assess")
async def assess(req: MIAssessmentRequest, auth: dict = Depends(require_role(ROLE_ANALYST))):
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
async def submit_decision(req: MIDecisionRequest, auth: dict = Depends(require_role(ROLE_OPERATOR))):
    """Submit operator decision on a recommendation."""
    # Rule 5: Validate decision as enum
    if req.decision not in ["accepted", "rejected", "deferred"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid decision. Must be one of: 'accepted', 'rejected', 'deferred'."
        )

    # Rule 3: Never trust request body for identity. Use token's sub.
    operator_id = auth.get("username", "system")

    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")

        # Rule 5: 404 for unknown recommendation, 409 if already decided
        rec_entry = None
        for entry in reversed(_mi_api.decision_log.log):
            if entry.get("recommendation_id") == req.recommendation_id:
                rec_entry = entry
                break

        if not rec_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation '{req.recommendation_id}' not found in registry."
            )

        if rec_entry.get("decision"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Recommendation '{req.recommendation_id}' already has a recorded decision ('{rec_entry.get('decision')}')."
            )

        result = await _mi_api.submit_decision(
            recommendation_id=req.recommendation_id,
            decision=req.decision,
            reasoning=req.reasoning,
            operator=operator_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {str(e)}")


@app.get("/api/history")
async def get_history(
    limit: int = Query(10, description="Maximum number of entries"),
    operator: str = Query(None, description="Filter by operator"),
    auth: dict = Depends(require_role(ROLE_VIEWER))
):
    """Get decision history."""
    user_role = auth.get("role")
    user_sub = auth.get("username")
    # Rule 4: non-admin users may only filter operator by their own sub
    if operator and user_role != ROLE_ADMIN and operator != user_sub:
        log_access_denied(user_sub, str(user_role), "/api/history", f"Cannot filter history by other operator '{operator}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Non-admin users cannot filter history by other operators ('{operator}')."
        )

    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")

        history = _mi_api.get_decision_history(limit=limit, operator=operator)
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


# Webhook Endpoints for Digital Twin Model Push (Strictly Service-to-Service or Admin)
@app.post("/webhook/trigger-assessment")
async def webhook_trigger_assessment(payload: dict, auth: dict = Depends(require_service_key_or_admin)):
    """Webhook to trigger full assessment from Digital Twin."""
    try:
        if not _mi_api:
            raise HTTPException(status_code=503, detail="Mission Intelligence not initialized")
        row_index = payload.get("row_index", 0)
        horizon_minutes = payload.get("horizon_minutes", 60)
        run_scenarios = payload.get("run_scenarios", False)
        return await _mi_api.get_full_assessment(
            row_index=row_index,
            horizon_minutes=horizon_minutes,
            run_scenarios=run_scenarios
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook assessment failed: {str(e)}")


@app.post("/webhook/digital-twin/state")
async def webhook_dt_state(payload: dict, auth: dict = Depends(require_service_key_or_admin)):
    """Webhook to receive state push from Digital Twin."""
    return {"status": "RECEIVED", "payload_type": "state", "step_index": payload.get("step_index")}


@app.post("/webhook/digital-twin/prediction")
async def webhook_dt_prediction(payload: dict, auth: dict = Depends(require_service_key_or_admin)):
    """Webhook to receive prediction push from Digital Twin."""
    return {"status": "RECEIVED", "payload_type": "prediction"}


@app.post("/webhook/digital-twin/recommendation")
async def webhook_dt_recommendation(payload: dict, auth: dict = Depends(require_service_key_or_admin)):
    """Webhook to receive recommendation push from Digital Twin."""
    return {"status": "RECEIVED", "payload_type": "recommendation", "recommendation_id": payload.get("recommendation_id")}



if __name__ == "__main__":
    print("[Mission Intelligence] Starting Mission Intelligence Server...")
    print(f"[Mission Intelligence] Digital Twin URL: {DIGITAL_TWIN_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
