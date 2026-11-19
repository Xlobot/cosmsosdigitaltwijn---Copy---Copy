"""
Mission Intelligence API
FastAPI endpoints for Mission Intelligence module.
Integrates all components and provides REST API for frontend.
"""

from fastapi import HTTPException
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .dt_adapter import DigitalTwinAdapter, get_adapter
from .situation_assessor import SituationAssessor
from .risk_engine import RiskAssessmentEngine
from .action_generator import ActionGenerator
from .scenario_evaluator import ScenarioEvaluator
from .recommendation_engine import RecommendationEngine
from .explanation_engine import ExplanationEngine
from .decision_log import DecisionLog
from .prediction_analyzer import PredictionAnalyzer
from .config import DEFAULT_PREDICTION_HORIZON_MINUTES, MODEL_LIMITATIONS, VERDICT_LEVELS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissionIntelligenceAPI:
    """
    Main API class for Mission Intelligence.
    Coordinates all components and provides unified interface.
    """

    def __init__(self):
        """Initialize all Mission Intelligence components."""
        self.dt_adapter = None  # Will be initialized async
        self.situation_assessor = SituationAssessor()
        self.risk_engine = RiskAssessmentEngine()
        self.action_generator = ActionGenerator()
        self.scenario_evaluator = None  # Will be initialized with dt_adapter
        self.recommendation_engine = RecommendationEngine()
        self.explanation_engine = ExplanationEngine()
        self.decision_log = DecisionLog()
        self.prediction_analyzer = PredictionAnalyzer()

    async def initialize(self):
        """Initialize async components."""
        self.dt_adapter = await get_adapter()
        self.scenario_evaluator = ScenarioEvaluator(self.dt_adapter)
        logger.info("Mission Intelligence API initialized")

    async def get_full_assessment(
        self,
        row_index: int = 0,
        horizon_minutes: int = DEFAULT_PREDICTION_HORIZON_MINUTES,
        run_scenarios: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete Mission Intelligence assessment.

        Args:
            row_index: Current row index in dataset
            horizon_minutes: Prediction horizon for scenarios
            run_scenarios: Whether to run scenario evaluation

        Returns:
            Complete assessment with situation, risks, actions, and recommendations
        """
        assessed_at = datetime.utcnow()

        try:
            # 1. Fetch current state from Digital Twin
            state = await self.dt_adapter.fetch_state(row_index)

            # 2. Fetch anomalies
            anomalies = await self.dt_adapter.fetch_anomalies()

            # 3. Assess current situation
            situation = self.situation_assessor.assess_current_situation(state, anomalies)

            # 4. Assess current risks
            risk_assessment = self.risk_engine.assess_current_risks(state, anomalies)

            # 5. Generate candidate actions
            actions = self.action_generator.generate_actions(state, risk_assessment)

            # 6. Evaluate scenarios (if requested and actions available)
            scenario_evaluation = None
            prediction_trajectory = []
            if run_scenarios and actions:
                scenario_actions = self.action_generator.generate_scenario_actions(state, risk_assessment)
                if scenario_actions:
                    scenario_evaluation = await self.scenario_evaluator.evaluate_scenarios(
                        scenario_actions,
                        row_index,
                        horizon_minutes
                    )
                    # Extract prediction trajectory for analysis
                    if scenario_evaluation and scenario_evaluation.get("scenarios"):
                        baseline_scenario = scenario_evaluation["scenarios"][0]
                        prediction_trajectory = baseline_scenario.get("trajectory", [])

            # 7. Analyze predictions for limit crossings
            prediction_analysis = None
            if prediction_trajectory:
                prediction_analysis = self.prediction_analyzer.analyze_predictions(
                    state,
                    prediction_trajectory,
                    horizon_minutes
                )

            # 8. Add constraint checks and evidence chains to actions
            for action in actions:
                constraints = self.action_generator.check_constraints(state, action)
                action["constraints"] = constraints
                
                evidence_chain = self.action_generator.generate_evidence_chain(
                    state, risk_assessment, action, prediction_analysis
                )
                action["evidence_chain"] = evidence_chain

            # 9. Rank actions
            ranked_actions = self.recommendation_engine.rank_actions(
                actions,
                risk_assessment,
                scenario_evaluation
            )

            # 10. Generate verdict
            verdict = self._generate_verdict(state, risk_assessment, prediction_analysis)

            # 11. Generate explanation for top recommendation
            explanation = None
            if ranked_actions.get("recommendation"):
                explanation = self.explanation_engine.generate_explanation(
                    ranked_actions["recommendation"],
                    situation,
                    risk_assessment,
                    scenario_evaluation
                )

            # 12. Log the recommendation
            recommendation_id = None
            if explanation:
                recommendation_id = self.decision_log.log_recommendation(
                    ranked_actions["recommendation"],
                    explanation,
                    situation,
                    risk_assessment
                )

            # Build complete assessment
            assessment = {
                "assessed_at": assessed_at.isoformat(),
                "row_index": row_index,
                "horizon_minutes": horizon_minutes,
                "recommendation_id": recommendation_id,
                "situation": situation,
                "risk_assessment": risk_assessment,
                "candidate_actions": actions,
                "scenario_evaluation": scenario_evaluation,
                "ranked_actions": ranked_actions,
                "explanation": explanation,
                "prediction_analysis": prediction_analysis,
                "verdict": verdict,
                "model_limitations": MODEL_LIMITATIONS,
                "data_availability": {
                    "digital_twin_status": state.get("_data_status"),
                    "scenario_data_available": scenario_evaluation is not None,
                    "data_source": "digital_twin_api",
                    "data_status": "SIMULATED",
                    "timestamp": state.get("timestamp", "unknown"),
                    "row_index": row_index
                }
            }

            return assessment

        except Exception as e:
            logger.error(f"Error in full assessment: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def submit_decision(
        self,
        recommendation_id: str,
        decision: str,
        reasoning: Optional[str] = None,
        operator: str = "system"
    ) -> Dict[str, Any]:
        """
        Submit operator decision on a recommendation.

        Args:
            recommendation_id: ID of the recommendation
            decision: "accepted", "rejected", or "deferred"
            reasoning: Optional reasoning
            operator: Operator identifier

        Returns:
            Success/failure response
        """
        try:
            success = self.decision_log.log_decision(
                recommendation_id,
                decision,
                reasoning,
                operator
            )

            if not success:
                raise HTTPException(
                    status_code=404,
                    detail=f"Recommendation {recommendation_id} not found"
                )

            return {
                "success": True,
                "recommendation_id": recommendation_id,
                "decision": decision,
                "timestamp": datetime.utcnow().isoformat()
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting decision: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _generate_verdict(
        self,
        state: Dict,
        risk_assessment: Dict,
        prediction_analysis: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a single consistent verdict with reason.
        """
        temp = state.get("temperature", 0)
        battery = state.get("battery_percentage", 100)
        payload_status = state.get("payload_status", "UNKNOWN")
        risk_level = risk_assessment.get("overall_risk_level", "LOW")
        
        # Determine verdict level
        if risk_level == "CRITICAL":
            verdict_level = "CRITICAL"
        elif risk_level == "HIGH":
            verdict_level = "WARNING"
        elif risk_level == "MEDIUM":
            verdict_level = "CAUTION"
        else:
            verdict_level = "WATCH" if temp < 5 or battery < 50 else "NOMINAL"
        
        # Build reason
        reason_parts = []
        
        # Temperature context
        if temp < 0:
            reason_parts.append(f"temperature is {temp:.1f} °C and below freezing")
        elif temp < 5:
            reason_parts.append(f"temperature is {temp:.1f} °C and falling")
        elif temp > 30:
            reason_parts.append(f"temperature is {temp:.1f} °C and elevated")
        
        # Battery context
        if battery < 30:
            reason_parts.append(f"battery is {battery:.1f}% and critical")
        elif battery < 50:
            reason_parts.append(f"battery is {battery:.1f}% and low")
        
        # Payload context
        if payload_status == "ON":
            reason_parts.append(f"payload is ON")
        
        # Add forecast if available
        if prediction_analysis:
            temp_crossings = prediction_analysis.get("limit_crossings", {}).get("temperature", [])
            if temp_crossings:
                first_crossing = temp_crossings[0]
                time_min = first_crossing.get("time_minutes", 0)
                limit = first_crossing.get("threshold", 0)
                reason_parts.append(f"forecast: will cross {limit} °C in {time_min:.0f} minutes")
        
        if not reason_parts:
            reason_parts.append("all systems nominal")
        
        reason = ", with ".join(reason_parts) + "."
        
        return {
            "level": verdict_level,
            "reason": reason
        }

    def get_decision_history(
        self,
        limit: int = 10,
        operator: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get decision history.

        Args:
            limit: Maximum number of entries
            operator: Filter by operator

        Returns:
            Decision history
        """
        try:
            history = self.decision_log.get_recent_recommendations(limit, operator)
            stats = self.decision_log.get_decision_statistics()

            return {
                "history": history,
                "statistics": stats,
                "retrieved_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting decision history: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """
        Check Mission Intelligence and Digital Twin health.

        Returns:
            Health status of all components
        """
        try:
            # Check Digital Twin
            dt_health = await self.dt_adapter.check_health()

            return {
                "mission_intelligence_status": "ONLINE",
                "digital_twin_status": dt_health,
                "components": {
                    "dt_adapter": "ONLINE",
                    "situation_assessor": "ONLINE",
                    "risk_engine": "ONLINE",
                    "action_generator": "ONLINE",
                    "scenario_evaluator": "ONLINE" if self.scenario_evaluator else "UNINITIALIZED",
                    "recommendation_engine": "ONLINE",
                    "explanation_engine": "ONLINE",
                    "decision_log": "ONLINE"
                },
                "checked_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return {
                "mission_intelligence_status": "ERROR",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }


# Singleton instance
_mi_api_instance = None


async def get_mi_api() -> MissionIntelligenceAPI:
    """Get or create singleton Mission Intelligence API instance."""
    global _mi_api_instance
    if _mi_api_instance is None:
        _mi_api_instance = MissionIntelligenceAPI()
        await _mi_api_instance.initialize()
    return _mi_api_instance
