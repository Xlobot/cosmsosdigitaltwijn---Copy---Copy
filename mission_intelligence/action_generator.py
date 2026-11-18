"""
Candidate Action Generator
Generates feasible candidate actions based on available evidence and mission constraints.
Actions are context-aware and only generated when they make sense for the current situation.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .config import (
    ACTION_CATEGORIES,
    BATTERY_CRITICAL_LOW,
    BATTERY_LOW,
    BATTERY_WARNING,
    BATTERY_OPTIMAL,
    TEMP_CRITICAL_HIGH,
    TEMP_HIGH,
    TEMP_WARNING_HIGH,
    TEMP_WARNING_LOW,
    TEMP_CRITICAL_LOW,
    TEMP_OPTIMAL_MIN,
    TEMP_OPTIMAL_MAX,
    HEALTH_CRITICAL_THRESHOLD,
    HEALTH_HIGH_THRESHOLD,
    FUEL_CRITICAL_LOW,
    FUEL_LOW,
    FUEL_WARNING,
    OPERATIONAL_MODES
)

# Constraint limits for checking
CONSTRAINT_LIMITS = {
    "battery_floor": BATTERY_CRITICAL_LOW,
    "battery_low": BATTERY_LOW,
    "thermal_min": TEMP_CRITICAL_LOW,
    "thermal_max": TEMP_CRITICAL_HIGH,
    "thermal_optimal_min": TEMP_OPTIMAL_MIN,
    "thermal_optimal_max": TEMP_OPTIMAL_MAX
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionGenerator:
    """
    Generates candidate actions based on current mission situation,
    risk assessment, and available Digital Twin scenario capabilities.
    """

    def __init__(self):
        self.action_templates = self._initialize_action_templates()

    def _initialize_action_templates(self) -> List[Dict]:
        """Initialize action templates for different situations."""
        return [
            {
                "id": "ACT_MONITOR",
                "name": "Continue Monitoring",
                "category": "MONITOR",
                "description": "Continue current operations with enhanced monitoring",
                "applicable_when": lambda s, r: r["overall_risk_level"] == "LOW",
                "controls": {
                    "scenario_id": "SCN-NOMINAL",
                    "scenario_label": "Continue Nominal Operations",
                    "payload_override": "SCHEDULE",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 0.0
                },
                "priority": 1
            },
            {
                "id": "ACT_INVESTIGATE",
                "name": "Investigate Anomaly",
                "category": "INVESTIGATE",
                "description": "Investigate detected anomaly before taking action",
                "applicable_when": lambda s, r: s.get("anomaly_flag", False) or r["overall_risk_level"] in ["HIGH", "CRITICAL"],
                "controls": None,
                "priority": 10
            },
            {
                "id": "ACT_PAYLOAD_OFF",
                "name": "Reduce Payload Activity",
                "category": "PAYLOAD_ADJUST",
                "description": "Turn off payload to conserve power and reduce thermal load",
                "applicable_when": lambda s, r: (
                    s.get("battery_percentage", 100) < BATTERY_LOW or
                    s.get("temperature", 0) > TEMP_HIGH or
                    r["overall_risk_level"] in ["HIGH", "CRITICAL"]
                ),
                "controls": {
                    "scenario_id": "SCN-PWR-SHED",
                    "scenario_label": "Payload Shedding & Thermal Recovery",
                    "payload_override": "FORCE_OFF",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 25.0
                },
                "priority": 8
            },
            {
                "id": "ACT_THERMAL_SLEW",
                "name": "Thermal Panel Slew",
                "category": "THERMAL_ADJUST",
                "description": "Slew solar panels away from sun to reduce thermal load",
                "applicable_when": lambda s, r: s.get("temperature", 0) > TEMP_HIGH,
                "controls": {
                    "scenario_id": "SCN-THERMAL-SLEW",
                    "scenario_label": "Thermal Recovery via Panel Slew",
                    "payload_override": "KEEP",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 30.0
                },
                "priority": 7
            },
            {
                "id": "ACT_PAYLOAD_DUTY_CYCLE",
                "name": "Reduce Payload Duty Cycle",
                "category": "PAYLOAD_ADJUST",
                "description": "Reduce payload to 50% duty cycle to balance power and mission",
                "applicable_when": lambda s, r: (
                    s.get("battery_percentage", 100) < BATTERY_WARNING and
                    s.get("battery_percentage", 100) > BATTERY_CRITICAL_LOW
                ),
                "controls": {
                    "scenario_id": "SCN-DUTY-CYCLE",
                    "scenario_label": "Payload 50% Duty Cycle",
                    "payload_override": "DUTY_CYCLE_50",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 0.0
                },
                "priority": 5
            },
            {
                "id": "ACT_ORBIT_BOOST",
                "name": "Orbit Boost Maneuver",
                "category": "ORBIT_ADJUST",
                "description": "Perform prograde delta-v burn to raise orbit",
                "applicable_when": lambda s, r: (
                    r["overall_risk_level"] == "LOW" and
                    s.get("fuel_remaining_pct", 0) > 20
                ),
                "controls": {
                    "scenario_id": "SCN-ORBIT-BOOST",
                    "scenario_label": "Prograde Phasing Burn",
                    "payload_override": "SCHEDULE",
                    "delta_v_prograde_ms": 15.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thrust_duration_s": 20.0,
                    "thermal_slew_deg": 0.0
                },
                "priority": 4
            },
            {
                "id": "ACT_EMERGENCY_MODE",
                "name": "Enter Emergency Mode",
                "category": "EMERGENCY",
                "description": "Activate emergency mode with minimal power consumption",
                "applicable_when": lambda s, r: (
                    r["overall_risk_level"] == "CRITICAL" or
                    s.get("battery_percentage", 100) < BATTERY_CRITICAL_LOW or
                    s.get("temperature", 0) > TEMP_CRITICAL_HIGH
                ),
                "controls": {
                    "scenario_id": "SCN-EMERGENCY",
                    "scenario_label": "Emergency Safe Mode",
                    "payload_override": "FORCE_OFF",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 45.0
                },
                "priority": 10
            },
            {
                "id": "ACT_POWER_OPTIMIZE",
                "name": "Optimize Power Consumption",
                "category": "POWER_MANAGEMENT",
                "description": "Optimize power consumption while maintaining capability",
                "applicable_when": lambda s, r: (
                    s.get("battery_percentage", 100) < BATTERY_OPTIMAL and
                    s.get("battery_percentage", 100) > BATTERY_LOW
                ),
                "controls": {
                    "scenario_id": "SCN-PWR-OPT",
                    "scenario_label": "Power Optimization Mode",
                    "payload_override": "DUTY_CYCLE_50",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 15.0
                },
                "priority": 6
            },
            {
                "id": "ACT_THERMAL_HEAT",
                "name": "Increase Thermal Heating",
                "category": "THERMAL_ADJUST",
                "description": "Increase power to heaters to raise temperature",
                "applicable_when": lambda s, r: s.get("temperature", 0) < TEMP_WARNING_LOW,
                "controls": {
                    "scenario_id": "SCN-THERMAL-HEAT",
                    "scenario_label": "Thermal Heating Mode",
                    "payload_override": "FORCE_ON",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": -15.0
                },
                "priority": 6
            },
            {
                "id": "ACT_SAFE_MODE",
                "name": "Enter Safe Mode",
                "category": "MONITOR",
                "description": "Enter safe mode with reduced activity for recovery",
                "applicable_when": lambda s, r: r["overall_risk_level"] in ["HIGH", "MEDIUM"],
                "controls": {
                    "scenario_id": "SCN-SAFE",
                    "scenario_label": "Safe Mode Recovery",
                    "payload_override": "DUTY_CYCLE_50",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 10.0
                },
                "priority": 7
            },
            {
                "id": "ACT_ORBIT_DEGRADE",
                "name": "Orbit Decay Maneuver",
                "category": "ORBIT_ADJUST",
                "description": "Perform retrograde burn to lower orbit for natural decay",
                "applicable_when": lambda s, r: (
                    r["overall_risk_level"] == "LOW" and
                    s.get("fuel_remaining_pct", 0) > 30
                ),
                "controls": {
                    "scenario_id": "SCN-ORBIT-DEGRADE",
                    "scenario_label": "Retrograde Decay Maneuver",
                    "payload_override": "SCHEDULE",
                    "delta_v_prograde_ms": -10.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thrust_duration_s": 15.0,
                    "thermal_slew_deg": 0.0
                },
                "priority": 3
            },
            {
                "id": "ACT_COMM_OPTIMIZE",
                "name": "Optimize Communication Window",
                "category": "COMMUNICATIONS",
                "description": "Adjust operations for optimal communication",
                "applicable_when": lambda s, r: s.get("communication_status", "") != "LINKED",
                "controls": None,
                "priority": 5
            },
            {
                "id": "ACT_PAYLOAD_MAX",
                "name": "Maximize Payload Operations",
                "category": "PAYLOAD_ADJUST",
                "description": "Maximize payload activity during optimal conditions",
                "applicable_when": lambda s, r: (
                    r["overall_risk_level"] == "LOW" and
                    s.get("battery_percentage", 100) > BATTERY_OPTIMAL and
                    s.get("temperature", 0) > TEMP_OPTIMAL_MIN and
                    s.get("temperature", 0) < TEMP_OPTIMAL_MAX
                ),
                "controls": {
                    "scenario_id": "SCN-PAYLOAD-MAX",
                    "scenario_label": "Maximum Payload Operations",
                    "payload_override": "FORCE_ON",
                    "delta_v_prograde_ms": 0.0,
                    "delta_v_radial_ms": 0.0,
                    "delta_v_normal_ms": 0.0,
                    "thermal_slew_deg": 0.0
                },
                "priority": 2
            },
            {
                "id": "ACT_FUEL_CONSERVE",
                "name": "Conserve Fuel",
                "category": "ORBIT_ADJUST",
                "description": "Conserve fuel by avoiding maneuvers",
                "applicable_when": lambda s, r: (
                    s.get("fuel_remaining_pct", 100) < FUEL_WARNING
                ),
                "controls": None,
                "priority": 6
            }
        ]

    def generate_actions(
        self,
        state: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        max_actions: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Generate candidate actions based on current situation and risks.
        Returns list of applicable actions with controls for Digital Twin scenarios.
        """
        generated_at = datetime.utcnow()

        # Evaluate all action templates
        applicable_actions = []
        for template in self.action_templates:
            try:
                if template["applicable_when"](state, risk_assessment):
                    action = {
                        "action_id": template["id"],
                        "name": template["name"],
                        "category": template["category"],
                        "description": template["description"],
                        "category_description": ACTION_CATEGORIES.get(template["category"], "Unknown"),
                        "controls": template["controls"],
                        "applicable": True,
                        "priority": template.get("priority", 5),
                        "generated_at": generated_at.isoformat()
                    }
                    applicable_actions.append(action)
            except Exception as e:
                logger.warning(f"Error evaluating action template {template['id']}: {e}")

        # Sort by priority (higher priority first)
        applicable_actions.sort(key=lambda a: a["priority"], reverse=True)

        # Limit to max_actions
        applicable_actions = applicable_actions[:max_actions]

        # Add contextual rationale for each action
        for action in applicable_actions:
            action["rationale"] = self._generate_rationale(state, risk_assessment, action)
            action["expected_outcome"] = self._predict_outcome(state, action)

        return applicable_actions

    def generate_scenario_actions(
        self,
        state: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate actions that can be evaluated via Digital Twin scenarios.
        Filters to only actions with control parameters.
        """
        all_actions = self.generate_actions(state, risk_assessment, max_actions=12)

        # Filter to actions with controls (can be simulated)
        scenario_actions = [a for a in all_actions if a.get("controls") is not None]

        return scenario_actions

    def _generate_rationale(
        self,
        state: Dict,
        risk_assessment: Dict,
        action: Dict
    ) -> str:
        """Generate rationale for why this action is applicable."""
        rationale_parts = []

        # Based on battery status
        battery_pct = state.get("battery_percentage", 100)
        if battery_pct < BATTERY_CRITICAL_LOW:
            rationale_parts.append(f"Battery critically low at {battery_pct:.1f}%")
        elif battery_pct < BATTERY_LOW:
            rationale_parts.append(f"Battery low at {battery_pct:.1f}%")
        elif battery_pct < BATTERY_WARNING:
            rationale_parts.append(f"Battery at {battery_pct:.1f}% (approaching depletion)")

        # Based on thermal status
        temp = state.get("temperature", 0)
        if temp > TEMP_CRITICAL_HIGH:
            rationale_parts.append(f"Temperature critically high at {temp:.1f}°C")
        elif temp > TEMP_HIGH:
            rationale_parts.append(f"Temperature elevated at {temp:.1f}°C")
        elif temp > TEMP_WARNING_HIGH:
            rationale_parts.append(f"Temperature approaching high threshold at {temp:.1f}°C")
        elif temp < TEMP_CRITICAL_LOW:
            rationale_parts.append(f"Temperature critically low at {temp:.1f}°C")
        elif temp < TEMP_WARNING_LOW:
            rationale_parts.append(f"Temperature below normal range at {temp:.1f}°C")

        # Based on fuel status
        fuel_pct = state.get("fuel_remaining_pct", 100)
        if fuel_pct < FUEL_CRITICAL_LOW:
            rationale_parts.append(f"Fuel critically low at {fuel_pct:.1f}%")
        elif fuel_pct < FUEL_WARNING:
            rationale_parts.append(f"Fuel reserves at {fuel_pct:.1f}% (consider conservation)")

        # Based on anomaly
        if state.get("anomaly_flag", False):
            anomaly_param = state.get("anomaly_parameter", "unknown")
            rationale_parts.append(f"Anomaly detected in {anomaly_param}")

        # Based on risk level
        risk_level = risk_assessment.get("overall_risk_level", "LOW")
        if risk_level == "CRITICAL":
            rationale_parts.append("Overall risk level is CRITICAL - immediate action required")
        elif risk_level == "HIGH":
            rationale_parts.append(f"Overall risk level is {risk_level} - action needed")
        elif risk_level == "MEDIUM":
            rationale_parts.append(f"Overall risk level is {risk_level} - precautionary action")

        # Based on health score
        health = state.get("health_score", 100)
        if health < HEALTH_CRITICAL_THRESHOLD:
            rationale_parts.append(f"Health score critically low at {health:.1f}")
        elif health < HEALTH_HIGH_THRESHOLD:
            rationale_parts.append(f"Health score degraded at {health:.1f}")

        # Based on communication status
        comm_status = state.get("communication_status", "")
        if comm_status != "LINKED":
            rationale_parts.append("Communication link not established")

        if not rationale_parts:
            rationale_parts.append("Routine operational monitoring - nominal conditions")

        return "; ".join(rationale_parts)

    def check_constraints(
        self,
        state: Dict,
        action: Dict
    ) -> Dict[str, Any]:
        """
        Check if action passes constraint limits.
        Returns pass/fail status for each constraint.
        """
        constraints = {
            "battery_floor": {
                "limit": CONSTRAINT_LIMITS["battery_floor"],
                "current": state.get("battery_percentage", 100),
                "passes": state.get("battery_percentage", 100) >= CONSTRAINT_LIMITS["battery_floor"]
            },
            "thermal_min": {
                "limit": CONSTRAINT_LIMITS["thermal_min"],
                "current": state.get("temperature", 0),
                "passes": state.get("temperature", 0) >= CONSTRAINT_LIMITS["thermal_min"]
            },
            "thermal_max": {
                "limit": CONSTRAINT_LIMITS["thermal_max"],
                "current": state.get("temperature", 0),
                "passes": state.get("temperature", 0) <= CONSTRAINT_LIMITS["thermal_max"]
            }
        }

        # Action-specific constraint adjustments
        action_category = action.get("category", "")
        if action_category == "THERMAL_ADJUST":
            # Thermal actions should aim to bring temp into optimal range
            constraints["thermal_optimal_target"] = {
                "limit_min": CONSTRAINT_LIMITS["thermal_optimal_min"],
                "limit_max": CONSTRAINT_LIMITS["thermal_optimal_max"],
                "current": state.get("temperature", 0),
                "passes": CONSTRAINT_LIMITS["thermal_optimal_min"] <= state.get("temperature", 0) <= CONSTRAINT_LIMITS["thermal_optimal_max"]
            }

        all_pass = all(c["passes"] for c in constraints.values())

        return {
            "all_pass": all_pass,
            "constraints": constraints
        }

    def generate_evidence_chain(
        self,
        state: Dict,
        risk_assessment: Dict,
        action: Dict,
        prediction_data: Optional[Dict] = None
    ) -> List[str]:
        """
        Generate action-specific evidence chain.
        """
        evidence = []

        # Current conditions
        sunlit = state.get("sunlit", False)
        payload_status = state.get("payload_status", "UNKNOWN")
        temp = state.get("temperature", 0)
        battery = state.get("battery_percentage", 100)

        evidence.append(f"Sunlit: {'yes' if sunlit else 'no'}")
        evidence.append(f"Payload: {payload_status}")
        evidence.append(f"Temperature: {temp:.1f} °C")
        evidence.append(f"Battery: {battery:.1f}%")

        # Add forecast if available
        if prediction_data and prediction_data.get("limit_crossings"):
            temp_crossings = prediction_data["limit_crossings"].get("temperature", [])
            if temp_crossings:
                first_crossing = temp_crossings[0]
                time_min = first_crossing.get("time_minutes", 0)
                limit = first_crossing.get("threshold", 0)
                crossing_type = first_crossing.get("crossing_type", "")
                direction = "below" if "LOW" in crossing_type else "above"
                evidence.append(f"Forecast: {direction} {limit} °C in about {time_min:.0f} minutes")

        # Add risk context
        risk_level = risk_assessment.get("overall_risk_level", "LOW")
        if risk_level != "LOW":
            evidence.append(f"Risk level: {risk_level}")

        return evidence

    def _predict_outcome(self, state: Dict, action: Dict) -> str:
        """Predict expected outcome of the action."""
        category = action.get("category", "MONITOR")
        
        outcomes = {
            "EMERGENCY": "Will minimize power consumption and reduce thermal load to stabilize system",
            "PAYLOAD_ADJUST": "Will adjust payload operations to improve resource balance",
            "THERMAL_ADJUST": "Will modify thermal management to bring temperature into optimal range",
            "ORBIT_ADJUST": "Will modify orbital parameters (consumes fuel)",
            "POWER_MANAGEMENT": "Will optimize power consumption patterns",
            "COMMUNICATIONS": "Will optimize for communication opportunities",
            "MONITOR": "Will continue current operations with enhanced monitoring",
            "INVESTIGATE": "Will gather additional data to inform decision-making"
        }
        
        return outcomes.get(category, "Will attempt to improve current situation")
