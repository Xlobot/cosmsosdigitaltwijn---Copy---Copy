"""
Mission Intelligence Configuration
Thresholds, rules, and operational constraints for satellite operations.
"""
import os

# Digital Twin API Configuration
DT_BASE_URL = os.getenv("DIGITAL_TWIN_URL", "http://127.0.0.1:8000")
DT_API_TIMEOUT = 30  # seconds

# Health Thresholds (based on Digital Twin's XGBoost Health Engine)
HEALTH_CRITICAL_THRESHOLD = 40.0
HEALTH_HIGH_THRESHOLD = 60.0
HEALTH_MEDIUM_THRESHOLD = 80.0

# Battery Thresholds
BATTERY_CRITICAL_LOW = 30.0  # percentage
BATTERY_LOW = 50.0  # percentage
BATTERY_WARNING = 70.0  # percentage
BATTERY_OPTIMAL = 85.0  # percentage

# Temperature Thresholds (Celsius)
TEMP_CRITICAL_HIGH = 35.0
TEMP_HIGH = 30.0
TEMP_WARNING_HIGH = 25.0
TEMP_OPTIMAL_MIN = 15.0
TEMP_OPTIMAL_MAX = 25.0
TEMP_WARNING_LOW = 5.0
TEMP_CRITICAL_LOW = 0.0

# Power Thresholds
POWER_CRITICAL_LOW = 5.0  # watts
POWER_LOW = 10.0  # watts
POWER_NORMAL = 20.0  # watts

# Fuel Thresholds
FUEL_CRITICAL_LOW = 20.0  # percentage
FUEL_LOW = 40.0  # percentage
FUEL_WARNING = 60.0  # percentage

# Risk Levels
RISK_LEVELS = ["LOW", "MED", "HIGH", "CRITICAL"]

# Subsystem priorities for ranking
SUBSYSTEM_PRIORITIES = {
    "battery": 1.0,
    "thermal": 0.9,
    "power": 0.85,
    "payload": 0.7,
    "communications": 0.65,
    "attitude": 0.6,
    "orbit": 0.55
}

# Action categories
ACTION_CATEGORIES = {
    "INVESTIGATE": "Gather more information before acting",
    "PAYLOAD_ADJUST": "Modify payload operation mode",
    "THERMAL_ADJUST": "Adjust thermal management",
    "ORBIT_ADJUST": "Orbit maneuvers (delta-v)",
    "POWER_MANAGEMENT": "Optimize power consumption",
    "COMMUNICATIONS": "Manage communication windows",
    "ATTITUDE_CONTROL": "Adjust spacecraft orientation",
    "MONITOR": "Continue monitoring with enhanced attention",
    "EMERGENCY": "Immediate response to critical situation"
}

# Decision log storage
DECISION_LOG_PATH = "mission_intelligence_decision_log.json"

# Data availability status
DATA_STATUS = {
    "CURRENT": "Data is current and fresh",
    "STALE": "Data is older than expected",
    "MISSING": "Data is unavailable",
    "SIMULATED": "Data is from simulation/replay",
    "UNKNOWN": "Data source status unknown"
}

# Prediction horizon for recommendations
DEFAULT_PREDICTION_HORIZON_MINUTES = 60
SHORT_HORIZON_MINUTES = 30
LONG_HORIZON_MINUTES = 120

# Scenario comparison metrics
COMPARISON_METRICS = [
    "health_score",
    "battery_percentage",
    "temperature",
    "anomalies_predicted",
    "fuel_remaining_pct",
    "power_consumption",
    "thermal_stability",
    "mission_success_probability"
]

# Confidence decay model parameters
CONFIDENCE_DECAY_RATE = 0.008  # per minute

# Trend analysis parameters
TREND_WINDOW_SIZE = 10  # number of data points for trend analysis
TREND_THRESHOLD = 0.1  # threshold for significant trend

# Mission priorities
MISSION_PRIORITIES = {
    "SAFETY": 1.0,
    "SCIENCE_DATA": 0.8,
    "MISSION_TIMELINE": 0.75,
    "RESOURCE_CONSERVATION": 0.7,
    "COMMUNICATION": 0.65
}

# Operational modes
OPERATIONAL_MODES = {
    "NOMINAL": "Normal operations",
    "DEGRADED": "Reduced capability mode",
    "SAFE": "Safe mode with minimal power",
    "EMERGENCY": "Emergency response mode"
}

# Forecast error estimation (from Digital Twin prediction tab)
FORECAST_ERROR_MEAN_DEG_C = 2.5  # mean absolute error for temperature
FORECAST_ERROR_STD_DEG_C = 1.8  # standard deviation for temperature
FORECAST_ERROR_MEAN_BATTERY_PCT = 3.0  # mean absolute error for battery
FORECAST_ERROR_STD_BATTERY_PCT = 2.2  # standard deviation for battery

# Model limitations (honest caveats)
MODEL_LIMITATIONS = [
    "Replay data - not live spacecraft telemetry",
    "Health labels are formula-based from Digital Twin ML models",
    "Forecast error: temperature ±" + str(FORECAST_ERROR_MEAN_DEG_C) + "°C (mean), ±" + str(FORECAST_ERROR_STD_DEG_C) + "°C (std)",
    "Forecast error: battery ±" + str(FORECAST_ERROR_MEAN_BATTERY_PCT) + "% (mean), ±" + str(FORECAST_ERROR_STD_BATTERY_PCT) + "% (std)",
    "Actions are advisory only - no spacecraft commands sent",
    "Scenario simulation based on simplified models",
    "Assumes similar operational conditions to training data"
]

# Verdict levels
VERDICT_LEVELS = ["NOMINAL", "WATCH", "CAUTION", "WARNING", "CRITICAL"]
