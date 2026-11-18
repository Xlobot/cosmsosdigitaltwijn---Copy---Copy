"""
Digital Twin Data Adapter
Fetches and normalizes outputs from the existing COSMOS Digital Twin.
Read-only integration - no modifications to Digital Twin code.
"""

import httpx
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from .config import (
    DT_BASE_URL,
    DT_API_TIMEOUT,
    DATA_STATUS,
    DEFAULT_PREDICTION_HORIZON_MINUTES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DigitalTwinAdapter:
    """
    Adapter for reading Digital Twin outputs via REST API.
    Handles missing, stale, or invalid data safely.
    """

    def __init__(self, base_url: str = DT_BASE_URL, timeout: int = DT_API_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = None
        self._last_successful_contact = None
        self._status = "UNKNOWN"

    async def _get_client(self):
        """Lazy initialization of HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        return self.client

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    def _get_data_status(self) -> str:
        """
        Determine data availability status based on last successful contact.
        """
        if self._last_successful_contact is None:
            return DATA_STATUS["UNKNOWN"]

        time_since_contact = datetime.utcnow() - self._last_successful_contact
        if time_since_contact < timedelta(minutes=5):
            return DATA_STATUS["CURRENT"]
        elif time_since_contact < timedelta(minutes=30):
            return DATA_STATUS["STALE"]
        else:
            return DATA_STATUS["MISSING"]

    async def fetch_state(self, row_index: int = 0) -> Dict[str, Any]:
        """
        Fetch current state from Digital Twin.
        Returns normalized state with data availability metadata.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/state",
                params={"index": row_index}
            )
            response.raise_for_status()

            state = response.json()
            self._last_successful_contact = datetime.utcnow()
            self._status = "ONLINE"

            # Add metadata
            state["_data_source"] = "digital_twin_api"
            state["_data_status"] = self._get_data_status()
            state["_fetch_timestamp"] = datetime.utcnow().isoformat()
            state["_row_index"] = row_index

            return state

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching state from Digital Twin (row {row_index})")
            self._status = "TIMEOUT"
            return self._create_error_state("timeout", row_index)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching state: {e}")
            self._status = "HTTP_ERROR"
            return self._create_error_state("http_error", row_index)
        except Exception as e:
            logger.error(f"Unexpected error fetching state: {e}")
            self._status = "ERROR"
            return self._create_error_state("unknown_error", row_index)

    async def fetch_prediction(
        self,
        start_row_index: int = 0,
        horizon_minutes: int = DEFAULT_PREDICTION_HORIZON_MINUTES
    ) -> Dict[str, Any]:
        """
        Fetch nominal prediction from Digital Twin.
        Returns prediction with validation metrics.
        """
        try:
            client = await self._get_client()
            payload = {
                "start_row_index": start_row_index,
                "horizon_minutes": horizon_minutes
            }
            response = await client.post(
                f"{self.base_url}/api/predict",
                json=payload
            )
            response.raise_for_status()

            prediction = response.json()
            self._last_successful_contact = datetime.utcnow()

            # Add metadata
            prediction["_data_source"] = "digital_twin_api"
            prediction["_data_status"] = self._get_data_status()
            prediction["_fetch_timestamp"] = datetime.utcnow().isoformat()

            return prediction

        except Exception as e:
            logger.error(f"Error fetching prediction: {e}")
            return self._create_error_prediction(str(e), start_row_index, horizon_minutes)

    async def fetch_scenarios(
        self,
        start_row_index: int = 0,
        horizon_minutes: int = DEFAULT_PREDICTION_HORIZON_MINUTES,
        scenarios: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Fetch scenario comparison from Digital Twin (what-if analysis).
        Returns multiple scenarios with trade-off recommendations.
        """
        try:
            client = await self._get_client()
            payload = {
                "start_row_index": start_row_index,
                "horizon_minutes": horizon_minutes,
                "scenarios": scenarios or []
            }
            response = await client.post(
                f"{self.base_url}/api/fork",
                json=payload
            )
            response.raise_for_status()

            fork_result = response.json()
            self._last_successful_contact = datetime.utcnow()

            # Add metadata
            fork_result["_data_source"] = "digital_twin_api"
            fork_result["_data_status"] = self._get_data_status()
            fork_result["_fetch_timestamp"] = datetime.utcnow().isoformat()

            return fork_result

        except Exception as e:
            logger.error(f"Error fetching scenarios: {e}")
            return self._create_error_scenarios(str(e), start_row_index, horizon_minutes)

    async def fetch_anomalies(self) -> List[Dict[str, Any]]:
        """
        Fetch anomaly registry from Digital Twin.
        Returns list of anomaly events with metadata.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/anomalies")
            response.raise_for_status()

            anomalies = response.json()
            self._last_successful_contact = datetime.utcnow()

            # Add metadata to each anomaly
            for anom in anomalies:
                anom["_data_source"] = "digital_twin_api"
                anom["_data_status"] = self._get_data_status()

            return anomalies

        except Exception as e:
            logger.error(f"Error fetching anomalies: {e}")
            return []

    async def check_health(self) -> Dict[str, Any]:
        """
        Check Digital Twin API health status.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/status")
            response.raise_for_status()

            status = response.json()
            self._last_successful_contact = datetime.utcnow()
            self._status = "ONLINE"

            return {
                "api_status": "ONLINE",
                "digital_twin_status": status,
                "adapter_status": self._status,
                "last_contact": self._last_successful_contact.isoformat() if self._last_successful_contact else None
            }

        except Exception as e:
            logger.error(f"Error checking Digital Twin health: {e}")
            self._status = "OFFLINE"
            return {
                "api_status": "OFFLINE",
                "error": str(e),
                "adapter_status": self._status,
                "last_contact": self._last_successful_contact.isoformat() if self._last_successful_contact else None
            }

    def _create_error_state(self, error_type: str, row_index: int) -> Dict[str, Any]:
        """Create error state when Digital Twin is unavailable."""
        return {
            "_data_source": "error",
            "_data_status": DATA_STATUS["MISSING"],
            "_error_type": error_type,
            "_row_index": row_index,
            "_fetch_timestamp": datetime.utcnow().isoformat(),
            "timestamp": "UNAVAILABLE",
            "satellite_id": "UNKNOWN",
            "health_score": 0.0,
            "battery_health": 0.0,
            "thermal_health": 0.0,
            "power_health": 0.0,
            "payload_health": 0.0,
            "anomaly_flag": False,
            "risk_level": "UNKNOWN"
        }

    def _create_error_prediction(
        self,
        error: str,
        start_row_index: int,
        horizon_minutes: int
    ) -> Dict[str, Any]:
        """Create error prediction when Digital Twin is unavailable."""
        return {
            "_data_source": "error",
            "_data_status": DATA_STATUS["MISSING"],
            "_error": error,
            "start_row_index": start_row_index,
            "horizon_minutes": horizon_minutes,
            "_fetch_timestamp": datetime.utcnow().isoformat(),
            "nominal_prediction": None,
            "ground_truth_validation": None
        }

    def _create_error_scenarios(
        self,
        error: str,
        start_row_index: int,
        horizon_minutes: int
    ) -> Dict[str, Any]:
        """Create error scenarios when Digital Twin is unavailable."""
        return {
            "_data_source": "error",
            "_data_status": DATA_STATUS["MISSING"],
            "_error": error,
            "start_row_index": start_row_index,
            "horizon_minutes": horizon_minutes,
            "_fetch_timestamp": datetime.utcnow().isoformat(),
            "scenarios": [],
            "ai_recommendation": None
        }


# Singleton instance for use across the module
_adapter_instance = None


async def get_adapter() -> DigitalTwinAdapter:
    """Get or create singleton adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = DigitalTwinAdapter()
    return _adapter_instance
