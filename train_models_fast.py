import os
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBRegressor, XGBClassifier

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(base_dir, "cosmos_twin_dataset.xlsx")
    if not os.path.exists(src):
        src = os.path.join(base_dir, "cosmos", "cosmos_twin_dataset.xlsx")

    print(f"Loading dataset from {src}...")
    tel = pd.read_excel(src, sheet_name="Telemetry").sort_values("timestamp").reset_index(drop=True)
    anom = pd.read_excel(src, sheet_name="Channel_Anomalies")
    twin = pd.read_excel(src, sheet_name="Twin_Derived")

    df = tel.merge(anom, on=["timestamp", "satellite_id"]).merge(
        twin[["timestamp", "satellite_id", "battery_health", "thermal_health",
              "power_health", "payload_health", "health_score",
              "anomaly_flag", "anomaly_parameter", "anomaly_confidence", "risk_level"]],
        on=["timestamp", "satellite_id"]
    )

    df["payload_on"] = (df["payload_status"] == "ON").astype(int)
    df["comm_linked"] = (df["communication_status"] == "LINKED").astype(int)
    df["sunlit_flag"] = df["sunlit"].astype(int)

    BASE_SIGNALS = ["battery_percentage", "battery_voltage", "battery_current",
                    "temperature", "solar_power_input", "power_draw"]

    for col in BASE_SIGNALS:
        df[f"{col}_roll5_mean"] = df.groupby("satellite_id")[col].transform(
            lambda s: s.rolling(5, min_periods=1).mean())
        df[f"{col}_roll5_std"] = df.groupby("satellite_id")[col].transform(
            lambda s: s.rolling(5, min_periods=1).std().fillna(0))
        df[f"{col}_roll10_mean"] = df.groupby("satellite_id")[col].transform(
            lambda s: s.rolling(10, min_periods=1).mean())
        df[f"{col}_delta"] = df.groupby("satellite_id")[col].diff().fillna(0)

    ORBITAL_COLS = ["position_x", "position_y", "position_z",
                     "velocity_x", "velocity_y", "velocity_z",
                     "semi_major_axis", "eccentricity", "inclination",
                     "raan", "argument_of_perigee", "true_anomaly"]

    FEATURES = (
        BASE_SIGNALS
        + ["payload_power_draw", "fuel_remaining_pct", "payload_on", "comm_linked", "sunlit_flag",
           "angular_velocity_x", "angular_velocity_y", "angular_velocity_z"]
        + [f"{c}_roll5_mean" for c in BASE_SIGNALS]
        + [f"{c}_roll5_std" for c in BASE_SIGNALS]
        + [f"{c}_roll10_mean" for c in BASE_SIGNALS]
        + [f"{c}_delta" for c in BASE_SIGNALS]
        + ORBITAL_COLS
    )

    X = df[FEATURES]
    y_health = df["health_score"]
    y_batt = df["battery_health"]
    y_therm = df["thermal_health"]
    y_power = df["power_health"]
    y_payload = df["payload_health"]
    y_anom = ((df["temperature_anomaly"] == 1) | (df["battery_voltage_anomaly"] == 1) |
              (df["solar_power_anomaly"] == 1)).astype(int)

    def train_reg(y, name):
        print(f"Training regressor for {name}...")
        model = XGBRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            n_jobs=1
        )
        model.fit(X, y)
        return model

    def train_clf(y, name):
        pos = y.sum()
        neg = len(y) - pos
        spw = max(1.0, neg / max(pos, 1))
        print(f"Training classifier for {name} (scale_pos_weight={spw:.1f})...")
        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            scale_pos_weight=spw,
            eval_metric="logloss",
            random_state=42,
            n_jobs=1
        )
        model.fit(X, y)
        return model

    m_health = train_reg(y_health, "health_score")
    m_batt = train_reg(y_batt, "battery_health")
    m_therm = train_reg(y_therm, "thermal_health")
    m_power = train_reg(y_power, "power_health")
    m_payload = train_reg(y_payload, "payload_health")

    m_anom = train_clf(y_anom, "anomaly_flag")

    chan_targets = {
        "temperature": df["temperature_anomaly"],
        "battery_voltage": df["battery_voltage_anomaly"],
        "solar_power_input": df["solar_power_anomaly"],
    }
    chan_models = {chan: train_clf(y_c, f"{chan}_anomaly") for chan, y_c in chan_targets.items()}

    bundle = {
        "health": m_health,
        "battery": m_batt,
        "thermal": m_therm,
        "power": m_power,
        "payload": m_payload,
        "anomaly": m_anom,
        "chan_models": chan_models,
        "features": FEATURES,
    }

    out_paths = [
        os.path.join(base_dir, "cosmos", "models.joblib"),
        os.path.join(base_dir, "cosmos", "models_clean.joblib"),
        os.path.join(base_dir, "backend", "models.joblib"),
    ]

    for p in out_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        joblib.dump(bundle, p)
        print(f"Saved bundle to {p} (size={os.path.getsize(p)} bytes)")

    print("All models successfully trained and saved!")

if __name__ == "__main__":
    main()
