"""
COSMOS Health Engine — ML training v2
Improvements over v1:
  1. Class imbalance fix — scale_pos_weight on rare anomaly classes
  2. Hyperparameter tuning — RandomizedSearchCV, 5-fold CV
  3. Engineered features — rolling mean/std, rate-of-change, orbital/position columns
"""
import pandas as pd
import numpy as np
from xgboost import XGBRegressor, XGBClassifier
from sklearn.model_selection import train_test_split, RandomizedSearchCV, KFold
from sklearn.metrics import mean_absolute_error, r2_score, f1_score, accuracy_score
import joblib

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

SRC = os.path.join(ROOT_DIR, "cosmos_twin_dataset.xlsx")
if not os.path.exists(SRC):
    SRC = os.path.join(BASE_DIR, "cosmos_twin_dataset.xlsx")

OUT_MODEL = os.path.join(BASE_DIR, "models.joblib")

tel = pd.read_excel(SRC, sheet_name="Telemetry").sort_values("timestamp").reset_index(drop=True)
anom = pd.read_excel(SRC, sheet_name="Channel_Anomalies")
twin = pd.read_excel(SRC, sheet_name="Twin_Derived")

df = tel.merge(anom, on=["timestamp", "satellite_id"]).merge(
    twin[["timestamp", "satellite_id", "battery_health", "thermal_health",
          "power_health", "payload_health", "health_score",
          "anomaly_flag", "anomaly_parameter", "anomaly_confidence", "risk_level"]],
    on=["timestamp", "satellite_id"]
)

# ---------- feature engineering ----------
df["payload_on"] = (df["payload_status"] == "ON").astype(int)
df["comm_linked"] = (df["communication_status"] == "LINKED").astype(int)
df["sunlit_flag"] = df["sunlit"].astype(int)

BASE_SIGNALS = ["battery_percentage", "battery_voltage", "battery_current",
                "temperature", "solar_power_input", "power_draw"]

# rolling stats (5 min and 10 min windows) — per satellite, time-ordered
for col in BASE_SIGNALS:
    df[f"{col}_roll5_mean"] = df.groupby("satellite_id")[col].transform(
        lambda s: s.rolling(5, min_periods=1).mean())
    df[f"{col}_roll5_std"] = df.groupby("satellite_id")[col].transform(
        lambda s: s.rolling(5, min_periods=1).std().fillna(0))
    df[f"{col}_roll10_mean"] = df.groupby("satellite_id")[col].transform(
        lambda s: s.rolling(10, min_periods=1).mean())
    # rate of change vs previous row
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
y_batt, y_therm, y_power, y_payload = (
    df["battery_health"], df["thermal_health"], df["power_health"], df["payload_health"]
)
y_anom = ((df["temperature_anomaly"] == 1) | (df["battery_voltage_anomaly"] == 1) |
          (df["solar_power_anomaly"] == 1)).astype(int)

idx_train, idx_test = train_test_split(df.index, test_size=0.2, random_state=42, shuffle=True)

# ---------- hyperparameter search space ----------
REG_PARAM_DIST = {
    "n_estimators": [200, 300, 400],
    "max_depth": [3, 4, 5],
    "learning_rate": [0.05, 0.08, 0.1],
    "subsample": [0.8, 0.9, 1.0],
    "colsample_bytree": [0.8, 0.9, 1.0],
}
CLF_PARAM_DIST = dict(REG_PARAM_DIST)

def tune_reg(y, name, n_iter=8):
    base = XGBRegressor(random_state=42, n_jobs=2)
    search = RandomizedSearchCV(
        base, REG_PARAM_DIST, n_iter=n_iter, cv=KFold(3, shuffle=True, random_state=42),
        scoring="neg_mean_absolute_error", random_state=42, n_jobs=4
    )
    search.fit(X.loc[idx_train], y.loc[idx_train])
    best = search.best_estimator_
    pred = best.predict(X.loc[idx_test])
    mae = mean_absolute_error(y.loc[idx_test], pred)
    r2 = r2_score(y.loc[idx_test], pred)
    print(f"[{name}] best_params={search.best_params_}")
    print(f"[{name}] MAE={mae:.4f}  R2={r2:.4f}")
    return best

def tune_clf(y, name, n_iter=8):
    pos = y.loc[idx_train].sum()
    neg = len(idx_train) - pos
    spw = max(1.0, neg / max(pos, 1))  # scale_pos_weight for class imbalance
    base = XGBClassifier(random_state=42, eval_metric="logloss", scale_pos_weight=spw, n_jobs=2)
    search = RandomizedSearchCV(
        base, CLF_PARAM_DIST, n_iter=n_iter, cv=KFold(3, shuffle=True, random_state=42),
        scoring="f1", random_state=42, n_jobs=4
    )
    search.fit(X.loc[idx_train], y.loc[idx_train])
    best = search.best_estimator_
    pred = best.predict(X.loc[idx_test])
    f1 = f1_score(y.loc[idx_test], pred, zero_division=0)
    acc = accuracy_score(y.loc[idx_test], pred)
    print(f"[{name}] best_params={search.best_params_}  scale_pos_weight={spw:.1f}")
    print(f"[{name}] Acc={acc:.4f}  F1={f1:.4f}  (train positives={int(pos)}/{len(idx_train)})")
    return best

print("=== Tuning subsystem + overall health regressors ===")
m_health = tune_reg(y_health, "health_score")
m_batt = tune_reg(y_batt, "battery_health")
m_therm = tune_reg(y_therm, "thermal_health")
m_power = tune_reg(y_power, "power_health")
m_payload = tune_reg(y_payload, "payload_health")

print("\n=== Tuning anomaly classifiers (class-weighted) ===")
m_anom = tune_clf(y_anom, "anomaly_flag")

chan_targets = {
    "temperature": df["temperature_anomaly"],
    "battery_voltage": df["battery_voltage_anomaly"],
    "solar_power_input": df["solar_power_anomaly"],
}
chan_models = {chan: tune_clf(y_c, f"{chan}_anomaly", n_iter=6) for chan, y_c in chan_targets.items()}

# --- save models ---
joblib.dump({
    "health": m_health,
    "battery": m_batt,
    "thermal": m_therm,
    "power": m_power,
    "payload": m_payload,
    "anomaly": m_anom,
    "chan_models": chan_models,
    "features": FEATURES,
}, OUT_MODEL)

print("\nModels saved.")