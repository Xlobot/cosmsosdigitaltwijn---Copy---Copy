# COSMOS Digital Twin — Data Schema & Implementation Plan

## 1. Full data field list

### 1.1 Core telemetry (from Group 1's API — the twin's raw input)

| Field | Type | Notes |
|---|---|---|
| `timestamp` | datetime | UTC, every row must have one |
| `satellite_id` | string | needed even for one satellite — future-proofs multi-sat |
| `battery_percentage` | float (0–100) | |
| `battery_voltage` | float (V) | |
| `battery_current` | float (A) | positive = charging, negative = discharging |
| `temperature` | float (°C) | pick one primary sensor first, expand later |
| `solar_power_input` | float (W) | |
| `power_draw` | float (W) | total system consumption |
| `payload_status` | enum (ON/OFF/STANDBY) | |
| `payload_power_draw` | float (W) | separate from total draw — needed for scenario forking |
| `communication_status` | enum (LINKED/NO_CONTACT/DOWNLINKING) | |
| `position_x, position_y, position_z` | float (km) | ECI or your chosen frame — pick one and document it |
| `velocity_x, velocity_y, velocity_z` | float (km/s) | same frame as position |
| `orientation_quaternion` (q0,q1,q2,q3) or `euler_roll_pitch_yaw` | float | attitude — pick one representation, quaternion avoids gimbal lock |
| `angular_velocity_x/y/z` | float (deg/s) | needed if you simulate orientation-change scenarios |
| `fuel_remaining` / `delta_v_budget` | float | only if propulsion scenarios are in scope |

### 1.2 Orbital elements (derived or provided — needed for trajectory propagation)

| Field | Notes |
|---|---|
| `semi_major_axis` | km |
| `eccentricity` | unitless |
| `inclination` | deg |
| `raan` (right ascension of ascending node) | deg |
| `argument_of_perigee` | deg |
| `true_anomaly` | deg |

*If your dataset only gives position/velocity (state vectors), you can derive these — flag this as a decision point, not a blocker.*

### 1.3 Derived/computed fields (produced by your group, not Group 1)

| Field | Type | Source |
|---|---|---|
| `health_score` | float (0–100) | your health engine |
| `subsystem_health` (battery/thermal/power/payload) | float each | health engine breakdown |
| `anomaly_flag` | bool | anomaly detector |
| `anomaly_parameter` | string | which field triggered it |
| `anomaly_confidence` | float (0–1) | |
| `risk_level` | enum (LOW/MED/HIGH/CRITICAL) | combined health + anomaly + trend |

### 1.4 Twin state fields (bookkeeping — makes replay/sync actually work)

| Field | Notes |
|---|---|
| `twin_state_id` | unique id per snapshot |
| `source_row_index` | which dataset row this state came from |
| `sync_status` | e.g. LIVE_REPLAY / FROZEN / SCENARIO_FORK |
| `state_confidence` | 1.0 for real dataset rows, decays for predicted rows |

### 1.5 Prediction tab fields

| Field | Notes |
|---|---|
| `prediction_horizon` | minutes ahead being forecast |
| `predicted_position/velocity` | array of future points |
| `predicted_battery/temp/power` | array over horizon |
| `predicted_vs_actual_error` | computed against dataset ground truth — your validation number |
| `confidence_decay` | function/curve of error vs horizon |

### 1.6 Experiment (scenario fork) fields

| Field | Notes |
|---|---|
| `scenario_id` | |
| `parent_state_id` | which twin state it forked from |
| `control_delta_v` | magnitude + direction |
| `control_thrust_duration` | seconds |
| `control_orientation_change` | target quaternion/euler |
| `control_payload_toggle` | ON/OFF override |
| `scenario_predicted_trajectory` | output array |
| `scenario_predicted_health` | output |
| `scenario_label` | e.g. "Nominal", "Increase thrust", "Divert" — for the UI tabs |

---

## 2. Implementation plan

### Phase 0 — Schema lock (before any code)
- Finalize the exact field list above with Group 1 (they own telemetry production, you own everything downstream)
- Agree on units, coordinate frame, and orientation representation in writing — this single decision saves the most integration pain later

### Phase 1 — Real-time tab (replay engine)
- Load dataset, build a row-index pointer
- Playback controls: play / pause / step / speed multiplier / jump-to-timestamp
- Display current telemetry + health score + anomaly flags
- This tab has zero prediction error — it's a direct read of the dataset

### Phase 2 — Prediction tab (nominal propagation)
- Build the propagation engine: physics-based for trajectory (orbital mechanics), ML/statistical for battery/thermal/health trends
- From the current frozen row, propagate forward with no control changes
- Compare predicted rows against the dataset's actual future rows
- Compute and display `predicted_vs_actual_error` and the confidence-decay curve — this is your validation story for judges

### Phase 3 — Experiment tab (scenario fork)
- Fork current twin state into a new scenario object
- Expose controls: speed/thrust, orientation, payload toggle
- Run the same propagation engine with modified inputs
- Support 2–3 simultaneous scenario forks, shown side by side
- Feed each scenario's predicted outcome back through the health engine for a comparable score

### Phase 4 — Integration
- Wire health engine + anomaly detector into all three tabs consistently (not just real-time)
- Standardize the API contract with Group 1 so the schema in Phase 0 is actually what's flowing
- Cross-tab consistency check: does Tab 1's current state match Tab 2's t=0 forecast starting point?

### Phase 5 — Explainability + polish
- Add reasoning output to scenario comparisons ("Scenario B recommended because...")
- Add the accuracy-vs-horizon chart as a visible UI element, not just a backend number
- Demo script: freeze real-time playback mid-decline → show prediction tab's forecast → fork 3 experiment scenarios → compare

---

## 3. How the twin connects to the rest of MISSION

The twin should not be a standalone app — it's the module that produces the raw material every other MISSION component needs. Think of it as exposing three functions, and everything downstream is a consumer of those three:

- `get_current_state()` → current synced telemetry + health + anomaly (Tab 1)
- `predict(horizon)` → nominal forecast + confidence decay (Tab 2)
- `fork_scenario(controls)` → hypothetical outcome for a given set of changes (Tab 3)

Every other module in your architecture consumes one or more of these — none of them need to know *how* the twin computes its answer, only what shape the answer comes in.

### 3.1 Module-by-module contract

| Module | Consumes from twin | Twin field(s) used | Produces |
|---|---|---|---|
| **Mission Context** | `get_current_state()` | telemetry, health_score, anomaly_flag | a "mission situation" object: current state + mission objective + constraints (comms window, task deadline) |
| **Advanced ML** | historical telemetry (not twin-specific) + `get_current_state()` | raw telemetry stream | trained health/anomaly models — these plug back INTO the twin's health scoring, so this is a two-way link, not one-way |
| **Digital Twin** *(this module)* | Mission Context's objective/constraints (to know what scenarios are worth forking) | — | `predict()` and `fork_scenario()` outputs |
| **Mission Planning** | `fork_scenario()` outputs for each candidate task ordering | scenario_predicted_trajectory, scenario_predicted_health | a feasible task sequence given battery/time/comms limits |
| **Decision Engine** | `predict()` + all active `fork_scenario()` results + Mission Context + Mission Planning output | predicted_vs_actual_error, risk_level, scenario_label | a single recommendation + which scenario it's based on |
| **Explainable AI** | Decision Engine's chosen recommendation + the twin fields that drove it | anomaly_parameter, subsystem_health, control_* fields of the winning scenario | human-readable justification ("delay payload — thermal trend rising, twin shows +5% battery margin if delayed") |
| **Mission Assistant** | read access to all of the above | everything | natural-language Q&A layer — this is presentation only, it shouldn't compute anything new |

### 3.2 What this means for how you build the twin

- Don't hardcode the twin's output format around your own UI tabs — define `get_current_state()`, `predict()`, and `fork_scenario()` as clean functions/API endpoints *now*, even if only your own tabs call them at first. Whoever builds Decision Engine or Mission Planning later just calls the same three functions.
- The **scenario_label** field (e.g. "Nominal", "Increase thrust") matters more than it looks — Decision Engine and Explainable AI both need a human-readable handle for "which option are we talking about," not just a UUID.
- Mission Context needs to tell the twin what's worth simulating (e.g. "there's an imaging task in 20 minutes, comms window closes in 15") — so there's a small feedback loop: Mission Context → twin (what to fork) → twin → Mission Planning/Decision Engine (what it found).
- Keep the twin's confidence/error data (`predicted_vs_actual_error`, `confidence_decay`) exposed as a first-class output, not buried — Decision Engine and Explainable AI both need to say "we recommend this, and here's how confident we are," and that confidence has to come from somewhere real.

## 4. Open decisions to settle with your team before coding

- Coordinate frame for position/velocity (ECI vs. simulator-native)
- Orientation representation (quaternion vs. Euler)
- Whether orbital elements come from the dataset or get derived from state vectors
- Prediction horizon default (e.g. 15 min) and max horizon for the confidence-decay demo
