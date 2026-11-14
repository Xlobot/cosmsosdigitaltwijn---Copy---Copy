"""
Decision Log
Records recommendations and operator decisions (accepted, rejected, deferred).
Preserves timestamps and reasoning.
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .config import DECISION_LOG_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DecisionLog:
    """
    Maintains a persistent log of recommendations and operator decisions.
    Stored in JSON file for simplicity and portability.
    """

    def __init__(self, log_path: str = None):
        """
        Initialize decision log.

        Args:
            log_path: Path to JSON log file. If None, uses default from config.
        """
        self.log_path = log_path or DECISION_LOG_PATH
        self.log = self._load_log()

    def _load_log(self) -> List[Dict]:
        """Load existing log from file or create new."""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    log = json.load(f)
                    if isinstance(log, list):
                        return log
                    else:
                        logger.warning(f"Log file not a list, creating new log")
                        return []
            except Exception as e:
                logger.error(f"Error loading log file: {e}")
                return []
        else:
            # Create new log
            return []

    def _save_log(self):
        """Save log to file."""
        try:
            # Ensure directory exists
            log_dir = os.path.dirname(self.log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            with open(self.log_path, 'w') as f:
                json.dump(self.log, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving log file: {e}")

    def log_recommendation(
        self,
        recommendation: Dict[str, Any],
        explanation: Dict[str, Any],
        situation: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        operator: str = "system"
    ) -> str:
        """
        Log a recommendation (before operator decision).

        Args:
            recommendation: The recommendation being made
            explanation: Full explanation from ExplanationEngine
            situation: Current situation assessment
            risk_assessment: Current risk assessment
            operator: Operator identifier (default: "system")

        Returns:
            recommendation_id: Unique ID for this recommendation
        """
        recommendation_id = f"REC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{len(self.log)}"

        log_entry = {
            "entry_type": "recommendation",
            "recommendation_id": recommendation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "operator": operator,
            "recommendation": recommendation,
            "explanation": explanation,
            "situation_snapshot": {
                "overall_status": situation.get("overall_status"),
                "health_score": situation.get("health_summary", {}).get("score"),
                "battery_percentage": situation.get("resource_status", {}).get("battery", {}).get("percentage"),
                "temperature": situation.get("resource_status", {}).get("thermal", {}).get("temperature_c"),
                "risk_level": risk_assessment.get("overall_risk_level")
            },
            "decision": None,  # Will be filled when operator decides
            "decision_timestamp": None,
            "decision_reasoning": None
        }

        self.log.append(log_entry)
        self._save_log()

        logger.info(f"Logged recommendation {recommendation_id}")
        return recommendation_id

    def log_decision(
        self,
        recommendation_id: str,
        decision: str,  # "accepted", "rejected", "deferred"
        reasoning: Optional[str] = None,
        operator: str = "system"
    ) -> bool:
        """
        Log operator decision on a recommendation.

        Args:
            recommendation_id: ID of the recommendation being decided
            decision: "accepted", "rejected", or "deferred"
            reasoning: Optional reasoning for the decision
            operator: Operator identifier

        Returns:
            True if successful, False if recommendation not found
        """
        # Find the recommendation
        for entry in reversed(self.log):  # Search from most recent
            if entry.get("recommendation_id") == recommendation_id:
                entry["decision"] = decision
                entry["decision_timestamp"] = datetime.utcnow().isoformat()
                entry["decision_reasoning"] = reasoning
                entry["decision_operator"] = operator

                self._save_log()

                logger.info(f"Logged decision {decision} for recommendation {recommendation_id}")
                return True

        logger.warning(f"Recommendation {recommendation_id} not found in log")
        return False

    def get_recent_recommendations(
        self,
        limit: int = 10,
        operator: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent recommendations from the log.

        Args:
            limit: Maximum number of entries to return
            operator: Filter by operator (if specified)

        Returns:
            List of recent recommendation entries
        """
        # Filter and sort by timestamp (most recent first)
        filtered = self.log
        if operator:
            filtered = [e for e in filtered if e.get("operator") == operator]

        # Sort by timestamp descending
        filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        return filtered[:limit]

    def get_decision_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on decisions made.

        Returns:
            Dictionary with decision counts and percentages
        """
        total = len(self.log)
        if total == 0:
            return {
                "total_recommendations": 0,
                "decisions_made": 0,
                "accepted": 0,
                "rejected": 0,
                "deferred": 0,
                "pending": 0
            }

        decisions = [e for e in self.log if e.get("decision")]
        decisions_made = len(decisions)

        accepted = sum(1 for e in decisions if e.get("decision") == "accepted")
        rejected = sum(1 for e in decisions if e.get("decision") == "rejected")
        deferred = sum(1 for e in decisions if e.get("decision") == "deferred")
        pending = total - decisions_made

        return {
            "total_recommendations": total,
            "decisions_made": decisions_made,
            "accepted": accepted,
            "rejected": rejected,
            "deferred": deferred,
            "pending": pending,
            "acceptance_rate": (accepted / decisions_made * 100) if decisions_made > 0 else 0
        }

    def get_recommendation_by_id(self, recommendation_id: str) -> Optional[Dict]:
        """
        Get a specific recommendation by ID.

        Args:
            recommendation_id: ID of the recommendation

        Returns:
            Recommendation entry or None if not found
        """
        for entry in self.log:
            if entry.get("recommendation_id") == recommendation_id:
                return entry
        return None

    def clear_old_entries(self, days_to_keep: int = 30):
        """
        Clear log entries older than specified days.

        Args:
            days_to_keep: Number of days of history to keep
        """
        cutoff = datetime.utcnow().timestamp() - (days_to_keep * 24 * 60 * 60)

        original_count = len(self.log)
        self.log = [
            entry for entry in self.log
            if datetime.fromisoformat(entry.get("timestamp", "")).timestamp() > cutoff
        ]

        removed = original_count - len(self.log)
        if removed > 0:
            self._save_log()
            logger.info(f"Cleared {removed} old log entries (older than {days_to_keep} days)")
