"""
Prediction Analyzer
Analyzes Digital Twin predictions to detect limit crossings and provide forecasts.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .config import (
    TEMP_CRITICAL_LOW,
    TEMP_WARNING_LOW,
    TEMP_WARNING_HIGH,
    TEMP_CRITICAL_HIGH,
    BATTERY_CRITICAL_LOW,
    BATTERY_LOW,
    BATTERY_WARNING,
    FORECAST_ERROR_MEAN_DEG_C,
    FORECAST_ERROR_STD_DEG_C,
    FORECAST_ERROR_MEAN_BATTERY_PCT,
    FORECAST_ERROR_STD_BATTERY_PCT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictionAnalyzer:
    """
    Analyzes predictions to detect when limits will be crossed.
    Provides time-to-limit estimates with uncertainty ranges.
    """

    def __init__(self):
        pass

    def analyze_predictions(
        self,
        current_state: Dict[str, Any],
        prediction_trajectory: List[Dict[str, Any]],
        horizon_minutes: int
    ) -> Dict[str, Any]:
        """
        Analyze prediction trajectory for limit crossings.
        """
        analyzed_at = datetime.utcnow()

        # Extract time series
        temperatures = [p.get("temperature_c", 0) for p in prediction_trajectory]
        batteries = [p.get("battery_percentage", 100) for p in prediction_trajectory]
        timestamps = [p.get("timestamp_minutes", i * 5) for i, p in enumerate(prediction_trajectory)]

        # Detect limit crossings
        temp_crossings = self._detect_limit_crossings(
            temperatures, timestamps,
            TEMP_CRITICAL_LOW, TEMP_WARNING_LOW, TEMP_WARNING_HIGH, TEMP_CRITICAL_HIGH,
            "temperature", "°C"
        )

        battery_crossings = self._detect_limit_crossings(
            batteries, timestamps,
            BATTERY_CRITICAL_LOW, BATTERY_LOW, BATTERY_WARNING, 100.0,
            "battery", "%"
        )

        # Generate forecast charts data
        temp_forecast = self._generate_forecast_data(
            temperatures, timestamps, current_state.get("temperature_c", 0),
            FORECAST_ERROR_MEAN_DEG_C, FORECAST_ERROR_STD_DEG_C
        )

        battery_forecast = self._generate_forecast_data(
            batteries, timestamps, current_state.get("battery_percentage", 100),
            FORECAST_ERROR_MEAN_BATTERY_PCT, FORECAST_ERROR_STD_BATTERY_PCT
        )

        return {
            "analyzed_at": analyzed_at.isoformat(),
            "temperature_forecast": temp_forecast,
            "battery_forecast": battery_forecast,
            "limit_crossings": {
                "temperature": temp_crossings,
                "battery": battery_crossings
            },
            "uncertainty_ranges": {
                "temperature": {
                    "mean_error_deg_c": FORECAST_ERROR_MEAN_DEG_C,
                    "std_error_deg_c": FORECAST_ERROR_STD_DEG_C
                },
                "battery": {
                    "mean_error_pct": FORECAST_ERROR_MEAN_BATTERY_PCT,
                    "std_error_pct": FORECAST_ERROR_STD_BATTERY_PCT
                }
            }
        }

    def _detect_limit_crossings(
        self,
        values: List[float],
        timestamps: List[float],
        critical_low: float,
        warning_low: float,
        warning_high: Optional[float] = None,
        critical_high: Optional[float] = None,
        metric_name: str = "value",
        unit: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Detect when values cross critical/warning thresholds.
        """
        crossings = []

        for i, (value, time_min) in enumerate(zip(values, timestamps)):
            crossing_type = None
            threshold = None

            if value <= critical_low:
                crossing_type = "CRITICAL_LOW"
                threshold = critical_low
            elif value <= warning_low:
                crossing_type = "WARNING_LOW"
                threshold = warning_low
            elif critical_high and value >= critical_high:
                crossing_type = "CRITICAL_HIGH"
                threshold = critical_high
            elif warning_high and value >= warning_high:
                crossing_type = "WARNING_HIGH"
                threshold = warning_high

            if crossing_type:
                crossings.append({
                    "time_minutes": time_min,
                    "value": value,
                    "threshold": threshold,
                    "crossing_type": crossing_type,
                    "metric_name": metric_name,
                    "unit": unit
                })

        return crossings

    def _generate_forecast_data(
        self,
        values: List[float],
        timestamps: List[float],
        current_value: float,
        mean_error: float,
        std_error: float
    ) -> Dict[str, Any]:
        """
        Generate forecast data with uncertainty ranges.
        """
        forecast_points = []

        for value, time_min in zip(values, timestamps):
            # Calculate uncertainty bounds
            upper_bound = value + mean_error + std_error
            lower_bound = value - mean_error - std_error

            forecast_points.append({
                "time_minutes": time_min,
                "predicted_value": value,
                "upper_bound": upper_bound,
                "lower_bound": lower_bound
            })

        return {
            "current_value": current_value,
            "mean_error": mean_error,
            "std_error": std_error,
            "trajectory": forecast_points
        }

    def get_time_to_limit(
        self,
        current_value: float,
        trajectory: List[float],
        timestamps: List[float],
        limit: float,
        direction: str = "below"  # "below" or "above"
    ) -> Optional[Dict[str, Any]]:
        """
        Estimate time until limit is crossed.
        """
        for value, time_min in zip(trajectory, timestamps):
            if direction == "below" and value <= limit:
                return {
                    "time_minutes": time_min,
                    "limit": limit,
                    "direction": direction
                }
            elif direction == "above" and value >= limit:
                return {
                    "time_minutes": time_min,
                    "limit": limit,
                    "direction": direction
                }

        return None
