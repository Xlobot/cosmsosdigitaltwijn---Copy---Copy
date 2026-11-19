"""
COSMOS telemetry — infinite real-time stream + on-disk store.

Replays cosmos_integrated_dataset.csv in a loop, stamps each row with
the real current UTC time, and appends it to live_telemetry.csv forever
(until you stop the process). Also serves the live HTTP API the twin polls.

Usage:
  python stream_cosmos_data.py --mode http --port 8080
  python stream_cosmos_data.py --mode stdout
  python stream_cosmos_data.py --interval 1 --out live_telemetry.csv
"""
import argparse
import csv
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STORE = os.path.join(HERE, "live_telemetry.csv")

NUMERIC_FIELDS = {
    "position_x", "position_y", "position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "semi_major_axis", "eccentricity", "inclination",
    "raan", "argument_of_perigee", "true_anomaly",
    "orientation_q0", "orientation_q1", "orientation_q2", "orientation_q3",
    "angular_velocity_x", "angular_velocity_y", "angular_velocity_z",
    "battery_percentage", "battery_voltage", "battery_current",
    "temperature", "solar_power_input", "power_draw",
    "payload_power_draw", "fuel_remaining_pct",
}


def _coerce_row(row):
    out = dict(row)
    for key in NUMERIC_FIELDS:
        if key not in out or out[key] in (None, ""):
            continue
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            pass
    if "sunlit" in out:
        v = out["sunlit"]
        if isinstance(v, str):
            out["sunlit"] = v.strip().upper() in ("TRUE", "1", "YES")
        else:
            out["sunlit"] = bool(v)
    return out


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [_coerce_row(r) for r in csv.DictReader(f)]


def _csv_cell(value):
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return value


class LiveStore:
    """Append-only CSV that grows for as long as the streamer runs."""

    def __init__(self, path, fieldnames):
        self.path = os.path.abspath(path)
        self.fieldnames = fieldnames
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        exists = os.path.isfile(self.path) and os.path.getsize(self.path) > 0
        self.rows_on_disk = 0
        if exists:
            with open(self.path, newline="", encoding="utf-8") as f:
                self.rows_on_disk = max(0, sum(1 for _ in f) - 1)
        self._fh = open(self.path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            self._writer.writeheader()
            self._fh.flush()

    def append(self, row):
        with self.lock:
            self._writer.writerow({k: _csv_cell(row.get(k, "")) for k in self.fieldnames})
            self._fh.flush()
            self.rows_on_disk += 1
            return self.rows_on_disk

    def close(self):
        with self.lock:
            self._fh.close()


def paced(rows, interval, loop, use_wallclock):
    """Yield one live row every `interval` seconds, forever when loop=True."""
    i = 0
    n = len(rows)
    while True:
        row = dict(rows[i % n])
        row["source_row_index"] = i % n
        row["emit_index"] = i
        if use_wallclock:
            row["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        yield row
        i += 1
        if not loop and i >= n:
            return
        time.sleep(interval)


def _store_fieldnames(sample):
    names = list(sample.keys())
    for extra in ("source_row_index", "emit_index"):
        if extra not in names:
            names.append(extra)
    return names


def run_stream(rows, interval, loop, use_wallclock, out_path, mode, port):
    store = LiveStore(out_path, _store_fieldnames({**rows[0], "source_row_index": 0, "emit_index": 0}))
    print(f"[store] appending forever -> {store.path}  (already {store.rows_on_disk} rows)", file=sys.stderr)

    state = {"emitted": [], "lock": threading.Lock(), "store": store}

    def emit_forever():
        for row in paced(rows, interval, loop, use_wallclock):
            stored = store.append(row)
            row["rows_stored"] = stored
            with state["lock"]:
                state["emitted"].append(row)
            if mode == "stdout":
                print(json.dumps(row))
                sys.stdout.flush()
            else:
                print(f"live #{row['emit_index']} stored={stored} @ {row['timestamp']}", file=sys.stderr)

    worker = threading.Thread(target=emit_forever, daemon=True)
    worker.start()

    if mode == "http":
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                with state["lock"]:
                    emitted = list(state["emitted"])
                if parsed.path == "/latest":
                    body = json.dumps(emitted[-1] if emitted else {})
                elif parsed.path == "/rows":
                    since = int(parse_qs(parsed.query).get("since", ["0"])[0])
                    body = json.dumps(emitted[since:])
                elif parsed.path == "/health":
                    body = json.dumps({
                        "status": "ok",
                        "rows_emitted": len(emitted),
                        "rows_stored": store.rows_on_disk,
                        "store_path": store.path,
                    })
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        print(f"[http] http://localhost:{port}  GET /latest  /rows?since=N  /health", file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        try:
            while worker.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    store.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", default=os.path.join(HERE, "cosmos_integrated_dataset.csv"))
    p.add_argument("--mode", choices=["stdout", "csv-append", "http"], default="http")
    p.add_argument("--interval", type=float, default=1.0, help="real-time seconds between rows")
    p.add_argument("--no-loop", dest="loop", action="store_false", default=True,
                    help="stop after one pass (default is infinite)")
    p.add_argument("--keep-original-timestamps", dest="use_wallclock", action="store_false", default=True)
    p.add_argument("--out", default=DEFAULT_STORE, help="append-only store path")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()

    rows = load_rows(args.file)
    if not rows:
        raise SystemExit("dataset is empty")
    run_stream(rows, args.interval, args.loop, args.use_wallclock, args.out, args.mode, args.port)
