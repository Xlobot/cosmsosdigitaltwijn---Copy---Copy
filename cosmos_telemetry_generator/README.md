# COSMOS Satellite Telemetry Generator (Standalone Package)

A production-ready, autonomous satellite telemetry streaming service designed to supply high-fidelity, real-time spaceflight telemetry to Digital Twins, 3D Mission Control dashboards, and ML anomaly detection systems.

---

## 📁 Package Contents

```
cosmos_telemetry_generator/
│
├── generator_api.py                 # Primary FastAPI REST service with Swagger UI & fault injection
├── stream_cosmos_data.py            # Zero-dependency standard library fallback streamer
├── client_ingest.py                 # Plug-and-play Python client adapter for another project
├── client_example_js.js             # Plug-and-play JavaScript / TypeScript / React poller
├── test_generator.py                # Standalone test suite verifying data fidelity & API contracts
│
├── cosmos_integrated_dataset.csv    # 4,320-row spaceflight dataset (32 channels, ISS-like orbit)
├── cosmos_synthetic_dataset.csv     # Alternative synthetic flight baseline
│
├── requirements.txt                 # Python dependencies (fastapi, uvicorn, pydantic)
├── Dockerfile                       # Docker container setup (optional deployment)
├── start_generator.bat              # 1-Click Windows launch script
├── start_generator.sh               # 1-Click Linux / macOS launch script
└── README.md                        # Complete integration guide & documentation
```

---

## 🚀 Quick Start (60 Seconds)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Generator API
```bash
# Windows
start_generator.bat

# Or direct Python
python generator_api.py --port 8080 --interval 1.0

# Or via Docker
docker build -t cosmos-generator .
docker run -p 8080:8080 cosmos-generator
```

Once running:
* **Interactive Swagger UI:** [http://localhost:8080/docs](http://localhost:8080/docs)
* **API Health Check:** [http://localhost:8080/health](http://localhost:8080/health)
* **Latest State Snapshot:** [http://localhost:8080/latest](http://localhost:8080/latest)
* **Incremental Telemetry Stream:** [http://localhost:8080/rows?since=0](http://localhost:8080/rows?since=0)
* **Key Catalog & Units:** [http://localhost:8080/keys](http://localhost:8080/keys)

---

## 🔌 How to Integrate into Another Project

### Option A: Python Backend (FastAPI, Flask, Django, Data Pipeline)

Copy `client_ingest.py` into your target project:

```python
from client_ingest import TelemetryClient

def on_new_frame(frame):
    # This callback receives a new frame every tick
    print(f"Frame #{frame['emit_index']} @ {frame['timestamp']}")
    print(f"  Orbit: Pos=({frame['position_x']}, {frame['position_y']}, {frame['position_z']}) km")
    print(f"  Power: Battery={frame['battery_percentage']}% | Solar={frame['solar_power_input']}W")
    print(f"  Thermal: Temp={frame['temperature']}°C")

# Connect to generator
client = TelemetryClient(url="http://127.0.0.1:8080", poll_interval=0.5)

# Start background stream listener
client.start(on_row=on_new_frame)

# ... your main application runs ...

# When shutting down:
client.stop()
```

### Option B: JavaScript / TypeScript (Node.js, React, Vue, Three.js)

Copy `client_example_js.js` into your frontend or Node service:

```javascript
import { startTelemetryStream } from './client_example_js.js';

// In React useEffect or app bootstrap:
const stopStream = startTelemetryStream('http://localhost:8080', (frame) => {
  console.log('Live Telemetry:', frame.timestamp, frame.battery_percentage, frame.temperature);
  // Update your 3D satellite mesh or live charts here!
});

// To disconnect:
// stopStream();
```

---

## 📡 Universal REST & WebSocket API Endpoints

The generator is designed with **universal route and parameter aliasing**. This means your friend does **NOT** need to match your file names, folder names, or exact query parameters. The API accepts any standard format automatically.

| Canonical Endpoint | Aliases Supported | Description |
|---|---|---|
| `GET /rows` | `/api/rows`, `/telemetry/rows`, `/telemetry`, `/api/telemetry`, `/data`, `/feed` | Incremental telemetry feed. Supports `?since=N`, `?cursor=N`, `?offset=N`, `?start=N`, or `?from=N`. |
| `GET /latest` | `/api/latest`, `/telemetry/latest`, `/current`, `/api/current`, `/state` | Returns the single most recent telemetry frame. |
| `GET /health` | `/api/health`, `/status`, `/api/status`, `/ping` | Ingestion liveness check (`{"status": "ok"}`). |
| `WS /ws` | `/api/ws`, `/ws/telemetry`, `/telemetry/ws`, `/socket` | Real-time WebSocket push stream for 60 FPS 3D visualizations. |
| `GET /stream` | `/api/stream`, `/events` | Server-Sent Events (SSE) native browser stream. |
| `GET /keys` | `/api/keys`, `/metadata` | Catalog of all 32 parameters, physical units, and subsystems. |
| `GET /schema` | `/api/schema` | JSON Schema for automated request validation. |
| `POST /control/rate`| `/api/control/rate` | Adjust emission rate: `{"interval_seconds": 0.5}`. |
| `POST /inject/anomaly`| `/api/inject/anomaly` | Inject synthetic faults (thermal spikes, undervoltage) to test ML alarms. |

---

## 🔗 Universal Compatibility (Why File Names Don't Matter)

Your friend's digital twin code communicates exclusively over the **HTTP / WebSocket network boundary**.
1. **File Names Are Irrelevant:** Your friend's files can be named `main.py`, `digital_twin.py`, `app.js`, `index.ts`, or anything else. The generator is an autonomous network service that listens on port `8080`.
2. **Query Parameters Are Auto-Resolved:** If their code sends `?since=10`, `?cursor=10`, `?offset=10`, `?start=10`, or `?from=10`, the generator automatically resolves the cursor.
3. **Payload Format Flexibility:** If their code expects a raw array `[...]` (default) or an envelope object (`{"status": "ok", "rows": [...]}` via `?format=envelope`), both are supported.
4. **Pre-Computed Geodetics Included:** Every frame includes both Cartesian coordinates (`position_x, y, z`) AND pre-computed Earth geodetic coordinates (`latitude`, `longitude`, `altitude_km`), plus shorthand aliases (`time`, `battery_soc`, `fuel_remaining`, `q0..3`).
5. **CORS Fully Enabled:** `Access-Control-Allow-Origin: *` is enabled so browser applications from any port (e.g. `3000`, `5173`, `8000`) connect without cross-origin blocks.

---

## 🛰️ 32 Telemetry Channels Specification

| Parameter | Type | Unit | Subsystem | Description |
|---|---|---|---|---|
| `timestamp` | string | ISO-8601 UTC | Clock | Real UTC observation time (e.g. `2026-11-10T12:00:00Z`). |
| `satellite_id` | string | — | ID | Spacecraft identifier (e.g. `ISS-25544`). |
| `position_x, y, z` | float | km | Orbit Mechanics | ECI Cartesian coordinates ($r \approx 6794\text{ km}$, LEO altitude $\approx 416\text{ km}$). |
| `velocity_x, y, z` | float | km/s | Orbit Mechanics | ECI Cartesian velocity vector ($v \approx 7.66\text{ km/s}$). |
| `semi_major_axis` | float | km | Keplerian Orbit | Orbit size ($a \approx 6800\text{ km}$). |
| `eccentricity` | float | dimensionless | Keplerian Orbit | Circularity ($e \approx 0.0007$). |
| `inclination` | float | degrees | Keplerian Orbit | Orbit inclination tilt ($i \approx 51.6^\circ$). |
| `raan` | float | degrees | Keplerian Orbit | Right Ascension of the Ascending Node. |
| `argument_of_perigee`| float | degrees | Keplerian Orbit | Angular distance of perigee. |
| `true_anomaly` | float | degrees | Keplerian Orbit | Current angle along orbit ellipse. |
| `orientation_q0..3` | float | quaternion | Attitude (ADCS) | Unit attitude quaternion ($\|q\| = 1.0$) for 3D rotation. |
| `angular_velocity_x..z`| float| deg/s | Attitude (ADCS) | Body rotation spin rates. |
| `battery_percentage`| float | % (0–100) | Power (EPS) | Battery State of Charge (SoC). |
| `battery_voltage` | float | V (~7.4V) | Power (EPS) | Main electrical bus terminal voltage. |
| `battery_current` | float | A | Power (EPS) | Battery current (>0 charging, <0 discharging). |
| `solar_power_input` | float | W | Power (EPS) | Photovoltaic solar generation (drops to 0 in eclipse). |
| `power_draw` | float | W | Power (EPS) | Total satellite avionics power consumption. |
| `sunlit` | boolean | True / False | Power (EPS) | Illumination flag (`True` = Sunlit, `False` = Eclipse). |
| `temperature` | float | °C | Thermal (TCS) | Primary avionics sensor temperature ($-4^\circ\text{C}$ to $40^\circ\text{C}$). |
| `payload_status` | string | ON / OFF | Payload | Primary scientific instrument status. |
| `payload_power_draw`| float | W | Payload | Power drawn exclusively by payload instrument. |
| `communication_status`| string| LINKED | TT&C | Ground tracking link state. |
| `fuel_remaining_pct` | float | % | Propulsion | Propellant reserve percentage for orbital delta-V. |

---

## 🧪 Converting ECI $(X, Y, Z)$ to Earth $(Lat, Lon, Alt)$

If your other project needs geodetic coordinates for a 3D Earth globe (e.g. Cesium, Three.js, or Leaflet):

```python
import math
import numpy as np

R_EARTH = 6378.137          # km (WGS84 equatorial radius)
OMEGA_EARTH = 7.2921159e-5  # rad/s (Earth rotation rate)

def cartesian_to_geodetic(x, y, z, step_index):
    r = math.sqrt(x*x + y*y + z*z)
    alt_km = r - R_EARTH
    
    # Earth rotation angle (GMST)
    gmst_rad = (step_index * 60.0 * OMEGA_EARTH) % (2.0 * math.pi)
    
    lat_deg = math.degrees(math.asin(z / r))
    lon_deg = (math.degrees(math.atan2(y, x) - gmst_rad) + 180.0) % 360.0 - 180.0
    
    return lat_deg, lon_deg, alt_km
```

---

## 🚨 Testing Synthetic Faults (Anomaly Injection)

To test an anomaly detection model or alert UI in another project, send a `POST` request to the generator:

```bash
curl -X POST "http://localhost:8080/inject/anomaly" \
     -H "Content-Type: application/json" \
     -d '{
       "duration_ticks": 10,
       "overrides": {
         "temperature": 89.5,
         "battery_voltage": 4.9
       }
     }'
```
For the next 10 frames, the generator will emit `temperature = 89.5°C` and `battery_voltage = 4.9V`, allowing you to verify that your consuming app triggers an alert immediately.

---

## ✅ Run Standalone Verification

To verify that the generator operates properly in any new environment:
```bash
python test_generator.py
```
This runs 5 automated checks (dataset loading, key dictionary, JSON schema validity, real-time streaming cadence, and fault injection).

