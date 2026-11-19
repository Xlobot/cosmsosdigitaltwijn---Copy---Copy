"""
COSMOS Telemetry Client Adapter
===============================
Plug-and-play Python ingestion client for integrating the telemetry generator
into any other project (e.g., Flask, FastAPI, Django, Celery, or data pipelines).

Usage in your project:
----------------------
    from client_ingest import TelemetryClient

    def handle_row(row):
        print(f"Received frame #{row['emit_index']} @ {row['timestamp']}: "
              f"Batt={row['battery_percentage']}%, Temp={row['temperature']}C")

    client = TelemetryClient(url="http://127.0.0.1:8080")
    client.start(on_row=handle_row)
    # ... your application runs ...
    client.stop()
"""

import os
import sys
import json
import time
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional, List, Dict, Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from cosmos_security import get_service_headers
except ImportError:
    def get_service_headers():
        return {}


class TelemetryClient:
    """
    Client for consuming live satellite telemetry frames from the Generator API.
    Handles cursor tracking, automatic reconnection, and background pacing.
    """

    def __init__(self, url: str = "http://127.0.0.1:8080", poll_interval: float = 0.5):
        self.url = url.rstrip("/")
        self.poll_interval = max(0.05, float(poll_interval))
        self.cursor = 0
        self.is_connected = False
        self.last_error: Optional[str] = None
        self.total_received = 0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def health(self) -> Dict[str, Any]:
        """Checks if the telemetry generator service is online."""
        req_url = f"{self.url}/health"
        try:
            req = urllib.request.Request(req_url, headers=get_service_headers())
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                self.is_connected = (data.get("status") == "ok")
                self.last_error = None
                return data
        except Exception as exc:
            self.is_connected = False
            self.last_error = str(exc)
            return {"status": "unreachable", "error": str(exc)}

    def get_latest(self) -> Dict[str, Any]:
        """Fetches the single most recent satellite telemetry frame."""
        req_url = f"{self.url}/latest"
        req = urllib.request.Request(req_url, headers=get_service_headers())
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode())

    def get_rows(self, since: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetches a batch of incremental telemetry rows starting from a cursor index."""
        target_since = self.cursor if since is None else since
        req_url = f"{self.url}/rows?since={target_since}&limit={limit}"
        req = urllib.request.Request(req_url, headers=get_service_headers())
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            rows = json.loads(resp.read().decode())
            if isinstance(rows, list):
                return rows
            return []

    def start(self, on_row: Callable[[Dict[str, Any]], None]):
        """Starts a background worker thread that continuously polls and dispatches new rows."""
        if self._thread and self._thread.is_alive():
            return
        self._callback = on_row
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="telemetry-client-worker", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the background polling worker."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.5)

    def _poll_loop(self):
        while not self._stop_event.is_set():
            try:
                rows = self.get_rows(since=self.cursor, limit=100)
                self.is_connected = True
                self.last_error = None

                for row in rows:
                    self.cursor += 1
                    self.total_received += 1
                    if self._callback:
                        try:
                            self._callback(row)
                        except Exception as cb_err:
                            print(f"[TelemetryClient] Callback error: {cb_err}")

            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                self.is_connected = False
                self.last_error = str(exc)
            except Exception as exc:
                self.is_connected = False
                self.last_error = str(exc)

            self._stop_event.wait(self.poll_interval)


if __name__ == "__main__":
    print("Testing TelemetryClient connection to http://127.0.0.1:8080...")
    client = TelemetryClient("http://127.0.0.1:8080")
    h = client.health()
    print(f"Health Status: {h}")

    if client.is_connected:
        print("\nStreaming live rows for 5 seconds (Ctrl+C to quit):")
        def print_telemetry(row):
            print(f"  Frame #{row.get('emit_index')}: UTC={row.get('timestamp')}, "
                  f"Pos=({row.get('position_x'):.1f}, {row.get('position_y'):.1f}, {row.get('position_z'):.1f}) km, "
                  f"Batt={row.get('battery_percentage')}% ({row.get('battery_voltage')}V), "
                  f"Temp={row.get('temperature')}°C, Sunlit={row.get('sunlit')}")

        client.start(on_row=print_telemetry)
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            client.stop()
            print(f"\nStopped. Total frames ingested: {client.total_received}")
    else:
        print("Generator is not reachable. Start generator_api.py first.")

