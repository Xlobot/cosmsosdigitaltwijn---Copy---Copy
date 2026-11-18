"""
Risk Assessment Engine
Identifies relevant anomalies, concerning trends, predicted threshold crossings,
subsystem risks, and potential mission impacts.
Uses existing Health Engine results and configurable rules.
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
    BATTERY_WARNING,
    TEMP_CRITICAL_HIGH,
    TEMP_HIGH,
    TEMP_CRITICAL_LOW,
    TEMP_WARNING_LOW,
    TEMP_WARNING_HIGH,
    FUEL_CRITICAL_LOW,
    FUEL_LOW,
    FUEL_WARNING,
    RISK_LEVELS,
    SUBSYSTEM_PRIORITIES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskAssessmentEngine:
    """
    Assesses mission risks based on current state, predictions,
    and health engine outputs.
    """

    def __init__(self):
        self.risk_rules = self._initialize_risk_rules()

    def _initialize_risk_rules(self) -> List[Dict]:
        """Initialize configurable risk assessment rules."""
        return [
            {
                "id": "R001",
                "name": "Critical Health Score",
                "condition": lambda s: s.get("health_score", 100) < HEALTH_CRITICAL_THRESHOLD,
                "severity": "CRITICAL",
                "subsystem": "overall",
                "description": "Overall health score below critical threshold"
            },
            {
                "id": "R002",
                "name": "Critical Battery Level",
                "condition": lambda s: s.get("battery_percentage", 100) < BATTERY_CRITICAL_LOW,
                "severity": "CRITICAL",
                "subsystem": "battery",
                "description": "Battery level critically low"
            },
            {
                "id": "R003",
                "name": "Critical High Temperature",
                "condition": lambda s: s.get("temperature", 0) > TEMP_CRITICAL_HIGH,
                "severity": "CRITICAL",
                "subsystem": "thermal",
                "description": "Temperature critically high"
            },
            {
                "id": "R004",
                "name": "Critical Low Temperature",
                "condition": lambda s: s.get("temperature", 0) < TEMP_CRITICAL_LOW,
                "severity": "CRITICAL",
                "subsystem": "thermal",
                "description": "Temperature critically low"
            },
            {
                "id": "R005",
                "name": "Active Anomaly",
                "condition": lambda s: s.get("anomaly_flag", False),
                "severity": "HIGH",
                "subsystem": "overall",
                "description": "Anomaly detected by Health Engine"
            },
            {
                "id": "R006",
                "name": "High Risk Level",
                "condition": lambda s: s.get("risk_level", "LOW") == "HIGH",
                "severity": "HIGH",
                "subsystem": "overall",
                "description": "Health Engine reports high risk"
            },
            {
                "id": "R007",
                "name": "Low Battery Warning",
                "condition": lambda s: s.get("battery_percentage", 100) < BATTERY_LOW,
                "severity": "HIGH",
                "subsystem": "battery",
                "description": "Battery level low"
            },
            {
                "id": "R008",
                "name": "High Temperature Warning",
                "condition": lambda s: s.get("temperature", 0) > TEMP_HIGH,
                "severity": "HIGH",
                "subsystem": "thermal",
                "description": "Temperature elevated"
            },
            {
                "id": "R009",
                "name": "Low Temperature Warning",
                "condition": lambda s: s.get("temperature", 0) < TEMP_WARNING_LOW,
                "severity": "MEDIUM",
                "subsystem": "thermal",
                "description": "Temperature below normal range"
            },
            {
                "id": "R010",
                "name": "Battery Depletion Warning",
                "condition": lambda s: s.get("battery_percentage", 100) < BATTERY_WARNING,
                "severity": "MEDIUM",
                "subsystem": "battery",
                "description": "Battery level approaching depletion"
            },
            {
                "id": "R011",
                "name": "Degraded Battery Health",
                "condition": lambda s: s.get("battery_health", 100) < HEALTH_HIGH_THRESHOLD,
                "severity": "MEDIUM",
                "subsystem": "battery",
                "description": "Battery subsystem health degraded"
            },
            {
                "id": "R012",
                "name": "Degraded Thermal Health",
                "condition": lambda s: s.get("thermal_health", 100) < HEALTH_HIGH_THRESHOLD,
                "severity": "MEDIUM",
                "subsystem": "thermal",
                "description": "Thermal subsystem health degraded"
            },
            {
                "id": "R013",
                "name": "Degraded Power Health",
                "condition": lambda s: s.get("power_health", 100) < HEALTH_HIGH_THRESHOLD,
                "severity": "MEDIUM",
                "subsystem": "power",
                "description": "Power subsystem health degraded"
            },
            {
                "id": "R014",
                "name": "Degraded Payload Health",
                "condition": lambda s: s.get("payload_health", 100) < HEALTH_HIGH_THRESHOLD,
                "severity": "MEDIUM",
                "subsystem": "payload",
                "description": "Payload subsystem health degraded"
            },
            {
                "id": "R015",
                "name": "Communication Loss",
                "condition": lambda s: s.get("communication_status", "") != "LINKED",
                "severity": "LOW",
                "subsystem": "communications",
                "description": "No communication link established"
            },
            {
                "id": "R016",
                "name": "Fuel Depletion Warning",
                "condition": lambda s: s.get("fuel_remaining_pct", 100) < FUEL_WARNING,
                "severity": "HIGH",
                "subsystem": "propulsion",
                "description": "Fuel reserves depleted"
            },
            {
                "id": "R017",
                "name": "Critical Fuel Level",
                "condition": lambda s: s.get("fuel_remaining_pct", 100) < FUEL_CRITICAL_LOW,
                "severity": "CRITICAL",
                "subsystem": "propulsion",
                "description": "Fuel critically low"
            },
            {
                "id": "R018",
                "name": "Temperature Warning High",
                "condition": lambda s: s.get("temperature", 0) > TEMP_WARNING_HIGH,
                "severity": "MEDIUM",
                "subsystem": "thermal",
                "description": "Temperature approaching high threshold"
            },
            {
                "id": "R019",
                "name": "Rapid Health Decline",
                "condition": lambda s: s.get("health_score", 100) < s.get("battery_health", 100) - 20,
                "severity": "HIGH",
                "subsystem": "overall",
                "description": "Health score declining faster than subsystem health"
            }
        ]

    def assess_current_risks(
        self,
        state: Dict[str, Any],
        anomalies: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Assess current risks based on state and health engine outputs.
        Returns structured risk assessment with severity levels.
        """
        assessed_at = datetime.utcnow()

        # Evaluate all risk rules
        triggered_risks = []
        for rule in self.risk_rules:
            try:
                if rule["condition"](state):
                    triggered_risks.append({
                        "rule_id": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "subsystem": rule["subsystem"],
                        "description": rule["description"],
                        "evidence": self._extract_evidence(state, rule)
                    })
            except Exception as e:
                logger.warning(f"Error evaluating risk rule {rule['id']}: {e}")

        # Group by severity
        risks_by_severity = self._group_by_severity(triggered_risks)

        # Group by subsystem
        risks_by_subsystem = self._group_by_subsystem(triggered_risks)

        # Calculate overall risk level
        overall_risk = self._calculate_overall_risk(triggered_risks)

        # Identify subsystem-specific risks
        subsystem_risks = self._assess_subsystem_risks(state)

        # Build risk assessment
        assessment = {
            "assessed_at": assessed_at.isoformat(),
            "data_source": state.get("_data_source", "unknown"),
            "overall_risk_level": overall_risk,
            "triggered_risk_count": len(triggered_risks),
            "risks_by_severity": risks_by_severity,
            "risks_by_subsystem": risks_by_subsystem,
            "subsystem_risks": subsystem_risks,
            "triggered_risks": triggered_risks,
            "risk_trend": "unknown",  # Would need historical data for trend
            "recommendation_priority": self._determine_priority(overall_risk)
        }

        return assessment

    def assess_predicted_risks(
        self,
        prediction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess predicted risks based on Digital Twin prediction.
        Returns structured risk assessment for predicted future state.
        """
        assessed_at = datetime.utcnow()

        nominal_pred = prediction.get("nominal_prediction", {})
        summary = nominal_pred.get("summary", {})
        trajectory = nominal_pred.get("trajectory", [])

        if not trajectory:
            return {
                "assessed_at": assessed_at.isoformat(),
                "prediction_source": prediction.get("_data_source", "unknown"),
                "error": "No trajectory data available"
            }

        # Extract final predicted state
        final_state = trajectory[-1] if trajectory else {}

        # Identify predicted risks
        predicted_risks = []

        # Check battery prediction
        min_battery = summary.get("min_battery_pct", 100)
        if min_battery < BATTERY_CRITICAL_LOW:
            predicted_risks.append({
                "type": "battery_critical",
                "severity": "CRITICAL",
                "subsystem": "battery",
                "description": f"Predicted battery will drop to {min_battery:.1f}%",
                "horizon_minutes": prediction.get("horizon_minutes", 0),
                "confidence": final_state.get("state_confidence", 0.0)
            })
        elif min_battery < BATTERY_LOW:
            predicted_risks.append({
                "type": "battery_low",
                "severity": "HIGH",
                "subsystem": "battery",
                "description": f"Predicted battery will drop to {min_battery:.1f}%",
                "horizon_minutes": prediction.get("horizon_minutes", 0),
                "confidence": final_state.get("state_confidence", 0.0)
            })

        # Check temperature prediction
        max_temp = summary.get("max_temperature_c", 0)
        if max_temp > TEMP_CRITICAL_HIGH:
            predicted_risks.append({
                "type": "thermal_high",
                "severity": "CRITICAL",
                "subsystem": "thermal",
                "description": f"Predicted temperature will reach {max_temp:.1f}°C",
                "horizon_minutes": prediction.get("horizon_minutes", 0),
                "confidence": final_state.get("state_confidence", 0.0)
            })
        elif max_temp > TEMP_HIGH:
            predicted_risks.append({
                "type": "thermal_elevated",
                "severity": "HIGH",
                "subsystem": "thermal",
                "description": f"Predicted temperature will reach {max_temp:.1f}°C",
                "horizon_minutes": prediction.get("horizon_minutes", 0),
                "confidence": final_state.get("state_confidence", 0.0)
            })

        # Check predicted anomalies
        anomalies_predicted = summary.get("anomalies_predicted", 0)
        if anomalies_predicted > 0:
            predicted_risks.append({
                "type": "anomaly_predicted",
                "severity": "HIGH",
                "subsystem": "overall",
                "description": f"{anomalies_predicted} anomalies predicted in horizon",
                "horizon_minutes": prediction.get("horizon_minutes", 0),
                "confidence": final_state.get("state_confidence", 0.0)
            })

        # Calculate overall predicted risk
        overall_predicted_risk = self._calculate_overall_risk_from_list(predicted_risks)

        # Build predicted risk assessment
        assessment = {
            "assessed_at": assessed_at.isoformat(),
            "observation_type": "prediction",
            "prediction_source": prediction.get("_data_source", "unknown"),
            "prediction_horizon_minutes": prediction.get("horizon_minutes", 0),
            "overall_predicted_risk_level": overall_predicted_risk,
            "predicted_risk_count": len(predicted_risks),
            "predicted_risks": predicted_risks,
            "confidence": self._estimate_prediction_confidence(trajectory)
        }

        return assessment

    def _extract_evidence(self, state: Dict, rule: Dict) -> Dict:
        """Extract evidence values for a triggered risk rule."""
        evidence = {}

        if "battery" in rule["subsystem"].lower():
            evidence["battery_percentage"] = state.get("battery_percentage", 0)
            evidence["battery_voltage"] = state.get("battery_voltage", 0)
            evidence["battery_health"] = state.get("battery_health", 0)

        if "thermal" in rule["subsystem"].lower():
            evidence["temperature"] = state.get("temperature", 0)
            evidence["thermal_health"] = state.get("thermal_health", 0)

        if "overall" in rule["subsystem"].lower():
            evidence["health_score"] = state.get("health_score", 0)
            evidence["risk_level"] = state.get("risk_level", "UNKNOWN")
            evidence["anomaly_flag"] = state.get("anomaly_flag", False)

        return evidence

    def _group_by_severity(self, risks: List[Dict]) -> Dict[str, List[Dict]]:
        """Group risks by severity level."""
        grouped = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for risk in risks:
            severity = risk.get("severity", "LOW")
            if severity in grouped:
                grouped[severity].append(risk)
        return grouped

    def _group_by_subsystem(self, risks: List[Dict]) -> Dict[str, List[Dict]]:
        """Group risks by subsystem."""
        grouped = {}
        for risk in risks:
            subsystem = risk.get("subsystem", "unknown")
            if subsystem not in grouped:
                grouped[subsystem] = []
            grouped[subsystem].append(risk)
        return grouped

    def _calculate_overall_risk(self, risks: List[Dict]) -> str:
        """Calculate overall risk level from triggered risks."""
        if not risks:
            return "LOW"

        # If any critical risk, overall is critical
        if any(r["severity"] == "CRITICAL" for r in risks):
            return "CRITICAL"

        # If any high risk, overall is high
        if any(r["severity"] == "HIGH" for r in risks):
            return "HIGH"

        # If multiple medium risks, overall is high
        medium_count = sum(1 for r in risks if r["severity"] == "MEDIUM")
        if medium_count >= 2:
            return "HIGH"

        # If any medium risk, overall is medium
        if medium_count >= 1:
            return "MEDIUM"

        return "LOW"

    def _calculate_overall_risk_from_list(self, risks: List[Dict]) -> str:
        """Calculate overall risk from predicted risks list."""
        if not risks:
            return "LOW"

        severities = [r.get("severity", "LOW") for r in risks]

        if "CRITICAL" in severities:
            return "CRITICAL"
        if "HIGH" in severities:
            return "HIGH"
        if severities.count("MEDIUM") >= 2:
            return "HIGH"
        if "MEDIUM" in severities:
            return "MEDIUM"

        return "LOW"

    def _assess_subsystem_risks(self, state: Dict) -> Dict[str, Any]:
        """Assess risk level for each subsystem."""
        return {
            "battery": {
                "health": state.get("battery_health", 100),
                "risk_level": self._subsystem_health_to_risk(state.get("battery_health", 100)),
                "priority": SUBSYSTEM_PRIORITIES.get("battery", 0.5)
            },
            "thermal": {
                "health": state.get("thermal_health", 100),
                "risk_level": self._subsystem_health_to_risk(state.get("thermal_health", 100)),
                "priority": SUBSYSTEM_PRIORITIES.get("thermal", 0.5)
            },
            "power": {
                "health": state.get("power_health", 100),
                "risk_level": self._subsystem_health_to_risk(state.get("power_health", 100)),
                "priority": SUBSYSTEM_PRIORITIES.get("power", 0.5)
            },
            "payload": {
                "health": state.get("payload_health", 100),
                "risk_level": self._subsystem_health_to_risk(state.get("payload_health", 100)),
                "priority": SUBSYSTEM_PRIORITIES.get("payload", 0.5)
            }
        }

    def _subsystem_health_to_risk(self, health: float) -> str:
        """Convert subsystem health score to risk level."""
        if health < HEALTH_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif health < HEALTH_HIGH_THRESHOLD:
            return "HIGH"
        elif health < HEALTH_MEDIUM_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"

    def _determine_priority(self, overall_risk: str) -> str:
        """Determine recommendation priority based on overall risk."""
        if overall_risk == "CRITICAL":
            return "IMMEDIATE"
        elif overall_risk == "HIGH":
            return "HIGH"
        elif overall_risk == "MEDIUM":
            return "MEDIUM"
        else:
            return "LOW"

    def _estimate_prediction_confidence(self, trajectory: List[Dict]) -> float:
        """Estimate prediction confidence from trajectory."""
        if not trajectory:
            return 0.0
        confidences = [row.get("state_confidence", 0.0) for row in trajectory]
        return sum(confidences) / len(confidences) if confidences else 0.0
