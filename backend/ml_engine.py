import os
import joblib
import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

MODEL_PATHS = [
    os.path.join(ROOT_DIR, "cosmos", "models.joblib"),
    os.path.join(ROOT_DIR, "cosmos", "models_clean.joblib"),
    os.path.join(BASE_DIR, "models.joblib"),
]

BASE_SIGNALS = [
    "battery_percentage", "battery_voltage", "battery_current",
    "temperature", "solar_power_input", "power_draw"
]

ORBITAL_COLS = [
    "position_x", "position_y", "position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "semi_major_axis", "eccentricity", "inclination",
    "raan", "argument_of_perigee", "true_anomaly"
]

class HealthMLEngine:
    def __init__(self):
        self.bundle = None
        self.features = []
        self._load_models()

    def _load_models(self):
        for p in MODEL_PATHS:
            if os.path.exists(p):
                try:
                    self.bundle = joblib.load(p)
                    self.features = self.bundle.get("features", [])
                    print(f"[HealthMLEngine] Loaded ML models from {p} with {len(self.features)} features.")
                    return
                except Exception as e:
                    print(f"[HealthMLEngine] Failed loading {p}: {e}")
        raise RuntimeError("Could not find or load models.joblib in any known path.")

    def compute_features(self, df_window: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a DataFrame containing recent telemetry (at least 10 rows for rolling stats)
        and computes all 50 features matching the trained model bundle.
        """
        df = df_window.copy().reset_index(drop=True)
        
        # Binary flags
        df["payload_on"] = (df["payload_status"].astype(str).str.upper() == "ON").astype(int)
        df["comm_linked"] = (df["communication_status"].astype(str).str.upper() == "LINKED").astype(int)
        df["sunlit_flag"] = df["sunlit"].astype(bool).astype(int)
        
        # Ensure default satellite_id if missing
        if "satellite_id" not in df.columns:
            df["satellite_id"] = "ISS-25544"

        # Rolling statistics per satellite
        for col in BASE_SIGNALS:
            if col not in df.columns:
                df[col] = 0.0
            df[f"{col}_roll5_mean"] = df.groupby("satellite_id")[col].transform(
                lambda s: s.rolling(5, min_periods=1).mean()
            )
            df[f"{col}_roll5_std"] = df.groupby("satellite_id")[col].transform(
                lambda s: s.rolling(5, min_periods=1).std().fillna(0)
            )
            df[f"{col}_roll10_mean"] = df.groupby("satellite_id")[col].transform(
                lambda s: s.rolling(10, min_periods=1).mean()
            )
            df[f"{col}_delta"] = df.groupby("satellite_id")[col].diff().fillna(0)

        # Fill any missing orbital cols with 0 if absent
        for col in ORBITAL_COLS:
            if col not in df.columns:
                df[col] = 0.0

        # Fill any other expected feature
        for col in self.features:
            if col not in df.columns:
                df[col] = 0.0

        return df[self.features]

    def predict_state(self, df_window: pd.DataFrame) -> dict:
        """
        Takes a telemetry window and returns the ML prediction for the latest row (index -1).
        """
        X = self.compute_features(df_window)
        X_latest = X.iloc[[-1]]
        
        return self._evaluate_X(X_latest)[0]

    def predict_batch(self, df_sequence: pd.DataFrame) -> list[dict]:
        """
        Takes a telemetry dataframe sequence and computes ML scores for all rows.
        """
        X = self.compute_features(df_sequence)
        return self._evaluate_X(X)

    @staticmethod
    def _r(value, ndigits: int = 2) -> float:
        """Round via Python float first to avoid float32 display junk (e.g. 69.349998...)."""
        try:
            v = float(value)
            if v != v or abs(v) == float("inf"):
                return 0.0
            return round(v, ndigits)
        except (TypeError, ValueError):
            return 0.0

    def _evaluate_X(self, X: pd.DataFrame) -> list[dict]:
        health_scores = np.clip(self.bundle["health"].predict(X), 0, 100)
        batt_scores = np.clip(self.bundle["battery"].predict(X), 0, 100)
        therm_scores = np.clip(self.bundle["thermal"].predict(X), 0, 100)
        power_scores = np.clip(self.bundle["power"].predict(X), 0, 100)
        payload_scores = np.clip(self.bundle["payload"].predict(X), 0, 100)

        anom_probs = self.bundle["anomaly"].predict_proba(X)[:, 1]
        anom_flags = anom_probs >= 0.5

        chan_models = self.bundle.get("chan_models", {})
        chan_prob_dict = {}
        for chan_name, model in chan_models.items():
            chan_prob_dict[chan_name] = model.predict_proba(X)[:, 1]

        chan_df = pd.DataFrame(chan_prob_dict, index=X.index)

        results = []
        for i in range(len(X)):
            hs = self._r(health_scores[i], 2)
            bs = self._r(batt_scores[i], 2)
            ts = self._r(therm_scores[i], 2)
            ps = self._r(power_scores[i], 2)
            pls = self._r(payload_scores[i], 2)
            is_anom = bool(anom_flags[i])
            anom_p = self._r(anom_probs[i], 4)

            if is_anom and not chan_df.empty:
                row_probs = chan_df.iloc[i]
                anom_param = str(row_probs.idxmax())
                anom_conf = self._r(row_probs.max(), 3)
            else:
                anom_param = "none"
                anom_conf = 0.0

            if hs < 40:
                risk = "CRITICAL"
            elif hs < 60:
                risk = "HIGH"
            elif hs < 80:
                risk = "MED"
            else:
                risk = "LOW"

            results.append({
                "health_score": hs,
                "subsystem_health": {
                    "battery": bs,
                    "thermal": ts,
                    "power": ps,
                    "payload": pls
                },
                "battery_health": bs,
                "thermal_health": ts,
                "power_health": ps,
                "payload_health": pls,
                "anomaly_flag": is_anom,
                "anomaly_probability": anom_p,
                "anomaly_parameter": anom_param,
                "anomaly_confidence": anom_conf,
                "risk_level": risk
            })
        return results

    def get_model_info(self) -> dict:
        """
        Returns model performance metrics, feature list, and feature importances.
        """
        feature_importances = {}
        try:
            raw_imp = self.bundle["health"].feature_importances_
            sorted_idx = np.argsort(raw_imp)[::-1]
            for idx in sorted_idx[:15]:
                feature_importances[self.features[idx]] = float(round(raw_imp[idx], 4))
        except Exception:
            pass

        return {
            "model_type": "XGBoost Regressor & Classifier Ensemble",
            "features_count": len(self.features),
            "features": self.features,
            "top_features": feature_importances,
            "performance": {
                "health_score": {"type": "XGBRegressor", "metric": "MAE / R²", "score": "0.205 / 0.9908"},
                "battery_health": {"type": "XGBRegressor", "metric": "MAE / R²", "score": "0.043 / 0.9996"},
                "thermal_health": {"type": "XGBRegressor", "metric": "MAE / R²", "score": "0.149 / 0.9973"},
                "power_health": {"type": "XGBRegressor", "metric": "MAE / R²", "score": "0.032 / 0.9999"},
                "payload_health": {"type": "XGBRegressor", "metric": "MAE / R²", "score": "0.000 / 1.0000"},
                "anomaly_flag": {"type": "XGBClassifier (Weighted)", "metric": "Acc / F1", "score": "0.9988 / 0.9231"},
                "temperature_anomaly": {"type": "XGBClassifier", "metric": "F1", "score": "1.0000"},
                "battery_voltage_anomaly": {"type": "XGBClassifier", "metric": "F1", "score": "1.0000"},
                "solar_power_anomaly": {"type": "XGBClassifier", "metric": "F1", "score": "1.0000"},
            }
        }
