"""
Mission Situation Assessor
Combines Digital Twin outputs, telemetry, health assessments, and mission context
to summarize current and predicted mission situation.
Distinguishes observations from predictions and inferences.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .config import (
    HEALTH_CRITICAL_THRESHOLD,
    HEALTH_HIGH_THRESHOLD,
    HEALTH_MEDIUM_THRESHOLD,
    BATTERY_CRITICAL_LOW,
    BATTERY_LOW,
    TEMP_CRITICAL_HIGH,
    TEMP_CRITICAL_LOW
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SituationAssessor:
    """
    Assesses the current and predicted mission situation based on
    Digital Twin outputs and health engine results.
    """

    def __init__(self):
        self.current_state = None
        self.prediction = None
        self.assessed_at = None

    def assess_current_situation(
        self,
        state: Dict[str, Any],
        anomalies: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Assess current mission situation from Digital Twin state.
        Returns structured situation summary with observations only.
        """
        self.current_state = state
        self.assessed_at = datetime.utcnow()

        # Extract key metrics
        health_score = state.get("health_score", 0.0)
        battery_pct = state.get("battery_percentage", 0.0)
        temperature = state.get("temperature", 0.0)
        risk_level = state.get("risk_level", "UNKNOWN")
        anomaly_flag = state.get("anomaly_flag", False)

        # Determine overall status
        overall_status = self._determine_overall_status(
            health_score, battery_pct, temperature, risk_level, anomaly_flag
        )

        # Identify subsystem status
        subsystem_status = {
            "battery": self._assess_battery(battery_pct),
            "thermal": self._assess_thermal(temperature),
            "power": self._assess_power(state),
            "payload": self._assess_payload(state)
        }

        # Identify active anomalies
        active_anomalies = self._identify_active_anomalies(anomalies, state)

        # Build situation summary
        situation = {
            "assessed_at": self.assessed_at.isoformat(),
            "data_source": state.get("_data_source", "unknown"),
            "data_status": state.get("_data_status", "unknown"),
            "observation_type": "current_state",  # Not a prediction
            "overall_status": overall_status,
            "health_summary": {
                "score": health_score,
                "level": self._health_level_to_text(health_score),
                "risk": risk_level
            },
            "subsystem_status": subsystem_status,
            "resource_status": {
                "battery": {
                    "percentage": battery_pct,
                    "status": self._assess_battery(battery_pct),
                    "voltage": state.get("battery_voltage", 0.0)
                },
                "thermal": {
                    "temperature_c": temperature,
                    "status": self._assess_thermal(temperature)
                },
                "fuel": {
                    "percentage": state.get("fuel_remaining_pct", 0.0),
                    "status": "adequate" if state.get("fuel_remaining_pct", 0) > 50 else "low"
                }
            },
            "anomaly_status": {
                "active": anomaly_flag,
                "count": len(active_anomalies),
                "active_anomalies": active_anomalies[:5]  # Limit to top 5
            },
            "operational_context": {
                "timestamp": state.get("timestamp", "unknown"),
                "payload_status": state.get("payload_status", "unknown"),
                "communication_status": state.get("communication_status", "unknown"),
                "sunlit": state.get("sunlit", False)
            },
            "concerns": self._identify_concerns(
                health_score, battery_pct, temperature, risk_level, anomaly_flag
            )
        }

        return situation

    def assess_predicted_situation(
        self,
        prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess predicted mission situation from Digital Twin prediction.
        Returns structured situation summary with predictions clearly marked.
        """
        self.prediction = prediction
        self.assessed_at = datetime.utcnow()

        nominal_pred = prediction.get("nominal_prediction", {})
        trajectory = nominal_pred.get("trajectory", [])
        summary = nominal_pred.get("summary", {})

        if not trajectory:
            return {
                "assessed_at": self.assessed_at.isoformat(),
                "observation_type": "prediction",
                "prediction_source": prediction.get("_data_source", "unknown"),
                "error": "No trajectory data available"
            }

        # Extract final predicted state
        final_state = trajectory[-1] if trajectory else {}
        final_health = summary.get("final_health_score", 0.0)
        final_battery = summary.get("final_battery_pct", 0.0)
        final_temp = summary.get("final_temperature_c", 0.0)
        min_battery = summary.get("min_battery_pct", 0.0)
        max_temp = summary.get("max_temperature_c", 0.0)
        anomalies_predicted = summary.get("anomalies_predicted", 0)

        # Determine predicted status
        predicted_status = self._determine_overall_status(
            final_health, final_battery, final_temp,
            summary.get("final_risk_level", "UNKNOWN"),
            anomalies_predicted > 0
        )

        # Identify predicted concerns
        predicted_concerns = []
        if min_battery < BATTERY_CRITICAL_LOW:
            predicted_concerns.append({
                "type": "battery_critical",
                "severity": "critical",
                "message": f"Predicted battery will drop to {min_battery:.1f}%"
            })
        elif min_battery < BATTERY_LOW:
            predicted_concerns.append({
                "type": "battery_low",
                "severity": "high",
                "message": f"Predicted battery will drop to {min_battery:.1f}%"
            })

        if max_temp > TEMP_CRITICAL_HIGH:
            predicted_concerns.append({
                "type": "thermal_high",
                "severity": "critical",
                "message": f"Predicted temperature will reach {max_temp:.1f}°C"
            })

        if anomalies_predicted > 0:
            predicted_concerns.append({
                "type": "anomaly_predicted",
                "severity": "high",
                "message": f"{anomalies_predicted} anomalies predicted in horizon"
            })

        # Build prediction summary
        situation = {
            "assessed_at": self.assessed_at.isoformat(),
            "observation_type": "prediction",  # Clearly marked as prediction
            "prediction_source": prediction.get("_data_source", "unknown"),
            "prediction_horizon_minutes": prediction.get("horizon_minutes", 0),
            "prediction_confidence": self._estimate_prediction_confidence(trajectory),
            "predicted_status": predicted_status,
            "predicted_final_state": {
                "health_score": final_health,
                "battery_percentage": final_battery,
                "temperature_c": final_temp,
                "fuel_percentage": summary.get("fuel_remaining_pct", 0.0),
                "risk_level": summary.get("final_risk_level", "UNKNOWN")
            },
            "predicted_extremes": {
                "min_battery_pct": min_battery,
                "max_temperature_c": max_temp,
                "anomalies_predicted": anomalies_predicted
            },
            "predicted_concerns": predicted_concerns,
            "validation_metrics": prediction.get("ground_truth_validation", None)
        }

        return situation

    def _determine_overall_status(
        self,
        health_score: float,
        battery_pct: float,
        temperature: float,
        risk_level: str,
        anomaly_flag: bool
    ) -> str:
        """Determine overall mission status."""
        if anomaly_flag or risk_level == "CRITICAL":
            return "CRITICAL"
        if health_score < HEALTH_CRITICAL_THRESHOLD:
            return "CRITICAL"
        if battery_pct < BATTERY_CRITICAL_LOW:
            return "CRITICAL"
        if temperature > TEMP_CRITICAL_HIGH or temperature < TEMP_CRITICAL_LOW:
            return "CRITICAL"

        if health_score < HEALTH_HIGH_THRESHOLD:
            return "HIGH_RISK"
        if battery_pct < BATTERY_LOW:
            return "HIGH_RISK"
        if risk_level == "HIGH":
            return "HIGH_RISK"

        if health_score < HEALTH_MEDIUM_THRESHOLD:
            return "MEDIUM_RISK"
        if risk_level == "MED":
            return "MEDIUM_RISK"

        return "NOMINAL"

    def _assess_battery(self, battery_pct: float) -> str:
        """Assess battery status."""
        if battery_pct < BATTERY_CRITICAL_LOW:
            return "critical"
        elif battery_pct < BATTERY_LOW:
            return "low"
        elif battery_pct < 80:
            return "depleted"
        else:
            return "nominal"

    def _assess_thermal(self, temperature: float) -> str:
        """Assess thermal status."""
        if temperature > TEMP_CRITICAL_HIGH:
            return "critical_high"
        elif temperature > 30:
            return "high"
        elif temperature < TEMP_CRITICAL_LOW:
            return "critical_low"
        elif temperature < 5:
            return "low"
        else:
            return "nominal"

    def _assess_power(self, state: Dict) -> str:
        """Assess power status."""
        power_health = state.get("power_health", 0.0)
        if power_health < HEALTH_CRITICAL_THRESHOLD:
            return "critical"
        elif power_health < HEALTH_HIGH_THRESHOLD:
            return "degraded"
        else:
            return "nominal"

    def _assess_payload(self, state: Dict) -> str:
        """Assess payload status."""
        payload_health = state.get("payload_health", 0.0)
        payload_status = state.get("payload_status", "UNKNOWN")
        if payload_health < HEALTH_CRITICAL_THRESHOLD:
            return "critical"
        elif payload_status == "STANDBY":
            return "standby"
        elif payload_status == "ON":
            return "operational"
        else:
            return "unknown"

    def _identify_active_anomalies(
        self,
        anomalies: Optional[List[Dict]],
        state: Dict
    ) -> List[Dict]:
        """Identify anomalies relevant to current state."""
        if not anomalies:
            return []

        # If state has anomaly flag, include anomaly details
        if state.get("anomaly_flag", False):
            return [{
                "parameter": state.get("anomaly_parameter", "unknown"),
                "confidence": state.get("anomaly_confidence", 0.0),
                "probability": state.get("anomaly_probability", 0.0)
            }]

        return []

    def _identify_concerns(
        self,
        health_score: float,
        battery_pct: float,
        temperature: float,
        risk_level: str,
        anomaly_flag: bool
    ) -> List[Dict]:
        """Identify current concerns based on state."""
        concerns = []

        if anomaly_flag:
            concerns.append({
                "type": "anomaly",
                "severity": "high",
                "message": "Anomaly detected by Health Engine"
            })

        if health_score < HEALTH_CRITICAL_THRESHOLD:
            concerns.append({
                "type": "health_critical",
                "severity": "critical",
                "message": f"Health score critically low: {health_score:.1f}"
            })

        if battery_pct < BATTERY_CRITICAL_LOW:
            concerns.append({
                "type": "battery_critical",
                "severity": "critical",
                "message": f"Battery critically low: {battery_pct:.1f}%"
            })

        if temperature > TEMP_CRITICAL_HIGH:
            concerns.append({
                "type": "thermal_high",
                "severity": "critical",
                "message": f"Temperature critically high: {temperature:.1f}°C"
            })

        if temperature < TEMP_CRITICAL_LOW:
            concerns.append({
                "type": "thermal_low",
                "severity": "critical",
                "message": f"Temperature critically low: {temperature:.1f}°C"
            })

        return concerns

    def _health_level_to_text(self, health_score: float) -> str:
        """Convert health score to text level."""
        if health_score < HEALTH_CRITICAL_THRESHOLD:
            return "critical"
        elif health_score < HEALTH_HIGH_THRESHOLD:
            return "high_risk"
        elif health_score < HEALTH_MEDIUM_THRESHOLD:
            return "medium_risk"
        else:
            return "nominal"

    def _estimate_prediction_confidence(self, trajectory: List[Dict]) -> float:
        """Estimate prediction confidence from trajectory confidence decay."""
        if not trajectory:
            return 0.0

        # Use average confidence across trajectory
        confidences = [row.get("state_confidence", 0.0) for row in trajectory]
        return sum(confidences) / len(confidences) if confidences else 0.0
