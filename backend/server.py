import os
import json
import asyncio
import httpx
from fastapi import FastAPI, Query, HTTPException, Body, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .ml_engine import HealthMLEngine
from .scenario_engine import ScenarioEngine
from .data_manager import DataManager

from cosmos_security import (
    seed_admin_user,
    get_user_by_username,
    get_all_users,
    create_user,
    update_user_permissions,
    delete_user,
    verify_password,
    create_access_token,
    update_user_last_login,
    require_user_token,
    require_service_key,
    require_role,
    require_role_or_service_key,
    require_service_key_or_admin,
    ROLE_VIEWER,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_ADMIN,
    get_service_headers,
    JWT_EXPIRATION_MINUTES,
    SERVICE_KEY_HEADER,
    ALL_PERMISSIONS,
    DEFAULT_OPERATOR_PERMS,
    log_access_denied
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# Mission Intelligence configuration
MISSION_INTELLIGENCE_URL = os.getenv("MISSION_INTELLIGENCE_URL", "http://127.0.0.1:8001")

app = FastAPI(
    title="COSMOS Digital Twin API",
    description="High-fidelity Satellite Digital Twin with XGBoost Health Engine & Orbital Propagation",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_security():
    seed_admin_user()

@app.get("/healthz", summary="Public Health Check")
async def healthz():
    """Minimal unauthenticated health check returning status ok."""
    return {"status": "ok"}

# Authentication models & endpoints
class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "operator"
    permissions: list[str] = None

class UpdateUserPermissionsRequest(BaseModel):
    role: str = None
    permissions: list[str] = None

@app.post("/api/auth/login")
async def login(credentials: LoginRequest):
    """
    Operator login endpoint: authenticates username + password via pwdlib[argon2].
    Issues a signed JWT access token with a 15-minute expiration lifespan.
    """
    user = get_user_by_username(credentials.username)
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid flight operator username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    update_user_last_login(user["username"])
    perms = user.get("permissions")
    if not perms:
        perms = ["*"] if user.get("role") == "admin" else ["telemetry:read"]

    token = create_access_token({"sub": user["username"], "role": user["role"], "permissions": perms})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRATION_MINUTES * 60,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "permissions": perms
        }
    }

@app.get("/api/auth/me")
async def get_current_user_profile(user: dict = Depends(require_role(ROLE_VIEWER))):
    """Returns authenticated operator profile."""
    return {"user": user}

@app.get("/api/auth/users")
async def list_users(admin_auth: dict = Depends(require_role(ROLE_ADMIN))):
    """List all registered users. Exclusively accessible by Administrators."""
    users = get_all_users()
    return {
        "users": users,
        "available_permissions": ALL_PERMISSIONS,
        "default_operator_permissions": DEFAULT_OPERATOR_PERMS
    }

@app.post("/api/auth/users")
async def add_new_user(req: CreateUserRequest, admin_auth: dict = Depends(require_role(ROLE_ADMIN))):
    """
    Register a new operator or admin user and configure their permissions.
    Exclusively permitted by Administrators.
    """
    try:
        user = create_user(
            username=req.username,
            plain_password=req.password,
            role=req.role,
            permissions=req.permissions
        )
        return {
            "success": True,
            "message": f"User '{user['username']}' registered successfully.",
            "user": user
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"User '{req.username}' already exists.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create user: {e}")

@app.put("/api/auth/users/{username}/permissions")
async def update_user_perms(username: str, req: UpdateUserPermissionsRequest, admin_auth: dict = Depends(require_role(ROLE_ADMIN))):
    """
    Update role and assigned permissions of an existing user.
    Exclusively permitted by Administrators.
    """
    try:
        user = update_user_permissions(username, role=req.role, permissions=req.permissions)
        return {
            "success": True,
            "message": f"Permissions updated successfully for user '{username}'.",
            "user": user
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update permissions: {e}")

@app.delete("/api/auth/users/{username}")
async def remove_user(username: str, admin_auth: dict = Depends(require_role(ROLE_ADMIN))):
    """
    Delete a user account.
    Exclusively permitted by Administrators.
    """
    try:
        deleted = delete_user(username)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found.")
        return {"success": True, "message": f"User '{username}' deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete user: {e}")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
print("[Server] Initializing COSMOS ML Health Engine & Data Manager...")
ml_engine = HealthMLEngine()
scenario_engine = ScenarioEngine(ml_engine)
data_manager = DataManager(ml_engine)
print("[Server] COSMOS Digital Twin initialized successfully.")

# Request models
class PredictRequest(BaseModel):
    start_row_index: int = 0
    horizon_minutes: int = 60

class ControlInputs(BaseModel):
    scenario_id: str = "SCN-1"
    scenario_label: str = "Custom Maneuver"
    delta_v_prograde_ms: float = Field(0.0, ge=-500.0, le=500.0)
    delta_v_radial_ms: float = Field(0.0, ge=-500.0, le=500.0)
    delta_v_normal_ms: float = Field(0.0, ge=-500.0, le=500.0)
    thrust_duration_s: float = Field(10.0, ge=0.0, le=7200.0)
    payload_override: str = "KEEP" # KEEP, FORCE_OFF, FORCE_ON, DUTY_CYCLE_50
    thermal_slew_deg: float = Field(0.0, ge=-180.0, le=180.0)

class ForkRequest(BaseModel):
    start_row_index: int = 0
    horizon_minutes: int = 60
    scenarios: list[ControlInputs] = []

@app.get("/api/status")
async def get_status(auth: dict = Depends(require_role(ROLE_VIEWER))):
    return {
        "status": "ONLINE",
        "system": "COSMOS Digital Twin Engine",
        "satellite_id": "ISS-25544",
        "dataset_total_rows": data_manager.get_total_rows(),
        "total_anomalies": len(data_manager.get_anomalies_list()),
        "ml_engine": "XGBoost Regressor & Classifier Ensemble (Active)",
        "features_count": len(ml_engine.features),
        "generator": data_manager.get_connection_status()
    }

@app.get("/api/generator/status")
async def get_generator_status(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Returns real-time link status to the COSMOS Telemetry Generator REST API."""
    return data_manager.get_connection_status()

@app.post("/api/generator/inject-anomaly")
async def inject_generator_anomaly(request: Request, req: dict = Body(...), auth: dict = Depends(require_role(ROLE_ADMIN))):
    """Proxies synthetic anomaly injection command to the Telemetry Generator REST API."""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        try:
            res = await client.post(f"{data_manager.generator_url}/inject/anomaly", json=req)
            return JSONResponse(status_code=res.status_code, content=res.json())
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Telemetry Generator unreachable at {data_manager.generator_url}: {e}")

@app.get("/api/state")
async def get_current_state(index: int = Query(0, description="Row index in dataset"), auth: dict = Depends(require_role_or_service_key(ROLE_VIEWER))):
    """
    Contract function: get_current_state()
    Produces current synced telemetry, ML health score, subsystem breakdown, and anomaly flags.
    """
    state = data_manager.get_state(index)
    return state

@app.get("/api/timeline")
async def get_timeline(
    start: int = Query(0, description="Start row index"),
    count: int = Query(100, description="Number of points to return"),
    step: int = Query(1, description="Step stride"),
    auth: dict = Depends(require_role(ROLE_VIEWER))
):
    """
    Returns time series slice for charts and playback navigation.
    """
    return data_manager.get_timeline(start_index=start, count=count, step=step)

@app.get("/api/anomalies")
async def get_anomalies(auth: dict = Depends(require_role_or_service_key(ROLE_VIEWER))):
    """
    Returns the curated registry of anomaly events for timeline markers and jump-to-event dropdown.
    """
    return data_manager.get_anomalies_list()

@app.get("/api/dataset/all")
async def get_all_dataset(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """
    Returns the full pre-evaluated dataset array for zero-latency client replay and continuous 60 FPS scrubbing.
    """
    return data_manager.get_timeline(start_index=0, count=data_manager.get_total_rows(), step=1)

@app.post("/api/predict")
async def predict_nominal(req: PredictRequest, auth: dict = Depends(require_role_or_service_key(ROLE_ANALYST))):
    """
    Contract function: predict(horizon)
    Performs nominal forward propagation starting at start_row_index.
    Compares against ground-truth future rows in the dataset and computes validation errors + confidence decay.
    """
    history = data_manager.get_history_window(req.start_row_index, window_size=30)

    # Nominal simulation — real physics+ML forecast (not a ground-truth replay)
    nominal_controls = {
        "scenario_id": "SCN-NOMINAL",
        "scenario_label": "Nominal Propagation",
        "payload_override": "SCHEDULE",  # continue ON/~30m STANDBY/~62m duty cycle
        "delta_v_prograde_ms": 0.0,
        "delta_v_radial_ms": 0.0,
        "delta_v_normal_ms": 0.0,
        "thermal_slew_deg": 0.0,
    }
    sim_result = scenario_engine.simulate_trajectory(
        initial_history=history,
        horizon_minutes=req.horizon_minutes,
        step_seconds=60,
        controls=nominal_controls,
    )

    # Compute Ground-Truth Validation metrics against actual dataset rows
    val_metrics = data_manager.compute_ground_truth_validation(
        start_index=req.start_row_index,
        predicted_trajectory=sim_result["trajectory"]
    )

    return {
        "start_row_index": req.start_row_index,
        "horizon_minutes": req.horizon_minutes,
        "nominal_prediction": sim_result,
        "ground_truth_validation": val_metrics
    }

@app.post("/api/fork")
async def fork_scenarios(req: ForkRequest, auth: dict = Depends(require_role_or_service_key(ROLE_ANALYST))):
    """
    Contract function: fork_scenario(controls)
    Forks the current twin state into 2-4 candidate scenarios simultaneously.
    Runs physical + ML propagation and produces Explainable AI trade-off recommendations.
    """
    history = data_manager.get_history_window(req.start_row_index, window_size=30)
    
    # If no custom scenarios provided, generate 3 canonical mission scenarios
    scenario_list = req.scenarios
    if not scenario_list:
        scenario_list = [
            ControlInputs(
                scenario_id="SCN-NOMINAL",
                scenario_label="Scenario A: Nominal Flight Path",
                payload_override="SCHEDULE",
                delta_v_prograde_ms=0.0,
                thermal_slew_deg=0.0
            ),
            ControlInputs(
                scenario_id="SCN-PWR-SHED",
                scenario_label="Scenario B: Payload Shedding & Thermal Recovery",
                payload_override="FORCE_OFF",
                delta_v_prograde_ms=0.0,
                thermal_slew_deg=25.0
            ),
            ControlInputs(
                scenario_id="SCN-ORBIT-BOOST",
                scenario_label="Scenario C: Prograde Phasing Burn (+15 m/s)",
                payload_override="SCHEDULE",
                delta_v_prograde_ms=15.0,
                thrust_duration_s=20.0,
                thermal_slew_deg=0.0
            )
        ]

    simulated_scenarios = []
    for scn in scenario_list:
        res = scenario_engine.simulate_trajectory(
            initial_history=history,
            horizon_minutes=req.horizon_minutes,
            step_seconds=60,
            controls=scn.model_dump()
        )
        simulated_scenarios.append(res)

    # Explainable AI recommendations
    ai_recommendation = scenario_engine.generate_scenario_recommendation(simulated_scenarios)

    return {
        "start_row_index": req.start_row_index,
        "horizon_minutes": req.horizon_minutes,
        "scenarios": simulated_scenarios,
        "ai_recommendation": ai_recommendation
    }

@app.get("/api/models/info")
async def get_models_info(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """
    Returns transparency details on the trained XGBoost models.
    """
    return ml_engine.get_model_info()


# ==============================================================================
# Mission Intelligence Integration Endpoints
# ==============================================================================

class MIStatePush(BaseModel):
    """Model for pushing state to Mission Intelligence."""
    timestamp: str
    satellite_id: str
    step_index: int
    health_score: float
    battery_percentage: float
    temperature: float
    battery_voltage: float
    payload_status: str
    sunlit: bool


@app.post("/api/mi/push-state")
async def push_state_to_mi(state: MIStatePush, auth: dict = Depends(require_service_key_or_admin)):
    """
    Push current state to Mission Intelligence and trigger assessment.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=get_service_headers()) as client:
            response = await client.post(
                f"{MISSION_INTELLIGENCE_URL}/webhook/digital-twin/state",
                json=state.dict()
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to push state to Mission Intelligence"
        }


@app.post("/api/mi/trigger-assessment")
async def trigger_mi_assessment(
    row_index: int = Query(0, description="Current row index"),
    horizon_minutes: int = Query(60, description="Prediction horizon"),
    run_scenarios: bool = Query(False, description="Run scenario evaluation"),
    auth: dict = Depends(require_role(ROLE_ANALYST))
):
    """
    Trigger a full Mission Intelligence assessment via webhook.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, headers=get_service_headers()) as client:
            response = await client.post(
                f"{MISSION_INTELLIGENCE_URL}/webhook/trigger-assessment",
                json={
                    "row_index": row_index,
                    "horizon_minutes": horizon_minutes,
                    "run_scenarios": run_scenarios
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to trigger Mission Intelligence assessment"
        }


@app.post("/api/mi/push-prediction")
async def push_prediction_to_mi(
    start_row_index: int = Query(0, description="Start row index"),
    horizon_minutes: int = Query(60, description="Prediction horizon"),
    auth: dict = Depends(require_service_key_or_admin)
):
    """
    Push Digital Twin prediction to Mission Intelligence for analysis.
    """
    try:
        prediction_req = PredictRequest(
            start_row_index=start_row_index,
            horizon_minutes=horizon_minutes
        )
        prediction = await predict_nominal(prediction_req, auth=auth)
        async with httpx.AsyncClient(timeout=10.0, headers=get_service_headers()) as client:
            response = await client.post(
                f"{MISSION_INTELLIGENCE_URL}/webhook/digital-twin/prediction",
                json={
                    "start_row_index": start_row_index,
                    "horizon_minutes": horizon_minutes,
                    "prediction_data": prediction
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to push prediction to Mission Intelligence"
        }


@app.post("/api/mi/push-recommendation")
async def push_recommendation_to_mi(
    recommendation_id: str = Body(..., description="Recommendation ID"),
    action: str = Body(..., description="Recommended action"),
    reasoning: str = Body(..., description="Reasoning for recommendation"),
    confidence: float = Body(0.85, description="Confidence level"),
    auth: dict = Depends(require_service_key_or_admin)
):
    """
    Push Digital Twin's AI recommendation to Mission Intelligence.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=get_service_headers()) as client:
            response = await client.post(
                f"{MISSION_INTELLIGENCE_URL}/webhook/digital-twin/recommendation",
                json={
                    "recommendation_id": recommendation_id,
                    "action": action,
                    "reasoning": reasoning,
                    "confidence": confidence
                }
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to push recommendation to Mission Intelligence"
        }


# Direct / Proxied Client Endpoints for Mission Intelligence UI
@app.post("/api/mi/assess")
async def mi_assess_endpoint(request: Request, req: dict = Body(...), auth: dict = Depends(require_role(ROLE_ANALYST))):
    """Assess current mission condition and generate recommended actions."""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient(timeout=35.0, headers=headers) as client:
        try:
            res = await client.post(f"{MISSION_INTELLIGENCE_URL}/api/assess", json=req)
            return JSONResponse(status_code=res.status_code, content=res.json())
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Mission Intelligence service unreachable at {MISSION_INTELLIGENCE_URL}: {e}")


@app.post("/api/mi/decision")
async def mi_decision_endpoint(request: Request, req: dict = Body(...), auth: dict = Depends(require_role(ROLE_OPERATOR))):
    """Submit operator acceptance/rejection of recommendation."""
    decision = req.get("decision")
    if decision not in ["accepted", "rejected", "deferred"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid decision. Must be one of: 'accepted', 'rejected', 'deferred'."
        )
    # Rule 3: Never trust request body for identity. Use token's sub.
    req["operator"] = auth.get("username")

    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            res = await client.post(f"{MISSION_INTELLIGENCE_URL}/api/decision", json=req)
            return JSONResponse(status_code=res.status_code, content=res.json())
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Mission Intelligence service unreachable at {MISSION_INTELLIGENCE_URL}: {e}")


@app.get("/api/mi/history")
async def mi_history_endpoint(request: Request, limit: int = 10, operator: str = None, auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Get recent operator decision log."""
    user_role = auth.get("role")
    user_sub = auth.get("username")
    # Rule 4: non-admin users may only filter operator by their own sub.
    if operator and user_role != ROLE_ADMIN and operator != user_sub:
        log_access_denied(user_sub, str(user_role), "/api/mi/history", f"Cannot filter history by other operator '{operator}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Non-admin users cannot filter history by other operators ('{operator}')."
        )
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            params = {"limit": limit}
            if operator:
                params["operator"] = operator
            res = await client.get(f"{MISSION_INTELLIGENCE_URL}/api/history", params=params)
            return JSONResponse(status_code=res.status_code, content=res.json())
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Mission Intelligence service unreachable at {MISSION_INTELLIGENCE_URL}: {e}")


@app.get("/api/mi/health")
async def mi_health_endpoint(request: Request, auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Check Mission Intelligence connectivity."""
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}
    async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
        try:
            res = await client.get(f"{MISSION_INTELLIGENCE_URL}/api/health")
            return JSONResponse(status_code=res.status_code, content=res.json())
        except Exception as e:
            return {"mission_intelligence_status": "OFFLINE", "error": str(e)}

# Static files for frontend build if present
FRONTEND_DIST = os.path.join(ROOT_DIR, "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
