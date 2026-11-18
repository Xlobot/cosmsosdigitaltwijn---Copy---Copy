"""
Recommendation and Ranking Engine
Ranks candidate actions using transparent criteria.
Explains why each action is recommended and identifies trade-offs.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .config import SUBSYSTEM_PRIORITIES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Ranks candidate actions based on risk reduction, mission priorities,
    feasibility, resource cost, uncertainty, and expected benefit.
    """

    def __init__(self):
        self.ranking_criteria = {
            "risk_reduction": 0.35,
            "health_improvement": 0.25,
            "resource_cost": 0.20,
            "feasibility": 0.10,
            "uncertainty": 0.10
        }

    def rank_actions(
        self,
        actions: List[Dict[str, Any]],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Rank candidate actions using transparent criteria.
        Returns ranked list with scores and trade-offs.
        """
        ranked_at = datetime.utcnow()

        # Score each action
        scored_actions = []
        for action in actions:
            score = self._calculate_action_score(
                action,
                risk_assessment,
                scenario_evaluation
            )

            scored_action = {
                **action,
                "overall_score": score["overall_score"],
                "component_scores": score["component_scores"],
                "trade_offs": score["trade_offs"],
                "justification": score["justification"]
            }
            scored_actions.append(scored_action)

        # Sort by overall score (descending)
        scored_actions.sort(key=lambda a: a["overall_score"], reverse=True)

        # Add rank
        for i, action in enumerate(scored_actions):
            action["rank"] = i + 1

        # Generate recommendation
        if scored_actions:
            recommended = scored_actions[0]
            recommendation = {
                "action_id": recommended["action_id"],
                "name": recommended["name"],
                "category": recommended["category"],
                "overall_score": recommended["overall_score"],
                "justification": recommended["justification"],
                "trade_offs": recommended["trade_offs"]
            }
        else:
            recommendation = None

        return {
            "ranked_at": ranked_at.isoformat(),
            "actions_count": len(scored_actions),
            "ranked_actions": scored_actions,
            "recommendation": recommendation,
            "ranking_criteria": self.ranking_criteria
        }

    def _calculate_action_score(
        self,
        action: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate score for a single action based on multiple criteria.
        """
        component_scores = {}
        trade_offs = []
        justification_parts = []

        # 1. Risk Reduction Score
        risk_score = self._calculate_risk_reduction_score(action, risk_assessment)
        component_scores["risk_reduction"] = risk_score
        if risk_score > 0.7:
            justification_parts.append("significantly reduces risk")

        # 2. Health Improvement Score
        health_score = self._calculate_health_improvement_score(
            action, scenario_evaluation
        )
        component_scores["health_improvement"] = health_score
        if health_score > 0.7:
            justification_parts.append("improves system health")

        # 3. Resource Cost Score (higher is better = lower cost)
        resource_score = self._calculate_resource_cost_score(
            action, scenario_evaluation
        )
        component_scores["resource_cost"] = resource_score
        if resource_score < 0.3:
            trade_offs.append("consumes significant resources")

        # 4. Feasibility Score
        feasibility_score = self._calculate_feasibility_score(action)
        component_scores["feasibility"] = feasibility_score
        if feasibility_score < 0.5:
            trade_offs.append("limited feasibility data")

        # 5. Uncertainty Score (higher is better = lower uncertainty)
        uncertainty_score = self._calculate_uncertainty_score(
            action, scenario_evaluation
        )
        component_scores["uncertainty"] = uncertainty_score
        if uncertainty_score < 0.5:
            trade_offs.append("high uncertainty in outcome")

        # Calculate weighted overall score
        overall_score = (
            component_scores["risk_reduction"] * self.ranking_criteria["risk_reduction"] +
            component_scores["health_improvement"] * self.ranking_criteria["health_improvement"] +
            component_scores["resource_cost"] * self.ranking_criteria["resource_cost"] +
            component_scores["feasibility"] * self.ranking_criteria["feasibility"] +
            component_scores["uncertainty"] * self.ranking_criteria["uncertainty"]
        )

        # Build justification
        if not justification_parts:
            justification_parts.append("standard operational procedure")

        justification = "; ".join(justification_parts)

        return {
            "overall_score": round(overall_score, 3),
            "component_scores": {k: round(v, 3) for k, v in component_scores.items()},
            "trade_offs": trade_offs,
            "justification": justification
        }

    def _calculate_risk_reduction_score(
        self,
        action: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> float:
        """Calculate risk reduction score for an action."""
        overall_risk = risk_assessment.get("overall_risk_level", "LOW")

        # Risk level to numeric
        risk_numeric = {"LOW": 0.0, "MEDIUM": 0.33, "HIGH": 0.66, "CRITICAL": 1.0}
        current_risk = risk_numeric.get(overall_risk, 0.0)

        # Action category effectiveness for risk reduction
        category_effectiveness = {
            "INVESTIGATE": 0.8,  # High effectiveness for risk situations
            "PAYLOAD_ADJUST": 0.7,
            "THERMAL_ADJUST": 0.7,
            "ORBIT_ADJUST": 0.5,
            "MONITOR": 0.3
        }

        category = action.get("category", "MONITOR")
        effectiveness = category_effectiveness.get(category, 0.5)

        # Score is higher when current risk is high and action is effective
        score = current_risk * effectiveness

        return min(1.0, max(0.0, score))

    def _calculate_health_improvement_score(
        self,
        action: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate health improvement score based on scenario evaluation."""
        if not scenario_evaluation:
            # Default moderate score without evaluation data
            return 0.5

        comparison = scenario_evaluation.get("comparison", {})
        summaries = comparison.get("summaries", [])

        # Find this action's scenario
        action_id = action.get("action_id")
        action_summary = None
        for summary in summaries:
            if summary.get("action_id") == action_id:
                action_summary = summary
                break

        if not action_summary:
            return 0.5

        # Score based on health metrics
        metrics = action_summary.get("metrics", {})
        health_score = metrics.get("final_health_score", 50) / 100.0
        battery_score = metrics.get("final_battery_pct", 50) / 100.0

        # Combine health and battery
        score = (health_score * 0.6 + battery_score * 0.4)

        return min(1.0, max(0.0, score))

    def _calculate_resource_cost_score(
        self,
        action: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate resource cost score (higher = lower cost)."""
        controls = action.get("controls")

        if not controls:
            # No controls means minimal resource cost (e.g., monitor)
            return 1.0

        # Check delta-v (fuel cost)
        delta_v = abs(controls.get("delta_v_prograde_ms", 0))
        delta_v += abs(controls.get("delta_v_radial_ms", 0))
        delta_v += abs(controls.get("delta_v_normal_ms", 0))

        if delta_v > 10:
            fuel_score = 0.2
        elif delta_v > 5:
            fuel_score = 0.5
        else:
            fuel_score = 0.9

        # Check payload impact
        payload_override = controls.get("payload_override", "KEEP")
        if payload_override == "FORCE_OFF":
            payload_score = 0.7  # Trade-off: saves power but loses mission
        elif payload_override == "DUTY_CYCLE_50":
            payload_score = 0.8
        else:
            payload_score = 1.0

        # Combined score
        score = (fuel_score * 0.6 + payload_score * 0.4)

        return min(1.0, max(0.0, score))

    def _calculate_feasibility_score(self, action: Dict[str, Any]) -> float:
        """Calculate feasibility score based on action complexity."""
        category = action.get("category", "MONITOR")

        # Feasibility by category
        category_feasibility = {
            "MONITOR": 1.0,  # Always feasible
            "INVESTIGATE": 0.9,
            "PAYLOAD_ADJUST": 0.8,
            "THERMAL_ADJUST": 0.8,
            "ORBIT_ADJUST": 0.6  # More complex, requires fuel
        }

        return category_feasibility.get(category, 0.7)

    def _calculate_uncertainty_score(
        self,
        action: Dict[str, Any],
        scenario_evaluation: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate uncertainty score (higher = lower uncertainty)."""
        if not scenario_evaluation:
            # No evaluation data = higher uncertainty
            return 0.5

        # Use scenario evaluation confidence if available
        ai_recommendation = scenario_evaluation.get("ai_recommendation", {})
        confidence = ai_recommendation.get("utility_score", 0.5)

        # Normalize to 0-1
        normalized_confidence = min(1.0, max(0.0, confidence / 100.0))

        return normalized_confidence
