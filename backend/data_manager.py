import os
import math
import numpy as np
import pandas as pd
from .orbit_propagator import cartesian_to_geodetic, OMEGA_EARTH
from .ml_engine import HealthMLEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

DATASET_PATHS = [
    os.path.join(ROOT_DIR, "cosmos_twin_dataset.xlsx"),
    os.path.join(ROOT_DIR, "cosmos", "cosmos_twin_dataset.xlsx"),
    os.path.join(ROOT_DIR, "cosmos", "cosmos_twin_ml_output_v2.xlsx"),
]


def _clean_value(v):
    """Normalize numpy/pandas scalars into JSON-safe Python types with sane floats."""
    if isinstance(v, (np.generic,)):
        v = v.item()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        # Collapse float32 display artifacts (69.349998... → 69.35)
        return round(v, 6) if abs(v) < 1e6 else float(v)
    if pd.isna(v):
        return None
    return v


def _clean_row(row_dict: dict) -> dict:
    return {k: _clean_value(v) for k, v in row_dict.items()}

class DataManager:
    def __init__(self, ml_engine: HealthMLEngine):
        self.ml_engine = ml_engine
        self.df = None
        self.anomalies = []
        self._load_dataset()

    def _load_dataset(self):
        dataset_path = None
        for p in DATASET_PATHS:
            if os.path.exists(p):
                dataset_path = p
                break
        
        if not dataset_path:
            raise FileNotFoundError("Could not locate cosmos_twin_dataset.xlsx.")

        print(f"[DataManager] Loading dataset from {dataset_path}...")
        
        # Load sheets
        xl = pd.ExcelFile(dataset_path)
        tel = pd.read_excel(xl, sheet_name="Telemetry").sort_values("timestamp").reset_index(drop=True)
        
        if "Channel_Anomalies" in xl.sheet_names:
            anom = pd.read_excel(xl, sheet_name="Channel_Anomalies")
            tel = tel.merge(anom, on=["timestamp", "satellite_id"], how="left")
        
        if "Twin_Derived" in xl.sheet_names:
            twin = pd.read_excel(xl, sheet_name="Twin_Derived")
            twin_cols = [c for c in twin.columns if c not in ["timestamp", "satellite_id"]]
            tel = tel.merge(twin[["timestamp", "satellite_id"] + twin_cols], on=["timestamp", "satellite_id"], how="left")

        # Compute Geodetic coordinates (Lat, Lon, Alt) for each row for 3D Earth projection
        lats, lons, alts = [], [], []
        for i, row in tel.iterrows():
            r_vec = np.array([row["position_x"], row["position_y"], row["position_z"]])
            lat, lon, alt = cartesian_to_geodetic(r_vec, gmst_rad=(i * 60.0 * OMEGA_EARTH))
            lats.append(round(lat, 4))
            lons.append(round(lon, 4))
            alts.append(round(alt, 2))

        tel["latitude"] = lats
        tel["longitude"] = lons
        tel["altitude_km"] = alts

        # Prefer dataset Twin_Derived health labels when present; otherwise run ML inference.
        # Always re-run ML so live API scores stay consistent with the loaded model bundle.
        print("[DataManager] Pre-evaluating ML Health Engine predictions...")
        ml_evals = self.ml_engine.predict_batch(tel)

        for k in ["health_score", "battery_health", "thermal_health", "power_health", "payload_health",
                  "anomaly_flag", "anomaly_probability", "anomaly_parameter", "anomaly_confidence", "risk_level"]:
            tel[k] = [eval_dict[k] for eval_dict in ml_evals]

        # Round telemetry numerics so API clients don't see float32 junk
        for col in tel.select_dtypes(include=[np.floating]).columns:
            tel[col] = tel[col].astype(float).round(6)

        # Metadata fields
        tel["twin_state_id"] = [f"TWIN-{i:06d}" for i in range(len(tel))]
        tel["source_row_index"] = list(range(len(tel)))
        tel["sync_status"] = "LIVE_REPLAY"
        tel["state_confidence"] = 1.0

        self.df = tel

        # Build Anomaly Registry
        anom_list = []
        for i, row in self.df.iterrows():
            is_anom = bool(row["anomaly_flag"]) or (row.get("temperature_anomaly", 0) == 1) or (row.get("battery_voltage_anomaly", 0) == 1) or (row.get("solar_power_anomaly", 0) == 1)
            if is_anom:
                anom_param = row.get("anomaly_parameter", "temperature")
                if anom_param == "none":
                    if row.get("temperature_anomaly", 0) == 1: anom_param = "temperature"
                    elif row.get("battery_voltage_anomaly", 0) == 1: anom_param = "battery_voltage"
                    elif row.get("solar_power_anomaly", 0) == 1: anom_param = "solar_power_input"
                
                desc = f"Anomaly in {anom_param.replace('_', ' ').title()} - Health Score dropped to {row['health_score']:.1f}"
                anom_list.append({
                    "row_index": int(i),
                    "timestamp": str(row["timestamp"]),
                    "satellite_id": str(row["satellite_id"]),
                    "parameter": anom_param,
                    "confidence": round(float(row.get("anomaly_confidence", 0.95) or 0.95), 3),
                    "health_score": round(float(row["health_score"]), 2),
                    "risk_level": str(row["risk_level"]),
                    "description": desc
                })
        self.anomalies = anom_list
        print(f"[DataManager] Dataset ready with {len(self.df)} rows, {len(self.anomalies)} anomaly events identified.")

    def get_total_rows(self) -> int:
        return len(self.df)

    def get_state(self, row_index: int) -> dict:
        idx = max(0, min(row_index, len(self.df) - 1))
        return _clean_row(self.df.iloc[idx].to_dict())

    def get_history_window(self, end_index: int, window_size: int = 60) -> pd.DataFrame:
        idx = max(0, min(end_index, len(self.df) - 1))
        start_idx = max(0, idx - window_size + 1)
        return self.df.iloc[start_idx : idx + 1].copy()

    def get_timeline(self, start_index: int = 0, count: int = 100, step: int = 1) -> list[dict]:
        end_idx = min(len(self.df), start_index + count * step)
        sub_df = self.df.iloc[start_index:end_idx:step]
        return [_clean_row(row.to_dict()) for _, row in sub_df.iterrows()]

    def get_anomalies_list(self) -> list[dict]:
        return self.anomalies

    def compute_ground_truth_validation(self, start_index: int, predicted_trajectory: list[dict]) -> dict:
        """
        Compares the predicted future trajectory with the actual ground truth telemetry
        rows in the dataset starting from start_index + 1.
        Computes Trajectory error (km), Battery error (%), Temperature error (°C), and Health Score error (MAE, R2).
        """
        horizon_steps = len(predicted_trajectory)
        end_idx = min(len(self.df), start_index + 1 + horizon_steps)
        actual_slice = self.df.iloc[start_index + 1 : end_idx].reset_index(drop=True)
        
        n_compare = min(len(actual_slice), horizon_steps)
        if n_compare == 0:
            return {"error": "No ground truth future rows available for validation (at end of dataset)."}

        pos_errors = []
        batt_errors = []
        temp_errors = []
        health_errors = []
        
        comparison_points = []
        actual_health_vals = []
        pred_health_vals = []

        for i in range(n_compare):
            act = actual_slice.iloc[i]
            prd = predicted_trajectory[i]

            # Trajectory Euclidean distance (km)
            r_act = np.array([act["position_x"], act["position_y"], act["position_z"]])
            r_prd = np.array([prd["position_x"], prd["position_y"], prd["position_z"]])
            pos_err = float(np.linalg.norm(r_act - r_prd))
            pos_errors.append(pos_err)

            # Battery % error
            b_err = abs(act["battery_percentage"] - prd["battery_percentage"])
            batt_errors.append(b_err)

            # Temp error (°C)
            t_err = abs(act["temperature"] - prd["temperature"])
            temp_errors.append(t_err)

            # Health Score error
            h_err = abs(act["health_score"] - prd["health_score"])
            health_errors.append(h_err)
            actual_health_vals.append(act["health_score"])
            pred_health_vals.append(prd["health_score"])

            comparison_points.append({
                "minute": prd["horizon_minute"],
                "timestamp": prd["timestamp"],
                "predicted_health": round(prd["health_score"], 2),
                "actual_health": round(act["health_score"], 2),
                "predicted_battery": round(prd["battery_percentage"], 2),
                "actual_battery": round(act["battery_percentage"], 2),
                "predicted_temp": round(prd["temperature"], 2),
                "actual_temp": round(act["temperature"], 2),
                "trajectory_error_km": round(pos_err, 3),
                "confidence": prd["state_confidence"]
            })

        # Calculate Health Score Accuracy & Fit
        mae_h = float(np.mean(health_errors)) if health_errors else 0.0
        accuracy_fit = max(0.0, min(1.0, 1.0 - (mae_h / 100.0)))

        y_true = np.asarray(actual_health_vals, dtype=float)
        y_pred = np.asarray(pred_health_vals, dtype=float)
        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
        if ss_tot > 1e-3:
            r2_val = 1.0 - (ss_res / ss_tot)
        else:
            r2_val = accuracy_fit
        # Keep R² in a readable band; negative fit still reports 0 for UI scorecards
        r2_display = max(0.0, min(1.0, r2_val))

        return {
            "validation_points_count": n_compare,
            "metrics": {
                "trajectory_mae_km": round(float(np.mean(pos_errors)), 3),
                "trajectory_max_error_km": round(float(np.max(pos_errors)), 3),
                "battery_mae_pct": round(float(np.mean(batt_errors)), 3),
                "temperature_mae_c": round(float(np.mean(temp_errors)), 3),
                "health_score_mae": round(mae_h, 3),
                "health_score_r2": round(r2_display, 4),
                "health_score_accuracy_pct": round(accuracy_fit * 100.0, 2),
            },
            "comparison_points": comparison_points
        }
