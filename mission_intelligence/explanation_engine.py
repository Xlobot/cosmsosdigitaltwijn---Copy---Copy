"""
Explanation Engine
For each recommendation, provides identified issue, supporting evidence,
relevant Digital Twin prediction, proposed action and reasoning, expected benefit,
risks and trade-offs, assumptions, missing information, and uncertainty.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExplanationEngine:
    """
    Generates human-readable explanations for recommendations,
    with full traceability to data sources and assumptions.
    """

    def __init__(self):
        pass

    def generate_explanation(
        self,
        recommendation: Dict[str, Any],
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation for a recommendation.
        """
        explained_at = datetime.utcnow()

        # Identify the issue
        issue = self._identify_issue(situation, risk_assessment)

        # Gather supporting evidence
        evidence = self._gather_evidence(situation, risk_assessment)

        # Extract Digital Twin prediction if available
        dt_prediction = self._extract_dt_prediction(scenario_evaluation)

        # Explain the proposed action
        action_explanation = self._explain_action(recommendation)

        # Calculate expected benefit
        expected_benefit = self._calculate_expected_benefit(
            recommendation, situation, scenario_evaluation
        )

        # Identify risks and trade-offs
        risks_tradeoffs = self._identify_risks_tradeoffs(
            recommendation, scenario_evaluation
        )

        # Document assumptions
        assumptions = self._document_assumptions(
            situation, risk_assessment, scenario_evaluation
        )

        # Identify missing information
        missing_info = self._identify_missing_info(
            situation, risk_assessment, scenario_evaluation
        )

        # Estimate uncertainty
        uncertainty = self._estimate_uncertainty(
            situation, scenario_evaluation
        )

        # Build explanation
        explanation = {
            "explained_at": explained_at.isoformat(),
            "recommendation": {
                "action_id": recommendation.get("action_id"),
                "name": recommendation.get("name"),
                "category": recommendation.get("category"),
                "overall_score": recommendation.get("overall_score")
            },
            "identified_issue": issue,
            "supporting_evidence": evidence,
            "digital_twin_prediction": dt_prediction,
            "proposed_action": action_explanation,
            "expected_benefit": expected_benefit,
            "risks_and_tradeoffs": risks_tradeoffs,
            "assumptions": assumptions,
            "missing_information": missing_info,
            "uncertainty": uncertainty,
            "traceability": {
                "data_sources": self._list_data_sources(situation, risk_assessment, scenario_evaluation),
                "prediction_source": scenario_evaluation.get("data_source") if scenario_evaluation else "none"
            }
        }

        return explanation

    def _identify_issue(
        self,
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify the primary issue that needs addressing."""
        concerns = situation.get("concerns", [])
        triggered_risks = risk_assessment.get("triggered_risks", [])
        overall_risk = risk_assessment.get("overall_risk_level", "LOW")

        if not concerns and not triggered_risks:
            return {
                "type": "routine",
                "description": "Routine monitoring - no critical issues detected",
                "severity": "LOW"
            }

        # Find highest severity concern
        critical_concerns = [c for c in concerns if c.get("severity") == "critical"]
        high_concerns = [c for c in concerns if c.get("severity") == "high"]

        if critical_concerns:
            primary = critical_concerns[0]
        elif high_concerns:
            primary = high_concerns[0]
        elif triggered_risks:
            primary_risk = triggered_risks[0]
            primary = {
                "type": primary_risk.get("name", "unknown"),
                "description": primary_risk.get("description", ""),
                "severity": primary_risk.get("severity", "MEDIUM")
            }
        else:
            primary = concerns[0] if concerns else {"type": "unknown", "description": "Unknown issue", "severity": "LOW"}

        return {
            "type": primary.get("type", "unknown"),
            "description": primary.get("description", ""),
            "severity": primary.get("severity", "LOW"),
            "overall_risk_level": overall_risk
        }

    def _gather_evidence(
        self,
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Gather supporting evidence for the issue."""
        evidence = []

        # Health score evidence
        health_summary = situation.get("health_summary", {})
        evidence.append({
            "metric": "health_score",
            "value": health_summary.get("score", 0),
            "level": health_summary.get("level", "unknown"),
            "source": "health_engine"
        })

        # Resource evidence
        resource_status = situation.get("resource_status", {})
        evidence.append({
            "metric": "battery_percentage",
            "value": resource_status.get("battery", {}).get("percentage", 0),
            "status": resource_status.get("battery", {}).get("status", "unknown"),
            "source": "telemetry"
        })
        evidence.append({
            "metric": "temperature_c",
            "value": resource_status.get("thermal", {}).get("temperature_c", 0),
            "status": resource_status.get("thermal", {}).get("status", "unknown"),
            "source": "telemetry"
        })

        # Risk evidence
        triggered_risks = risk_assessment.get("triggered_risks", [])
        for risk in triggered_risks[:3]:  # Top 3 risks
            evidence.append({
                "metric": "risk_rule",
                "rule_id": risk.get("rule_id"),
                "name": risk.get("name"),
                "severity": risk.get("severity"),
                "source": "risk_assessment_engine"
            })

        return evidence

    def _extract_dt_prediction(
        self,
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract relevant Digital Twin prediction data."""
        if not scenario_evaluation:
            return None

        ai_recommendation = scenario_evaluation.get("ai_recommendation", {})
        if not ai_recommendation:
            return None

        return {
            "recommended_scenario_id": ai_recommendation.get("recommended_scenario_id"),
            "utility_score": ai_recommendation.get("utility_score"),
            "executive_summary": ai_recommendation.get("executive_summary"),
            "prediction_source": scenario_evaluation.get("data_source", "unknown")
        }

    def _explain_action(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Explain the proposed action."""
        return {
            "action_id": recommendation.get("action_id"),
            "name": recommendation.get("name"),
            "category": recommendation.get("category"),
            "description": recommendation.get("description"),
            "rationale": recommendation.get("rationale", ""),
            "overall_score": recommendation.get("overall_score"),
            "justification": recommendation.get("justification", "")
        }

    def _calculate_expected_benefit(
        self,
        recommendation: Dict[str, Any],
        situation: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate expected benefit of the action."""
        category = recommendation.get("category", "MONITOR")

        benefits = []

        if category == "PAYLOAD_ADJUST":
            benefits.append("Reduces power consumption")
            benefits.append("Lowers thermal load")
        elif category == "THERMAL_ADJUST":
            benefits.append("Reduces temperature")
            benefits.append("Protects thermal components")
        elif category == "ORBIT_ADJUST":
            benefits.append("Modifies orbital parameters")
            benefits.append("May improve mission timeline")
        elif category == "INVESTIGATE":
            benefits.append("Provides better situational awareness")
            benefits.append("Enables informed decision-making")
        elif category == "MONITOR":
            benefits.append("Maintains operational continuity")
            benefits.append("Preserves current mission state")

        # Add quantitative benefit if scenario evaluation available
        quantitative_benefit = None
        if scenario_evaluation:
            comparison = scenario_evaluation.get("comparison", {})
            summaries = comparison.get("summaries", [])

            action_id = recommendation.get("action_id")
            for summary in summaries:
                if summary.get("action_id") == action_id:
                    metrics = summary.get("metrics", {})
                    quantitative_benefit = {
                        "predicted_health_score": metrics.get("final_health_score"),
                        "predicted_battery_pct": metrics.get("final_battery_pct"),
                        "predicted_temperature_c": metrics.get("final_temperature_c")
                    }
                    break

        return {
            "qualitative_benefits": benefits,
            "quantitative_benefit": quantitative_benefit
        }

    def _identify_risks_tradeoffs(
        self,
        recommendation: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Identify risks and trade-offs of the action."""
        tradeoffs = recommendation.get("trade_offs", [])

        # Add category-specific trade-offs
        category = recommendation.get("category", "MONITOR")
        if category == "PAYLOAD_ADJUST":
            tradeoffs.append("Reduces mission data collection")
        elif category == "ORBIT_ADJUST":
            tradeoffs.append("Consumes fuel")
            tradeoffs.append("Introduces orbital uncertainty")

        return tradeoffs

    def _document_assumptions(
        self,
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Document assumptions made in the recommendation."""
        assumptions = []

        # Data source assumptions
        data_status = situation.get("data_status", "unknown")
        if data_status == "SIMULATED":
            assumptions.append("Data is from simulation/replay, not live spacecraft")
        elif data_status == "STALE":
            assumptions.append("Data may be stale")

        # Health engine assumptions
        assumptions.append("Health Engine predictions assume similar operational conditions")
        assumptions.append("Health Engine model trained on specific mission profile")

        # Scenario evaluation assumptions
        if scenario_evaluation:
            assumptions.append("Scenario predictions assume accurate orbital propagation")
            assumptions.append("Scenario evaluation uses current system parameters")

        return assumptions

    def _identify_missing_info(
        self,
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Identify missing information that could improve the recommendation."""
        missing = []

        # Check for live data
        if situation.get("data_status") != "CURRENT":
            missing.append("Live spacecraft telemetry")

        # Check for scenario evaluation
        if not scenario_evaluation:
            missing.append("Scenario evaluation data for action comparison")

        # Check for historical context
        missing.append("Long-term historical trend data")

        # Check for external constraints
        missing.append("Mission timeline constraints")
        missing.append("Ground station availability")

        return missing

    def _estimate_uncertainty(
        self,
        situation: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Estimate uncertainty in the recommendation."""
        uncertainty_level = "MEDIUM"
        factors = []

        # Data uncertainty
        if situation.get("data_status") == "STALE":
            uncertainty_level = "HIGH"
            factors.append("Stale data increases uncertainty")

        if situation.get("data_status") == "MISSING":
            uncertainty_level = "CRITICAL"
            factors.append("Missing data - high uncertainty")

        # Prediction uncertainty
        if scenario_evaluation:
            confidence = scenario_evaluation.get("ai_recommendation", {}).get("utility_score", 50)
            if confidence < 30:
                uncertainty_level = "HIGH"
                factors.append("Low prediction confidence")
        else:
            factors.append("No scenario evaluation available")

        return {
            "level": uncertainty_level,
            "factors": factors
        }

    def _list_data_sources(
        self,
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> List[str]:
        """List all data sources used in the recommendation."""
        sources = []

        if situation.get("data_source"):
            sources.append(f"State: {situation.get('data_source')}")

        if risk_assessment.get("data_source"):
            sources.append(f"Risk: {risk_assessment.get('data_source')}")

        if scenario_evaluation and scenario_evaluation.get("data_source"):
            sources.append(f"Scenario: {scenario_evaluation.get('data_source')}")

        if not sources:
            sources.append("No data sources identified")

        return sources
