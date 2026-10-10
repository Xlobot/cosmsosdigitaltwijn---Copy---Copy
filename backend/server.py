import os
import json
import asyncio
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .ml_engine import HealthMLEngine
from .scenario_engine import ScenarioEngine
from .data_manager import DataManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

app = FastAPI(
    title="COSMOS Digital Twin API",
    description="High-fidelity Satellite Digital Twin with XGBoost Health Engine & Orbital Propagation",
    version="2.0.0"
)

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
    delta_v_prograde_ms: float = 0.0
    delta_v_radial_ms: float = 0.0
    delta_v_normal_ms: float = 0.0
    thrust_duration_s: float = 10.0
    payload_override: str = "KEEP" # KEEP, FORCE_OFF, FORCE_ON, DUTY_CYCLE_50
    thermal_slew_deg: float = 0.0

class ForkRequest(BaseModel):
    start_row_index: int = 0
    horizon_minutes: int = 60
    scenarios: list[ControlInputs] = []

@app.get("/api/status")
async def get_status():
    return {
        "status": "ONLINE",
        "system": "COSMOS Digital Twin Engine",
        "satellite_id": "ISS-25544",
        "dataset_total_rows": data_manager.get_total_rows(),
        "total_anomalies": len(data_manager.get_anomalies_list()),
        "ml_engine": "XGBoost Regressor & Classifier Ensemble (Active)",
        "features_count": len(ml_engine.features)
    }

@app.get("/api/state")
async def get_current_state(index: int = Query(0, description="Row index in dataset")):
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
    step: int = Query(1, description="Step stride")
):
    """
    Returns time series slice for charts and playback navigation.
    """
    return data_manager.get_timeline(start_index=start, count=count, step=step)

@app.get("/api/anomalies")
async def get_anomalies():
    """
    Returns the curated registry of anomaly events for timeline markers and jump-to-event dropdown.
    """
    return data_manager.get_anomalies_list()

@app.get("/api/dataset/all")
async def get_all_dataset():
    """
    Returns the full pre-evaluated dataset array for zero-latency client replay and continuous 60 FPS scrubbing.
    """
    return data_manager.get_timeline(start_index=0, count=data_manager.get_total_rows(), step=1)

@app.post("/api/predict")
async def predict_nominal(req: PredictRequest):
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
async def fork_scenarios(req: ForkRequest):
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
async def get_models_info():
    """
    Returns transparency details on the trained XGBoost models.
    """
    return ml_engine.get_model_info()

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
