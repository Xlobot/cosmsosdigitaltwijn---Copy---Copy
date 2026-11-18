"""
Scenario Evaluation
Evaluates candidate actions using Digital Twin's what-if capabilities.
Compares outcomes with baseline using supported metrics.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .config import COMPARISON_METRICS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScenarioEvaluator:
    """
    Evaluates candidate actions by running Digital Twin scenarios
    and comparing outcomes against a baseline.
    """

    def __init__(self, dt_adapter):
        """
        Initialize with Digital Twin adapter.

        Args:
            dt_adapter: DigitalTwinAdapter instance for API calls
        """
        self.dt_adapter = dt_adapter

    async def evaluate_scenarios(
        self,
        actions: List[Dict[str, Any]],
        start_row_index: int = 0,
        horizon_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Evaluate candidate actions using Digital Twin scenario fork.
        Returns comparison of all scenarios against baseline.

        Args:
            actions: List of candidate actions with controls
            start_row_index: Starting row index for simulation
            horizon_minutes: Prediction horizon in minutes
        """
        evaluated_at = datetime.utcnow()

        # Extract control parameters from actions
        scenario_controls = []
        for action in actions:
            if action.get("controls"):
                scenario_controls.append({
                    **action["controls"],
                    "action_id": action["action_id"],
                    "action_name": action["name"]
                })

        # Add "do nothing" baseline scenario
        baseline_controls = {
            "scenario_id": "SCN-BASELINE",
            "scenario_label": "Do Nothing (Baseline)",
            "payload_override": "SCHEDULE",
            "delta_v_prograde_ms": 0.0,
            "delta_v_radial_ms": 0.0,
            "delta_v_normal_ms": 0.0,
            "thermal_slew_deg": 0.0,
            "action_id": "ACT_BASELINE",
            "action_name": "Do Nothing"
        }
        scenario_controls.insert(0, baseline_controls)

        if not scenario_controls:
            # No actions with controls, return empty evaluation
            return {
                "evaluated_at": evaluated_at.isoformat(),
                "start_row_index": start_row_index,
                "horizon_minutes": horizon_minutes,
                "error": "No actions with simulation controls provided"
            }

        try:
            # Call Digital Twin fork API
            fork_result = await self.dt_adapter.fetch_scenarios(
                start_row_index=start_row_index,
                horizon_minutes=horizon_minutes,
                scenarios=scenario_controls
            )

            # Check if fork_result is None or has error
            if fork_result is None:
                return {
                    "evaluated_at": evaluated_at.isoformat(),
                    "error": "Digital Twin returned no data",
                    "start_row_index": start_row_index,
                    "horizon_minutes": horizon_minutes
                }

            # Check for errors
            if fork_result.get("_data_status") == "MISSING":
                return {
                    "evaluated_at": evaluated_at.isoformat(),
                    "error": "Digital Twin unavailable",
                    "error_detail": fork_result.get("_error", "Unknown error"),
                    "start_row_index": start_row_index,
                    "horizon_minutes": horizon_minutes
                }

            # Process scenario results
            scenarios = fork_result.get("scenarios", [])
            ai_recommendation = fork_result.get("ai_recommendation", {})

            # Compare scenarios
            comparison = self._compare_scenarios(scenarios)

            # Build evaluation result
            evaluation = {
                "evaluated_at": evaluated_at.isoformat(),
                "data_source": fork_result.get("_data_source", "unknown"),
                "data_status": fork_result.get("_data_status", "unknown"),
                "start_row_index": start_row_index,
                "horizon_minutes": horizon_minutes,
                "scenarios": scenarios,
                "scenario_count": len(scenarios),
                "comparison": comparison,
                "ai_recommendation": ai_recommendation,
                "best_scenario": ai_recommendation.get("recommended_scenario_id") if ai_recommendation else None
            }

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating scenarios: {e}")
            return {
                "evaluated_at": evaluated_at.isoformat(),
                "error": str(e),
                "start_row_index": start_row_index,
                "horizon_minutes": horizon_minutes
            }

    def _compare_scenarios(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """
        Compare scenarios against baseline.
        Returns structured comparison with metrics and deltas for each scenario.
        """
        if not scenarios:
            return {"error": "No scenarios to compare"}

        # Get baseline (first scenario should be "do nothing")
        baseline = scenarios[0]
        baseline_summary = baseline.get("summary", {})

        # Extract summaries for comparison with deltas
        summaries = []
        for scenario in scenarios:
            summary = scenario.get("summary", {})
            scenario_id = scenario.get("scenario_id")
            
            # Calculate deltas against baseline
            health_delta = summary.get("final_health_score", 0) - baseline_summary.get("final_health_score", 0)
            battery_delta = summary.get("final_battery_pct", 0) - baseline_summary.get("final_battery_pct", 0)
            temp_delta = summary.get("final_temperature_c", 0) - baseline_summary.get("final_temperature_c", 0)
            
            summaries.append({
                "scenario_id": scenario_id,
                "scenario_label": scenario.get("scenario_label"),
                "action_id": scenario.get("controls", {}).get("action_id", "unknown"),
                "is_baseline": scenario_id == "SCN-BASELINE",
                "metrics": {
                    "final_health_score": summary.get("final_health_score", 0),
                    "average_health_score": summary.get("average_health_score", 0),
                    "final_battery_pct": summary.get("final_battery_pct", 0),
                    "min_battery_pct": summary.get("min_battery_pct", 0),
                    "final_temperature_c": summary.get("final_temperature_c", 0),
                    "max_temperature_c": summary.get("max_temperature_c", 0),
                    "fuel_remaining_pct": summary.get("fuel_remaining_pct", 0),
                    "anomalies_predicted": summary.get("anomalies_predicted", 0),
                    "final_risk_level": summary.get("final_risk_level", "UNKNOWN")
                },
                "deltas": {
                    "health_delta": health_delta,
                    "battery_delta": battery_delta,
                    "temperature_delta": temp_delta
                }
            })

        # Find best scenario for each metric
        comparisons = {}
        for metric in COMPARISON_METRICS:
            if metric == "anomalies_predicted":
                # Lower is better
                best = min(summaries, key=lambda s: s["metrics"].get(metric, float('inf')))
            else:
                # Higher is better (except temperature which is complex)
                if "temperature" in metric:
                    # For temperature, closest to nominal (around 20°C) is better
                    best = min(
                        summaries,
                        key=lambda s: abs(s["metrics"].get(metric, 20) - 20)
                    )
                else:
                    best = max(summaries, key=lambda s: s["metrics"].get(metric, 0))

            comparisons[metric] = {
                "best_scenario_id": best["scenario_id"],
                "best_scenario_label": best["scenario_label"],
                "best_value": best["metrics"].get(metric, 0),
                "all_values": {s["scenario_id"]: s["metrics"].get(metric, 0) for s in summaries}
            }

        return {
            "summaries": summaries,
            "metric_comparisons": comparisons,
            "metric_count": len(COMPARISON_METRICS)
        }

    def compare_with_baseline(
        self,
        evaluation: Dict[str, Any],
        baseline_scenario_id: str = "SCN-NOMINAL"
    ) -> Dict[str, Any]:
        """
        Compare scenarios against a baseline scenario.
        Returns deltas and trade-offs.
        """
        scenarios = evaluation.get("scenarios", [])
        comparison = evaluation.get("comparison", {})

        if not scenarios:
            return {"error": "No scenarios available for baseline comparison"}

        # Find baseline scenario
        baseline = None
        for scenario in scenarios:
            if scenario.get("scenario_id") == baseline_scenario_id:
                baseline = scenario
                break

        if not baseline:
            return {"error": f"Baseline scenario {baseline_scenario_id} not found"}

        baseline_summary = baseline.get("summary", {})

        # Compare each scenario to baseline
        baseline_comparisons = []
        for scenario in scenarios:
            if scenario.get("scenario_id") == baseline_scenario_id:
                continue

            scenario_summary = scenario.get("summary", {})

            # Calculate deltas
            deltas = {
                "health_score_delta": scenario_summary.get("final_health_score", 0) - baseline_summary.get("final_health_score", 0),
                "battery_delta": scenario_summary.get("final_battery_pct", 0) - baseline_summary.get("final_battery_pct", 0),
                "temperature_delta": scenario_summary.get("final_temperature_c", 0) - baseline_summary.get("final_temperature_c", 0),
                "fuel_delta": scenario_summary.get("fuel_remaining_pct", 0) - baseline_summary.get("fuel_remaining_pct", 0),
                "anomaly_delta": scenario_summary.get("anomalies_predicted", 0) - baseline_summary.get("anomalies_predicted", 0)
            }

            # Identify trade-offs
            trade_offs = []
            if deltas["health_score_delta"] > 5:
                trade_offs.append("Improves health score")
            elif deltas["health_score_delta"] < -5:
                trade_offs.append("Reduces health score")

            if deltas["battery_delta"] > 5:
                trade_offs.append("Saves battery")
            elif deltas["battery_delta"] < -5:
                trade_offs.append("Consumes extra battery")

            if abs(deltas["temperature_delta"]) > 2:
                if deltas["temperature_delta"] < 0:
                    trade_offs.append("Reduces temperature")
                else:
                    trade_offs.append("Increases temperature")

            if deltas["fuel_delta"] < -1:
                trade_offs.append("Consumes fuel")

            baseline_comparisons.append({
                "scenario_id": scenario.get("scenario_id"),
                "scenario_label": scenario.get("scenario_label"),
                "action_id": scenario.get("controls", {}).get("action_id", "unknown"),
                "deltas": deltas,
                "trade_offs": trade_offs
            })

        return {
            "baseline_scenario_id": baseline_scenario_id,
            "baseline_scenario_label": baseline.get("scenario_label"),
            "baseline_summary": baseline_summary,
            "comparisons": baseline_comparisons
        }
