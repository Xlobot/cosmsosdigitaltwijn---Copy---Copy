"""
COSMOS Telemetry Generator REST API Service
============================================
Provides high-fidelity, real-time satellite telemetry streaming via HTTP REST API.
Eliminates the need for CSV/Excel file exports by allowing the COSMOS Digital Twin
module to directly ingest telemetry keys over HTTP.

Usage:
  python generator_api.py --port 8080 --interval 1.0
  python -m uvicorn generator_api:app --host 0.0.0.0 --port 8080
"""

import os
import sys
import csv
import json
import math
import time
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, HTTPException, Body, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from cosmos_security import (
    require_role,
    require_viewer_or_service_key,
    authenticate_websocket,
    ROLE_VIEWER,
    ROLE_ADMIN
)
DEFAULT_CSV = os.path.join(HERE, "cosmos_integrated_dataset.csv")

NUMERIC_FIELDS = {
    "position_x", "position_y", "position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "semi_major_axis", "eccentricity", "inclination",
    "raan", "argument_of_perigee", "true_anomaly",
    "orientation_q0", "orientation_q1", "orientation_q2", "orientation_q3",
    "angular_velocity_x", "angular_velocity_y", "angular_velocity_z",
    "battery_percentage", "battery_voltage", "battery_current",
    "temperature", "solar_power_input", "power_draw",
    "payload_power_draw", "fuel_remaining_pct",
}

KEY_METADATA = {
    "timestamp": {
        "type": "string (ISO-8601 UTC)",
        "subsystem": "Identification & Time",
        "description": "UTC timestamp of the telemetry observation sample",
        "example": "2026-10-14T10:45:00Z"
    },
    "satellite_id": {
        "type": "string",
        "subsystem": "Identification & Time",
        "description": "Identifier of the spacecraft/space station (e.g. ISS-25544)",
        "example": "ISS-25544"
    },
    "position_x": {
        "type": "float",
        "unit": "km",
        "subsystem": "Orbit & Ephemeris",
        "description": "X Cartesian coordinate in Earth-Centered Inertial (ECI) frame",
        "example": 5008.04
    },
    "position_y": {
        "type": "float",
        "unit": "km",
        "subsystem": "Orbit & Ephemeris",
        "description": "Y Cartesian coordinate in Earth-Centered Inertial (ECI) frame",
        "example": 4478.62
    },
    "position_z": {
        "type": "float",
        "unit": "km",
        "subsystem": "Orbit & Ephemeris",
        "description": "Z Cartesian coordinate in Earth-Centered Inertial (ECI) frame",
        "example": -1058.73
    },
    "velocity_x": {
        "type": "float",
        "unit": "km/s",
        "subsystem": "Orbit & Ephemeris",
        "description": "ECI Velocity vector X component",
        "example": -3.89
    },
    "velocity_y": {
        "type": "float",
        "unit": "km/s",
        "subsystem": "Orbit & Ephemeris",
        "description": "ECI Velocity vector Y component",
        "example": 2.97
    },
    "velocity_z": {
        "type": "float",
        "unit": "km/s",
        "subsystem": "Orbit & Ephemeris",
        "description": "ECI Velocity vector Z component",
        "example": -5.89
    },
    "semi_major_axis": {
        "type": "float",
        "unit": "km",
        "subsystem": "Keplerian Orbital Elements",
        "description": "Semi-major axis of the orbit ellipse",
        "example": 6800.59
    },
    "eccentricity": {
        "type": "float",
        "unit": "dimensionless",
        "subsystem": "Keplerian Orbital Elements",
        "description": "Orbital eccentricity (0 = circular)",
        "example": 0.000789
    },
    "inclination": {
        "type": "float",
        "unit": "degrees",
        "subsystem": "Keplerian Orbital Elements",
        "description": "Orbital inclination relative to equatorial plane",
        "example": 51.66
    },
    "raan": {
        "type": "float",
        "unit": "degrees",
        "subsystem": "Keplerian Orbital Elements",
        "description": "Right Ascension of the Ascending Node",
        "example": 214.65
    },
    "argument_of_perigee": {
        "type": "float",
        "unit": "degrees",
        "subsystem": "Keplerian Orbital Elements",
        "description": "Angular distance of perigee from ascending node",
        "example": 92.39
    },
    "true_anomaly": {
        "type": "float",
        "unit": "degrees",
        "subsystem": "Keplerian Orbital Elements",
        "description": "True anomaly position angle along the orbit ellipse",
        "example": 99.06
    },
    "orientation_q0": {
        "type": "float",
        "unit": "quaternion scalar",
        "subsystem": "Attitude & Dynamics",
        "description": "Attitude quaternion component 0",
        "example": -0.019
    },
    "orientation_q1": {
        "type": "float",
        "unit": "quaternion vector",
        "subsystem": "Attitude & Dynamics",
        "description": "Attitude quaternion component 1",
        "example": -0.495
    },
    "orientation_q2": {
        "type": "float",
        "unit": "quaternion vector",
        "subsystem": "Attitude & Dynamics",
        "description": "Attitude quaternion component 2",
        "example": -0.421
    },
    "orientation_q3": {
        "type": "float",
        "unit": "quaternion vector",
        "subsystem": "Attitude & Dynamics",
        "description": "Attitude quaternion component 3",
        "example": 0.760
    },
    "angular_velocity_x": {
        "type": "float",
        "unit": "deg/s",
        "subsystem": "Attitude & Dynamics",
        "description": "Body rotation rate along X axis",
        "example": -0.013
    },
    "angular_velocity_y": {
        "type": "float",
        "unit": "deg/s",
        "subsystem": "Attitude & Dynamics",
        "description": "Body rotation rate along Y axis",
        "example": -0.064
    },
    "angular_velocity_z": {
        "type": "float",
        "unit": "deg/s",
        "subsystem": "Attitude & Dynamics",
        "description": "Body rotation rate along Z axis",
        "example": -0.003
    },
    "battery_percentage": {
        "type": "float",
        "unit": "%",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Battery state of charge (SoC)",
        "example": 58.85
    },
    "battery_voltage": {
        "type": "float",
        "unit": "V",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Main electrical bus battery terminal voltage",
        "example": 7.43
    },
    "battery_current": {
        "type": "float",
        "unit": "A",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Battery current flow (>0 charging, <0 discharging)",
        "example": -7.39
    },
    "solar_power_input": {
        "type": "float",
        "unit": "W",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Solar photovoltaic generation power",
        "example": 0.30
    },
    "power_draw": {
        "type": "float",
        "unit": "W",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Total spacecraft electrical power consumption",
        "example": 55.23
    },
    "sunlit": {
        "type": "boolean",
        "unit": "bool",
        "subsystem": "Electrical Power System (EPS)",
        "description": "Orbital illumination status (True = Sunlit, False = Eclipse/Shadow)",
        "example": False
    },
    "temperature": {
        "type": "float",
        "unit": "°C",
        "subsystem": "Thermal Control Subsystem (TCS)",
        "description": "Primary sensor core temperature",
        "example": 13.26
    },
    "payload_status": {
        "type": "string",
        "subsystem": "Payload Subsystem",
        "description": "Payload operational status ('ON', 'OFF', 'STANDBY')",
        "example": "ON"
    },
    "payload_power_draw": {
        "type": "float",
        "unit": "W",
        "subsystem": "Payload Subsystem",
        "description": "Electrical power consumed exclusively by the payload instrument",
        "example": 24.48
    },
    "communication_status": {
        "type": "string",
        "subsystem": "Communication Subsystem (TT&C)",
        "description": "Ground telemetry link state ('LINKED', 'DOWNLINKING', 'NO_CONTACT')",
        "example": "LINKED"
    },
    "fuel_remaining_pct": {
        "type": "float",
        "unit": "%",
        "subsystem": "Propulsion Subsystem",
        "description": "Propellant mass reserve percentage for orbit-maintenance delta-V",
        "example": 100.0
    }
}


def _coerce_row(row: dict) -> dict:
    out = dict(row)
    for key in NUMERIC_FIELDS:
        if key not in out or out[key] in (None, ""):
            continue
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            pass
    if "sunlit" in out:
        v = out["sunlit"]
        if isinstance(v, str):
            out["sunlit"] = v.strip().upper() in ("TRUE", "1", "YES")
        else:
            out["sunlit"] = bool(v)
    return out


def load_dataset(csv_path: str) -> list[dict]:
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"Telemetry source CSV not found: {csv_path}")
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [_coerce_row(r) for r in csv.DictReader(f)]


class TelemetryStreamEngine:
    """In-memory streaming engine that emits paced real-time satellite telemetry."""

    def __init__(self, source_rows: list[dict], interval_seconds: float = 1.0, loop: bool = True):
        self.rows = source_rows
        self.interval = max(0.01, float(interval_seconds))
        self.loop = loop
        self.lock = threading.Lock()
        
        self.emitted: list[dict] = []
        self.is_running: bool = False
        self.is_paused: bool = False
        self.cursor: int = 0
        self.start_time = datetime.now(timezone.utc)
        self.anomaly_overrides: dict[str, Any] = {}
        self.anomaly_countdown: int = 0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="telemetry-emitter", daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def reset(self):
        with self.lock:
            self.cursor = 0
            self.emitted.clear()
            self.anomaly_overrides.clear()
            self.anomaly_countdown = 0

    def set_interval(self, seconds: float):
        with self.lock:
            self.interval = max(0.01, float(seconds))

    def inject_anomaly(self, overrides: dict[str, Any], count: int = 10):
        with self.lock:
            self.anomaly_overrides = dict(overrides)
            self.anomaly_countdown = count

    def get_latest(self) -> dict:
        with self.lock:
            return dict(self.emitted[-1]) if self.emitted else {}

    def get_rows_since(self, since: int, limit: int = 1000) -> list[dict]:
        with self.lock:
            start_idx = max(0, since)
            return [dict(r) for r in self.emitted[start_idx:start_idx + limit]]

    def status(self) -> dict:
        with self.lock:
            return {
                "status": "ok",
                "service": "COSMOS Satellite Telemetry Generator API",
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "interval_seconds": self.interval,
                "rows_emitted": len(self.emitted),
                "dataset_source_rows": len(self.rows),
                "cursor": self.cursor,
                "anomaly_active": self.anomaly_countdown > 0,
                "uptime_seconds": round((datetime.now(timezone.utc) - self.start_time).total_seconds(), 1),
                "latest_timestamp": self.emitted[-1]["timestamp"] if self.emitted else None,
                "satellite_id": self.emitted[-1].get("satellite_id", "ISS-25544") if self.emitted else "ISS-25544",
            }

    def _run_loop(self):
        n = len(self.rows)
        while not self._stop_event.is_set():
            if self.is_paused:
                time.sleep(0.1)
                continue

            with self.lock:
                idx = self.cursor % n
                row = dict(self.rows[idx])
                row["source_row_index"] = idx
                row["emit_index"] = self.cursor
                row["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                # Pre-calculate Geodetic coordinates (Lat, Lon, Alt) for immediate 3D visualization
                px = float(row.get("position_x", 0) or 0)
                py = float(row.get("position_y", 0) or 0)
                pz = float(row.get("position_z", 0) or 0)
                r_mag = math.sqrt(px * px + py * py + pz * pz)
                if r_mag > 1e-3:
                    alt_km = r_mag - 6378.137
                    gmst_rad = (self.cursor * 60.0 * 7.2921159e-5) % (2.0 * math.pi)
                    lat_deg = math.degrees(math.asin(max(-1.0, min(1.0, pz / r_mag))))
                    lon_deg = (math.degrees(math.atan2(py, px) - gmst_rad) + 180.0) % 360.0 - 180.0
                    row["latitude"] = round(lat_deg, 4)
                    row["longitude"] = round(lon_deg, 4)
                    row["altitude_km"] = round(alt_km, 2)

                # Shorthand aliases for universal digital twin code compatibility
                row["time"] = row["timestamp"]
                row["fuel_remaining"] = row.get("fuel_remaining_pct")
                row["battery_soc"] = row.get("battery_percentage")
                row["pos_x"] = px
                row["pos_y"] = py
                row["pos_z"] = pz
                row["vel_x"] = row.get("velocity_x")
                row["vel_y"] = row.get("velocity_y")
                row["vel_z"] = row.get("velocity_z")
                row["q0"] = row.get("orientation_q0")
                row["q1"] = row.get("orientation_q1")
                row["q2"] = row.get("orientation_q2")
                row["q3"] = row.get("orientation_q3")

                # Apply active synthetic anomaly injection if specified
                if self.anomaly_countdown > 0:
                    for k, v in self.anomaly_overrides.items():
                        row[k] = v
                    self.anomaly_countdown -= 1

                self.emitted.append(row)
                self.cursor += 1

                if not self.loop and self.cursor >= n:
                    self.is_running = False
                    break

            time.sleep(self.interval)


# Global Engine Instance
DATASET = load_dataset(DEFAULT_CSV)
streamer = TelemetryStreamEngine(DATASET, interval_seconds=1.0, loop=True)
streamer.start()

# FastAPI Application Definition
app = FastAPI(
    title="COSMOS Telemetry Generator API",
    description=(
        "High-performance REST API streaming live satellite telemetry directly to "
        "the COSMOS Digital Twin module. Replaces slow and manual Excel exports."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Models
class RateChangeRequest(BaseModel):
    interval_seconds: float = Field(..., gt=0.0, description="Telemetry emission interval in seconds (e.g. 1.0 or 0.2)")

class AnomalyInjectionRequest(BaseModel):
    duration_ticks: int = Field(10, description="Number of consecutive rows the anomaly should persist")
    overrides: Dict[str, Any] = Field(
        ...,
        description="Key-value pairs to override in telemetry (e.g. {'temperature': 88.5, 'battery_voltage': 5.2})"
    )


@app.get("/healthz", summary="Public Health Check")
def healthz():
    """Minimal unauthenticated health check returning status ok."""
    return {"status": "ok"}


@app.get("/", summary="Root Overview")
def root_info(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Provides service status, available endpoints, and instructions for Digital Twin integration."""
    return {
        "service": "COSMOS Telemetry Generator API",
        "version": "2.0.0",
        "documentation": "/docs",
        "endpoints": {
            "health": "/health",
            "latest": "/latest",
            "rows": "/rows?since={index}&limit={count}",
            "websocket": "ws://localhost:8080/ws",
            "sse_stream": "/stream",
            "keys": "/keys",
            "schema": "/schema",
            "rate_control": "POST /control/rate",
            "pause": "POST /control/pause",
            "resume": "POST /control/resume",
            "reset": "POST /control/reset",
            "inject_anomaly": "POST /inject/anomaly",
        },
        "digital_twin_compatibility": {
            "live_ingest_url": "http://127.0.0.1:8080",
            "polling_endpoint": "GET /rows?since={cursor}",
            "health_check_endpoint": "GET /health"
        }
    }


@app.get("/health", summary="Health Check for Digital Twin Ingestion")
@app.get("/api/health", include_in_schema=False)
@app.get("/status", include_in_schema=False)
@app.get("/api/status", include_in_schema=False)
@app.get("/ping", include_in_schema=False)
def get_health(auth: dict = Depends(require_viewer_or_service_key)):
    """
    Standard health check endpoint polled by Digital Twin's `LiveIngest._health_ok()`.
    Returns `status: ok` and telemetry stream statistics.
    """
    return streamer.status()


@app.get("/latest", summary="Get Latest Telemetry Frame")
@app.get("/api/latest", include_in_schema=False)
@app.get("/telemetry/latest", include_in_schema=False)
@app.get("/current", include_in_schema=False)
@app.get("/api/current", include_in_schema=False)
@app.get("/state", include_in_schema=False)
def get_latest(auth: dict = Depends(require_viewer_or_service_key)):
    """
    Returns the single most recent satellite telemetry frame emitted by the generator.
    The digital twin can query this for instantaneous state synchronization.
    Requires viewer role or X-Service-Key authentication header.
    """
    latest = streamer.get_latest()
    if not latest:
        raise HTTPException(status_code=503, detail="No telemetry frames emitted yet")
    return latest


@app.get("/rows", summary="Incremental Telemetry Polling")
@app.get("/api/rows", include_in_schema=False)
@app.get("/telemetry/rows", include_in_schema=False)
@app.get("/telemetry", include_in_schema=False)
@app.get("/api/telemetry", include_in_schema=False)
@app.get("/data", include_in_schema=False)
@app.get("/feed", include_in_schema=False)
def get_rows(
    since: Optional[int] = Query(None, description="Emit index cursor. Returns rows with emit_index >= since"),
    cursor: Optional[int] = Query(None, description="Cursor alias for since"),
    offset: Optional[int] = Query(None, description="Offset alias for since"),
    start: Optional[int] = Query(None, description="Start index alias for since"),
    from_row: Optional[int] = Query(None, alias="from", description="From index alias for since"),
    limit: Optional[int] = Query(None, description="Max number of rows to return"),
    count: Optional[int] = Query(None, description="Count alias for limit"),
    format: Optional[str] = Query("list", description="Format: 'list' (default JSON array) or 'envelope'"),
    auth: dict = Depends(require_viewer_or_service_key)
):
    """
    The primary ingestion endpoint consumed by the Digital Twin LiveIngest engine.
    Supports all parameter names (since, cursor, offset, start, from) so any digital twin
    code connects seamlessly without modifications.
    """
    idx = 0
    for cand in (since, cursor, offset, start, from_row):
        if isinstance(cand, (int, float)):
            idx = max(0, int(cand))
            break

    max_rows = 1000
    for cand in (count, limit):
        if isinstance(cand, (int, float)):
            max_rows = max(1, int(cand))
            break

    rows = streamer.get_rows_since(since=idx, limit=max_rows)
    if format == "envelope":
        return {
            "status": "ok",
            "cursor": idx,
            "count": len(rows),
            "rows": rows,
            "data": rows
        }
    return rows


@app.websocket("/ws")
@app.websocket("/api/ws")
@app.websocket("/ws/telemetry")
@app.websocket("/telemetry/ws")
@app.websocket("/socket")
async def websocket_telemetry(websocket: WebSocket):
    """
    Real-time WebSocket stream of satellite telemetry frames.
    Requires authenticated token via Sec-WebSocket-Protocol header or initial auth message.
    """
    payload = await authenticate_websocket(websocket, min_role=ROLE_VIEWER)
    if not payload:
        return
    last_emitted_index = -1
    try:
        while True:
            latest = streamer.get_latest()
            if latest and latest.get("emit_index") != last_emitted_index:
                last_emitted_index = latest.get("emit_index")
                await websocket.send_json(latest)
            await asyncio.sleep(0.05)
    except (WebSocketDisconnect, Exception):
        pass


@app.get("/stream", summary="Server-Sent Events (SSE) Stream")
@app.get("/api/stream", include_in_schema=False)
@app.get("/events", include_in_schema=False)
async def sse_telemetry(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """
    Real-time Server-Sent Events (SSE) stream of satellite telemetry frames.
    Requires valid viewer Bearer token.
    """
    async def event_generator():
        last_emitted_index = -1
        while True:
            latest = streamer.get_latest()
            if latest and latest.get("emit_index") != last_emitted_index:
                last_emitted_index = latest.get("emit_index")
                yield f"data: {json.dumps(latest)}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/keys", summary="Telemetry Key Catalog & Digital Twin Mapping")
@app.get("/api/keys", include_in_schema=False)
@app.get("/metadata", include_in_schema=False)
def get_keys(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """
    Returns complete documentation of all 32 telemetry keys: data types, physical units,
    subsystems, and example values.
    """
    return {
        "total_keys": len(KEY_METADATA),
        "keys": KEY_METADATA,
        "subsystem_groups": {
            "Identification & Time": ["timestamp", "satellite_id"],
            "Orbit & Ephemeris": ["position_x", "position_y", "position_z", "velocity_x", "velocity_y", "velocity_z"],
            "Keplerian Orbital Elements": ["semi_major_axis", "eccentricity", "inclination", "raan", "argument_of_perigee", "true_anomaly"],
            "Attitude & Dynamics": ["orientation_q0", "orientation_q1", "orientation_q2", "orientation_q3", "angular_velocity_x", "angular_velocity_y", "angular_velocity_z"],
            "Electrical Power System (EPS)": ["battery_percentage", "battery_voltage", "battery_current", "solar_power_input", "power_draw", "sunlit"],
            "Thermal Control Subsystem (TCS)": ["temperature"],
            "Payload Subsystem": ["payload_status", "payload_power_draw"],
            "Communication Subsystem (TT&C)": ["communication_status"],
            "Propulsion Subsystem": ["fuel_remaining_pct"]
        }
    }


@app.get("/schema", summary="Telemetry Data Schema")
@app.get("/api/schema", include_in_schema=False)
def get_schema(auth: dict = Depends(require_role(ROLE_VIEWER))):
    """Returns the JSON schema of keys emitted in every telemetry row."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "CosmosTelemetryRow",
        "type": "object",
        "properties": {
            k: {
                "type": meta["type"].split()[0],
                "description": meta["description"],
                "unit": meta.get("unit", "N/A")
            }
            for k, meta in KEY_METADATA.items()
        },
        "required": list(KEY_METADATA.keys())
    }


@app.post("/control/rate", summary="Adjust Telemetry Frequency")
@app.post("/api/control/rate", include_in_schema=False)
def set_rate(req: RateChangeRequest, auth: dict = Depends(require_role(ROLE_ADMIN))):
    """Dynamically increases or decreases the real-time telemetry emission rate."""
    streamer.set_interval(req.interval_seconds)
    return {"message": f"Emission interval updated to {req.interval_seconds}s ({1.0/req.interval_seconds:.2f} Hz)"}


@app.post("/control/pause", summary="Pause Stream")
@app.post("/api/control/pause", include_in_schema=False)
def pause_stream(auth: dict = Depends(require_role(ROLE_ADMIN))):
    """Pauses telemetry streaming."""
    streamer.pause()
    return {"message": "Telemetry stream paused"}


@app.post("/control/resume", summary="Resume Stream")
@app.post("/api/control/resume", include_in_schema=False)
def resume_stream(auth: dict = Depends(require_role(ROLE_ADMIN))):
    """Resumes telemetry streaming."""
    streamer.resume()
    return {"message": "Telemetry stream resumed"}


@app.post("/control/reset", summary="Reset Stream Cursor")
@app.post("/api/control/reset", include_in_schema=False)
def reset_stream(auth: dict = Depends(require_role(ROLE_ADMIN))):
    """Resets the emission cursor back to the start of the dataset."""
    streamer.reset()
    return {"message": "Telemetry stream reset to index 0"}


@app.post("/inject/anomaly", summary="Inject Synthetic Fault / Anomaly")
@app.post("/api/inject/anomaly", include_in_schema=False)
def inject_anomaly(req: AnomalyInjectionRequest, auth: dict = Depends(require_role(ROLE_ADMIN))):
    """
    Injects a temporary fault into the telemetry feed (e.g. temperature spike to 90°C)
    to test the Digital Twin's ML anomaly detection and risk scoring in real time.
    """
    streamer.inject_anomaly(req.overrides, count=req.duration_ticks)
    return {
        "message": f"Injected synthetic anomaly for {req.duration_ticks} ticks",
        "overrides": req.overrides
    }


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="COSMOS Telemetry Generator REST API")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind API (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between telemetry ticks (default: 1.0)")
    args = parser.parse_args()

    streamer.set_interval(args.interval)
    print(f"\n=======================================================")
    print(f"  COSMOS Telemetry Generator REST API Service")
    print(f"  Running at: http://{args.host}:{args.port}")
    print(f"  Interactive Swagger UI: http://localhost:{args.port}/docs")
    print(f"  Digital Twin Ingest Endpoint: http://localhost:{args.port}/rows")
    print(f"=======================================================\n")
    uvicorn.run(app, host=args.host, port=args.port)
