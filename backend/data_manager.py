"""
COSMOS Data Manager - Telemetry Generator API Ingestion Engine
==============================================================
Connects directly to the COSMOS Telemetry Generator REST API service (http://127.0.0.1:8080).
All historical static dataset files (e.g. cosmos_twin_dataset.xlsx) are completely decoupled.
All incoming telemetry data is evaluated dynamically in real time by the trained XGBoost ML Health Engine.
"""

import os
import math
import time
import threading
import urllib.request
import urllib.error
import json
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any

from .orbit_propagator import cartesian_to_geodetic, OMEGA_EARTH
from .ml_engine import HealthMLEngine
from cosmos_security import get_service_headers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
GENERATOR_CSV_FALLBACK = os.path.join(ROOT_DIR, "cosmos_telemetry_generator", "cosmos_integrated_dataset.csv")

DEFAULT_GENERATOR_URL = os.getenv("COSMOS_GENERATOR_URL", "http://127.0.0.1:8080").rstrip("/")


def _clean_value(v):
    """Normalize numpy/pandas scalars into JSON-safe Python types."""
    if isinstance(v, (np.generic,)):
        v = v.item()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 6) if abs(v) < 1e6 else float(v)
    if pd.isna(v):
        return None
    return v


def _clean_row(row_dict: dict) -> dict:
    return {k: _clean_value(v) for k, v in row_dict.items()}


class DataManager:
    """
    Consumes live telemetry streams from the COSMOS Telemetry Generator REST API,
    runs dynamic XGBoost ML health and anomaly evaluations on new incoming frames,
    and serves real-time digital twin state across all operational stations.
    """

    def __init__(self, ml_engine: HealthMLEngine, generator_url: str = DEFAULT_GENERATOR_URL):
        self.ml_engine = ml_engine
        self.generator_url = generator_url.rstrip("/")
        self.df = pd.DataFrame()
        self.anomalies = []
        self.lock = threading.Lock()
        self.cursor = 0
        self.is_connected = False
        self.last_sync_time = None
        self._stop_event = threading.Event()
        self._poller_thread: Optional[threading.Thread] = None

        print(f"[DataManager] Initializing live generator connection to {self.generator_url}...")
        self._initialize_data()
        self._start_background_sync()

    def _initialize_data(self):
        """Initial bootstrap: loads the baseline telemetry dataset, then establishes live generator sync."""
        if os.path.exists(GENERATOR_CSV_FALLBACK):
            print(f"[DataManager] Loading baseline telemetry dataset from {GENERATOR_CSV_FALLBACK}...")
            df_init = pd.read_csv(GENERATOR_CSV_FALLBACK)
        else:
            raise FileNotFoundError(f"Could not locate generator data source at {GENERATOR_CSV_FALLBACK}")

        # Check generator connectivity and sync cursor
        try:
            health_url = f"{self.generator_url}/health"
            req = urllib.request.Request(health_url, headers=get_service_headers())
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                hdata = json.loads(resp.read().decode())
                if hdata.get("status") == "ok":
                    self.is_connected = True
                    self.cursor = hdata.get("rows_emitted", 0)
                    print(f"[DataManager] Connected to live Telemetry Generator API (cursor at frame #{self.cursor}).")
        except Exception:
            self.is_connected = False
            self.cursor = 0
            print(f"[DataManager] Telemetry Generator not currently active on {self.generator_url}. Baseline loaded.")

        # Ensure correct column types and ML evaluation
        self._process_and_evaluate_dataframe(df_init)

    def _process_and_evaluate_dataframe(self, df_raw: pd.DataFrame):
        """Computes coordinates and evaluates ML model predictions on the new data."""
        df = df_raw.copy().reset_index(drop=True)

        # Geodetic coordinates (Lat, Lon, Alt) if missing
        if "latitude" not in df.columns or "longitude" not in df.columns or "altitude_km" not in df.columns:
            lats, lons, alts = [], [], []
            for i, row in df.iterrows():
                r_vec = np.array([float(row.get("position_x", 6800) or 6800),
                                  float(row.get("position_y", 0) or 0),
                                  float(row.get("position_z", 0) or 0)])
                lat, lon, alt = cartesian_to_geodetic(r_vec, gmst_rad=(i * 60.0 * OMEGA_EARTH))
                lats.append(round(lat, 4))
                lons.append(round(lon, 4))
                alts.append(round(alt, 2))
            df["latitude"] = lats
            df["longitude"] = lons
            df["altitude_km"] = alts

        # Run XGBoost ML Health Engine inference on the new data
        print(f"[DataManager] Running XGBoost Health Engine inference on {len(df)} new generator frames...")
        ml_evals = self.ml_engine.predict_batch(df)

        for k in ["health_score", "battery_health", "thermal_health", "power_health", "payload_health",
                  "anomaly_flag", "anomaly_probability", "anomaly_parameter", "anomaly_confidence", "risk_level"]:
            df[k] = [eval_dict[k] for eval_dict in ml_evals]

        # Round floats for clean JSON transmission
        for col in df.select_dtypes(include=[np.floating]).columns:
            df[col] = df[col].astype(float).round(6)

        df["twin_state_id"] = [f"TWIN-{i:06d}" for i in range(len(df))]
        df["source_row_index"] = list(range(len(df)))
        df["sync_status"] = "GENERATOR_LIVE"
        df["state_confidence"] = 1.0

        with self.lock:
            self.df = df
            self._rebuild_anomaly_registry()
            self.last_sync_time = time.time()

        print(f"[DataManager] Generator data ready: {len(self.df)} frames active, {len(self.anomalies)} anomalies identified by ML.")

    def _rebuild_anomaly_registry(self):
        """Extracts anomalies detected by the ML engine on the current generator data."""
        anom_list = []
        for i, row in self.df.iterrows():
            is_anom = bool(row.get("anomaly_flag", False)) or (float(row.get("anomaly_probability", 0) or 0) >= 0.5)
            if is_anom:
                anom_param = row.get("anomaly_parameter", "temperature")
                if not anom_param or anom_param == "none":
                    anom_param = "telemetry_deviation"
                
                desc = f"Anomaly in {str(anom_param).replace('_', ' ').title()} - ML Health Score: {float(row['health_score']):.1f} ({row['risk_level']})"
                anom_list.append({
                    "row_index": int(i),
                    "timestamp": str(row.get("timestamp", "")),
                    "satellite_id": str(row.get("satellite_id", "ISS-25544")),
                    "parameter": anom_param,
                    "confidence": round(float(row.get("anomaly_confidence", 0.95) or 0.95), 3),
                    "health_score": round(float(row["health_score"]), 2),
                    "risk_level": str(row["risk_level"]),
                    "description": desc
                })
        self.anomalies = anom_list

    def _fetch_rows_from_api(self, since: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Queries the generator REST API endpoint."""
        url = f"{self.generator_url}/rows?since={since}&limit={limit}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "COSMOS-DigitalTwin/2.0", **get_service_headers()}
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "rows" in data:
                    return data["rows"]
        except Exception:
            return []
        return []

    def _start_background_sync(self):
        """Starts background poller thread that continuously streams new frames from the generator API."""
        if self._poller_thread and self._poller_thread.is_alive():
            return
        self._stop_event.clear()
        self._poller_thread = threading.Thread(target=self._sync_loop, name="generator-sync-worker", daemon=True)
        self._poller_thread.start()

    def _sync_loop(self):
        """Continuous polling loop that fetches new live frames emitted by generator_api.py."""
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                new_rows = self._fetch_rows_from_api(since=self.cursor, limit=50)
                if new_rows and len(new_rows) > 0:
                    self.is_connected = True
                    consecutive_errors = 0
                    self._ingest_new_frames(new_rows)
                else:
                    # Check health
                    health_url = f"{self.generator_url}/health"
                    try:
                        req = urllib.request.Request(health_url, headers=get_service_headers())
                        with urllib.request.urlopen(req, timeout=1.5) as hresp:
                            hdata = json.loads(hresp.read().decode())
                            self.is_connected = (hdata.get("status") == "ok")
                    except Exception:
                        self.is_connected = False
            except Exception as e:
                consecutive_errors += 1
                self.is_connected = False

            time.sleep(1.0)

    def _ingest_new_frames(self, frames: List[Dict[str, Any]]):
        """Appends new streaming frames, computes ML scores, and updates live telemetry."""
        df_new = pd.DataFrame(frames)
        
        # Ensure geodetics
        if "latitude" not in df_new.columns:
            lats, lons, alts = [], [], []
            for _, r in df_new.iterrows():
                r_vec = np.array([float(r.get("position_x", 6800) or 6800),
                                  float(r.get("position_y", 0) or 0),
                                  float(r.get("position_z", 0) or 0)])
                lat, lon, alt = cartesian_to_geodetic(r_vec)
                lats.append(round(lat, 4))
                lons.append(round(lon, 4))
                alts.append(round(alt, 2))
            df_new["latitude"] = lats
            df_new["longitude"] = lons
            df_new["altitude_km"] = alts

        # ML inference for new frames
        ml_evals = self.ml_engine.predict_batch(df_new)
        for k in ["health_score", "battery_health", "thermal_health", "power_health", "payload_health",
                  "anomaly_flag", "anomaly_probability", "anomaly_parameter", "anomaly_confidence", "risk_level"]:
            df_new[k] = [eval_dict[k] for eval_dict in ml_evals]

        with self.lock:
            start_idx = len(self.df)
            df_new["twin_state_id"] = [f"TWIN-{start_idx + i:06d}" for i in range(len(df_new))]
            df_new["source_row_index"] = list(range(start_idx, start_idx + len(df_new)))
            df_new["sync_status"] = "GENERATOR_LIVE"
            df_new["state_confidence"] = 1.0

            # Concatenate
            self.df = pd.concat([self.df, df_new], ignore_index=True)
            self.cursor += len(frames)
            self._rebuild_anomaly_registry()
            self.last_sync_time = time.time()

        latest = self.df.iloc[-1]
        print(f"[DataManager] Ingested {len(frames)} frames from Generator API (Cursor: {self.cursor}) -> Latest Health Score: {latest['health_score']:.1f}, Risk: {latest['risk_level']}")

    def get_total_rows(self) -> int:
        with self.lock:
            return len(self.df)

    def get_state(self, row_index: int) -> dict:
        with self.lock:
            if len(self.df) == 0:
                return {}
            idx = max(0, min(row_index, len(self.df) - 1))
            return _clean_row(self.df.iloc[idx].to_dict())

    def get_latest_state(self) -> dict:
        with self.lock:
            if len(self.df) == 0:
                return {}
            return _clean_row(self.df.iloc[-1].to_dict())

    def get_history_window(self, end_index: int, window_size: int = 60) -> pd.DataFrame:
        with self.lock:
            if len(self.df) == 0:
                return pd.DataFrame()
            idx = max(0, min(end_index, len(self.df) - 1))
            start_idx = max(0, idx - window_size + 1)
            return self.df.iloc[start_idx : idx + 1].copy()

    def get_timeline(self, start_index: int = 0, count: int = 100, step: int = 1) -> list[dict]:
        with self.lock:
            if len(self.df) == 0:
                return []
            end_idx = min(len(self.df), start_index + count * step)
            sub_df = self.df.iloc[start_index:end_idx:step]
            return [_clean_row(row.to_dict()) for _, row in sub_df.iterrows()]

    def get_anomalies_list(self) -> list[dict]:
        with self.lock:
            return list(self.anomalies)

    def get_connection_status(self) -> dict:
        with self.lock:
            return {
                "generator_url": self.generator_url,
                "is_connected": self.is_connected,
                "cursor": self.cursor,
                "total_rows_ingested": len(self.df),
                "anomalies_detected": len(self.anomalies),
                "last_sync_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_sync_time)) if self.last_sync_time else None
            }

    def compute_ground_truth_validation(self, start_index: int, predicted_trajectory: list[dict]) -> dict:
        """
        Compares the predicted future trajectory with actual rows generated from the stream.
        """
        with self.lock:
            horizon_steps = len(predicted_trajectory)
            end_idx = min(len(self.df), start_index + 1 + horizon_steps)
            actual_slice = self.df.iloc[start_index + 1 : end_idx].reset_index(drop=True)
            
            n_compare = min(len(actual_slice), horizon_steps)
            if n_compare == 0:
                return {"error": "Insufficient future rows available for validation."}

            pos_errors, batt_errors, temp_errors, health_errors = [], [], [], []
            comparison_points = []
            actual_health_vals, pred_health_vals = [], []

            for i in range(n_compare):
                act = actual_slice.iloc[i]
                prd = predicted_trajectory[i]

                r_act = np.array([float(act["position_x"]), float(act["position_y"]), float(act["position_z"])])
                r_prd = np.array([float(prd["position_x"]), float(prd["position_y"]), float(prd["position_z"])])
                pos_err = float(np.linalg.norm(r_act - r_prd))
                pos_errors.append(pos_err)

                b_err = abs(float(act["battery_percentage"]) - float(prd["battery_percentage"]))
                batt_errors.append(b_err)

                t_err = abs(float(act["temperature"]) - float(prd["temperature"]))
                temp_errors.append(t_err)

                h_err = abs(float(act["health_score"]) - float(prd["health_score"]))
                health_errors.append(h_err)
                actual_health_vals.append(float(act["health_score"]))
                pred_health_vals.append(float(prd["health_score"]))

                comparison_points.append({
                    "minute": prd["horizon_minute"],
                    "timestamp": prd["timestamp"],
                    "predicted_health": round(float(prd["health_score"]), 2),
                    "actual_health": round(float(act["health_score"]), 2),
                    "predicted_battery": round(float(prd["battery_percentage"]), 2),
                    "actual_battery": round(float(act["battery_percentage"]), 2),
                    "predicted_temp": round(float(prd["temperature"]), 2),
                    "actual_temp": round(float(act["temperature"]), 2),
                    "trajectory_error_km": round(pos_err, 3),
                    "confidence": prd["state_confidence"]
                })

            mae_h = float(np.mean(health_errors)) if health_errors else 0.0
            accuracy_fit = max(0.0, min(1.0, 1.0 - (mae_h / 100.0)))

            y_true = np.asarray(actual_health_vals, dtype=float)
            y_pred = np.asarray(pred_health_vals, dtype=float)
            ss_res = float(np.sum((y_true - y_pred) ** 2))
            ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
            r2_val = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-3 else accuracy_fit

            return {
                "validation_points_count": n_compare,
                "metrics": {
                    "trajectory_mae_km": round(float(np.mean(pos_errors)), 3),
                    "trajectory_max_error_km": round(float(np.max(pos_errors)), 3),
                    "battery_mae_pct": round(float(np.mean(batt_errors)), 3),
                    "temperature_mae_c": round(float(np.mean(temp_errors)), 3),
                    "health_score_mae": round(mae_h, 3),
                    "health_score_r2": round(max(0.0, min(1.0, r2_val)), 4),
                    "health_score_accuracy_pct": round(accuracy_fit * 100.0, 2),
                },
                "comparison_points": comparison_points
            }
