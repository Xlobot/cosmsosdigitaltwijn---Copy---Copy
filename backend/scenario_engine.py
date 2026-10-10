import math
import numpy as np
import pandas as pd
from .orbit_propagator import (
    propagate_orbit_step,
    cartesian_to_geodetic,
    estimate_sun_vector,
    DEFAULT_SUN_ECI,
    OMEGA_EARTH,
)
from .ml_engine import HealthMLEngine

# Empirically calibrated to cosmos_twin_dataset.xlsx (ISS-like CubeSat twin)
BUS_POWER_W = 30.5
STANDBY_PAYLOAD_W = 4.8
PAYLOAD_ON_W = 25.0
BATTERY_CAPACITY_WH = 80.0
PEAK_SOLAR_W = 122.0


def _safe_float(v, default=0.0):
    try:
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


class ScenarioEngine:
    def __init__(self, ml_engine: HealthMLEngine):
        self.ml_engine = ml_engine

    def _infer_payload_schedule(self, history: pd.DataFrame) -> list[str]:
        """
        Continue the dataset's typical payload duty cycle (~30 min ON / ~62 min STANDBY)
        from the streak already in progress at the end of history.
        """
        ON_DUR = 30
        ST_DUR = 62
        statuses = history["payload_status"].astype(str).str.upper().tolist()
        if not statuses:
            return ["STANDBY"] * 1000

        cur = statuses[-1]
        streak = 1
        for s in reversed(statuses[:-1]):
            if s == cur:
                streak += 1
            else:
                break

        # Build a long schedule starting mid-cycle
        remaining = max(0, (ON_DUR if cur == "ON" else ST_DUR) - streak)
        schedule = []
        state = cur
        left = remaining if remaining > 0 else (ON_DUR if state == "ON" else ST_DUR)
        # If streak already consumed a full block, flip immediately
        if remaining == 0:
            state = "STANDBY" if cur == "ON" else "ON"
            left = ON_DUR if state == "ON" else ST_DUR

        for _ in range(2000):
            schedule.append(state)
            left -= 1
            if left <= 0:
                state = "STANDBY" if state == "ON" else "ON"
                left = ON_DUR if state == "ON" else ST_DUR
        return schedule

    def _resolve_payload(
        self,
        override: str,
        base_status: str,
        step: int,
        schedule: list[str] | None = None,
    ) -> tuple[str, float]:
        if override == "FORCE_OFF":
            return "STANDBY", 0.0
        if override == "FORCE_ON":
            return "ON", PAYLOAD_ON_W
        if override == "DUTY_CYCLE_50":
            on = (step % 10) < 5
            return ("ON", PAYLOAD_ON_W) if on else ("STANDBY", STANDBY_PAYLOAD_W)
        if override == "SCHEDULE" and schedule:
            status = schedule[min(step - 1, len(schedule) - 1)]
            return ("ON", PAYLOAD_ON_W) if status == "ON" else ("STANDBY", STANDBY_PAYLOAD_W)
        # KEEP
        status = str(base_status or "STANDBY").upper()
        if status == "ON":
            return "ON", PAYLOAD_ON_W
        return "STANDBY", STANDBY_PAYLOAD_W

    def _estimate_sun_from_history(self, history: pd.DataFrame) -> np.ndarray:
        try:
            pos = history[["position_x", "position_y", "position_z"]].to_numpy(dtype=float)
            flags = history["sunlit"].astype(bool).to_numpy()
            return estimate_sun_vector(pos, flags)
        except Exception:
            return DEFAULT_SUN_ECI.copy()

    def simulate_trajectory(
        self,
        initial_history: pd.DataFrame,
        horizon_minutes: int = 60,
        step_seconds: int = 60,
        controls: dict = None,
        ground_truth_future: pd.DataFrame = None  # kept for API compat; never used as prediction
    ) -> dict:
        """
        Propagates the satellite state forward from the last row of initial_history.
        Always runs physics + ML — never copies ground-truth rows into the forecast.
        """
        controls = controls or {}
        scenario_id = controls.get("scenario_id", "SCN-NOMINAL")
        scenario_label = controls.get("scenario_label", "Nominal Flight Plan")
        payload_override = controls.get("payload_override", "KEEP")
        delta_v_prograde_ms = float(controls.get("delta_v_prograde_ms", 0.0))
        delta_v_radial_ms = float(controls.get("delta_v_radial_ms", 0.0))
        delta_v_normal_ms = float(controls.get("delta_v_normal_ms", 0.0))
        thermal_slew_deg = float(controls.get("thermal_slew_deg", 0.0))

        last_row = initial_history.iloc[-1].to_dict()
        num_steps = max(1, int((horizon_minutes * 60) / step_seconds))

        a = _safe_float(last_row.get("semi_major_axis"), 6800.0)
        e = _safe_float(last_row.get("eccentricity"), 0.0008)
        inc = _safe_float(last_row.get("inclination"), 51.65)
        raan = _safe_float(last_row.get("raan"), 214.6)
        argp = _safe_float(last_row.get("argument_of_perigee"), 92.0)
        nu = _safe_float(last_row.get("true_anomaly"), 99.0)

        batt_pct = _safe_float(last_row.get("battery_percentage"), 95.0)
        batt_v = _safe_float(last_row.get("battery_voltage"), 8.25)
        temp_c = _safe_float(last_row.get("temperature"), 13.0)
        fuel_pct = _safe_float(last_row.get("fuel_remaining_pct"), 100.0)
        payload_status = str(last_row.get("payload_status", "STANDBY")).upper()

        r0 = np.array([
            _safe_float(last_row.get("position_x"), 6800.0),
            _safe_float(last_row.get("position_y"), 0.0),
            _safe_float(last_row.get("position_z"), 0.0),
        ])
        v0 = np.array([
            _safe_float(last_row.get("velocity_x"), 0.0),
            _safe_float(last_row.get("velocity_y"), 7.66),
            _safe_float(last_row.get("velocity_z"), 0.0),
        ])

        dv_eci = np.zeros(3)
        if abs(delta_v_prograde_ms) > 1e-4 or abs(delta_v_radial_ms) > 1e-4 or abs(delta_v_normal_ms) > 1e-4:
            v_unit = v0 / max(np.linalg.norm(v0), 1e-6)
            r_unit = r0 / max(np.linalg.norm(r0), 1e-6)
            w_unit = np.cross(r_unit, v_unit)
            w_unit = w_unit / max(np.linalg.norm(w_unit), 1e-6)
            # Control inputs are m/s → convert to km/s for ECI state
            dv_eci = (
                delta_v_prograde_ms * v_unit
                + delta_v_radial_ms * r_unit
                + delta_v_normal_ms * w_unit
            ) / 1000.0
            fuel_cost_pct = float(np.linalg.norm(dv_eci) * 1000.0) * 0.08
            fuel_pct = max(0.0, fuel_pct - fuel_cost_pct)

        sun_vec = self._estimate_sun_from_history(initial_history)
        # Slow apparent sun drift (~1 deg/day) for multi-hour horizons
        sun_drift_rad_per_s = math.radians(1.0) / 86400.0

        payload_schedule = None
        if payload_override == "SCHEDULE" or (
            payload_override == "KEEP" and scenario_id in ("SCN-NOMINAL", "SCN-ORBIT-BOOST")
        ):
            # Continue the observed ON/~30m STANDBY/~62m duty cycle for fair nominal/boost compares
            payload_override = "SCHEDULE"
            payload_schedule = self._infer_payload_schedule(initial_history)

        simulated_rows = []
        history_window = initial_history.copy()
        curr_time = pd.to_datetime(last_row.get("timestamp", "2019-12-09T00:00:00Z"), utc=True)
        if curr_time.tzinfo is not None:
            curr_time = curr_time.tz_localize(None)

        # Absolute GMST-ish phase seeded from history length so lon is continuous
        gmst0 = len(initial_history) * step_seconds * OMEGA_EARTH
        delta_v_applied = False
        dt_hours = step_seconds / 3600.0
        dt_minutes = step_seconds / 60.0

        for step in range(1, num_steps + 1):
            curr_time = curr_time + pd.Timedelta(seconds=step_seconds)

            # Rotate sun slightly with elapsed time
            ang = sun_drift_rad_per_s * step * step_seconds
            c, s = math.cos(ang), math.sin(ang)
            sun_step = np.array([
                c * sun_vec[0] - s * sun_vec[1],
                s * sun_vec[0] + c * sun_vec[1],
                sun_vec[2],
            ])
            sun_step = sun_step / max(np.linalg.norm(sun_step), 1e-12)

            dv_step = None
            if not delta_v_applied and np.linalg.norm(dv_eci) > 0:
                dv_step = dv_eci
                delta_v_applied = True

            orbit_state = propagate_orbit_step(
                a, e, inc, raan, argp, nu,
                dt_seconds=step_seconds,
                delta_v_vector=dv_step,
                sun_vec_eci=sun_step,
            )
            a = orbit_state["semi_major_axis"]
            e = orbit_state["eccentricity"]
            inc = orbit_state["inclination"]
            raan = orbit_state["raan"]
            argp = orbit_state["argument_of_perigee"]
            nu = orbit_state["true_anomaly"]
            sunlit = bool(orbit_state["sunlit"])

            r_vec = np.array([
                orbit_state["position_x"],
                orbit_state["position_y"],
                orbit_state["position_z"],
            ])
            lat, lon, alt = cartesian_to_geodetic(
                r_vec, gmst_rad=gmst0 + step * step_seconds * OMEGA_EARTH
            )

            curr_payload_status, curr_payload_pwr = self._resolve_payload(
                payload_override, payload_status, step, schedule=payload_schedule
            )
            total_draw = BUS_POWER_W + curr_payload_pwr

            # Solar: peak output attenuated by intentional thermal slew off-sun
            slew_rad = math.radians(max(0.0, thermal_slew_deg))
            panel_factor = max(0.05, math.cos(slew_rad))
            if sunlit:
                # Mild orbital variation so power isn't a flat line
                phase = math.radians(nu)
                solar_input = PEAK_SOLAR_W * panel_factor * (0.92 + 0.08 * abs(math.cos(phase)))
            else:
                solar_input = 0.25  # albedo / residual

            net_pwr = solar_input - total_draw
            batt_current = net_pwr / max(batt_v, 6.5)

            # Battery SoC integration (80 Wh pack calibrated to dataset charge/discharge rates)
            delta_wh = net_pwr * dt_hours
            batt_pct = float(np.clip(batt_pct + (delta_wh / BATTERY_CAPACITY_WH) * 100.0, 20.0, 100.0))
            # Voltage tracks SoC with small IR drop/rise from current
            batt_v = float(np.clip(
                7.20 + (batt_pct / 100.0) * 1.20 + (0.08 if batt_current > 0 else -0.08),
                6.70, 8.45
            ))

            # Thermal rates empirically fit to dataset (payload × sunlit interaction)
            payload_on = curr_payload_status == "ON"
            if sunlit and payload_on:
                d_temp = 0.74 * panel_factor
            elif sunlit and not payload_on:
                d_temp = 0.18 * panel_factor
            elif (not sunlit) and payload_on:
                d_temp = -0.48
            else:
                d_temp = -1.02
            # Intentional sun-slew cools panels; forced payload-off sheds internal heat faster
            if thermal_slew_deg > 0 and sunlit:
                d_temp -= 0.01 * min(thermal_slew_deg, 45.0) / 15.0
            if payload_override == "FORCE_OFF" and sunlit:
                d_temp -= 0.05
            temp_c = float(np.clip(temp_c + d_temp * dt_minutes, -5.0, 45.0))

            # Comms windows ~ every 20 minutes for ~2 minutes (matches dataset cadence)
            comm_status = "LINKED" if (step % 20) < 2 else "NO_CONTACT"

            row_data = {
                "timestamp": curr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "satellite_id": str(last_row.get("satellite_id", "ISS-25544")),
                "position_x": round(orbit_state["position_x"], 6),
                "position_y": round(orbit_state["position_y"], 6),
                "position_z": round(orbit_state["position_z"], 6),
                "velocity_x": round(orbit_state["velocity_x"], 6),
                "velocity_y": round(orbit_state["velocity_y"], 6),
                "velocity_z": round(orbit_state["velocity_z"], 6),
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "altitude_km": round(alt, 2),
                "semi_major_axis": round(orbit_state["semi_major_axis"], 6),
                "eccentricity": round(orbit_state["eccentricity"], 9),
                "inclination": round(orbit_state["inclination"], 6),
                "raan": round(orbit_state["raan"], 6),
                "argument_of_perigee": round(orbit_state["argument_of_perigee"], 6),
                "true_anomaly": round(orbit_state["true_anomaly"], 6),
                "battery_percentage": round(batt_pct, 2),
                "battery_voltage": round(batt_v, 3),
                "battery_current": round(batt_current, 3),
                "temperature": round(temp_c, 2),
                "solar_power_input": round(solar_input, 2),
                "power_draw": round(total_draw, 2),
                "payload_status": curr_payload_status,
                "payload_power_draw": round(curr_payload_pwr, 2),
                "communication_status": comm_status,
                "fuel_remaining_pct": round(fuel_pct, 2),
                "sunlit": sunlit,
                "angular_velocity_x": round(_safe_float(last_row.get("angular_velocity_x"), 0.02), 4),
                "angular_velocity_y": round(_safe_float(last_row.get("angular_velocity_y"), 0.01), 4),
                "angular_velocity_z": round(_safe_float(last_row.get("angular_velocity_z"), 0.01), 4),
                "orientation_q0": round(_safe_float(last_row.get("orientation_q0"), 0.7071), 4),
                "orientation_q1": round(_safe_float(last_row.get("orientation_q1"), 0.0), 4),
                "orientation_q2": round(_safe_float(last_row.get("orientation_q2"), 0.7071), 4),
                "orientation_q3": round(_safe_float(last_row.get("orientation_q3"), 0.0), 4),
                "step_index": step,
                "horizon_minute": round((step * step_seconds) / 60.0, 1),
            }
            simulated_rows.append(row_data)

        # Batch ML evaluation using the trained XGBoost models
        df_sim = pd.DataFrame(simulated_rows)
        full_df = pd.concat([history_window.tail(15), df_sim], ignore_index=True)
        ml_evals = self.ml_engine.predict_batch(full_df)
        sim_ml_evals = ml_evals[-num_steps:]

        combined_results = []
        for i, row in enumerate(simulated_rows):
            eval_dict = sim_ml_evals[i]
            horizon_m = row["horizon_minute"]
            # Confidence decays with horizon; trajectory uncertainty grows ~linearly in LEO
            conf_decay = float(round(math.exp(-0.008 * horizon_m), 3))

            merged = dict(row)
            merged.update(eval_dict)
            merged["state_confidence"] = conf_decay
            merged["scenario_id"] = scenario_id
            merged["scenario_label"] = scenario_label
            combined_results.append(merged)

        final_state = combined_results[-1]
        min_batt = min(r["battery_percentage"] for r in combined_results)
        max_temp = max(r["temperature"] for r in combined_results)
        avg_health = sum(r["health_score"] for r in combined_results) / len(combined_results)
        anomaly_count = sum(1 for r in combined_results if r["anomaly_flag"])

        return {
            "scenario_id": scenario_id,
            "scenario_label": scenario_label,
            "controls": controls,
            "horizon_minutes": horizon_minutes,
            "summary": {
                "final_health_score": round(final_state["health_score"], 2),
                "average_health_score": round(avg_health, 2),
                "min_battery_pct": round(min_batt, 2),
                "final_battery_pct": round(final_state["battery_percentage"], 2),
                "max_temperature_c": round(max_temp, 2),
                "final_temperature_c": round(final_state["temperature"], 2),
                "fuel_remaining_pct": round(final_state["fuel_remaining_pct"], 2),
                "anomalies_predicted": int(anomaly_count),
                "final_risk_level": final_state["risk_level"],
            },
            "trajectory": combined_results,
        }

    def generate_scenario_recommendation(self, scenarios: list[dict]) -> dict:
        """
        Explainable AI Decision Engine: Evaluates candidate scenarios and produces
        a justified recommendation based on safety margins and health optimization.
        """
        if not scenarios:
            return {"recommended_id": "", "reasoning": "No scenarios evaluated."}

        scored = []
        for s in scenarios:
            sumry = s["summary"]
            # Penalties only fire when margins are actually unsafe
            batt_pen = max(0.0, 55.0 - sumry["min_battery_pct"]) * 2.0
            hot_pen = max(0.0, sumry["max_temperature_c"] - 32.0) * 2.5
            cold_pen = max(0.0, 0.0 - sumry["final_temperature_c"]) * 1.5
            anom_pen = sumry["anomalies_predicted"] * 12.0

            # Health dominates; do not reward overcooling when the bird is already healthy
            utility = (
                sumry["average_health_score"] * 0.65
                + sumry["final_health_score"] * 0.20
                + sumry["final_battery_pct"] * 0.15
                - batt_pen - hot_pen - cold_pen - anom_pen
            )
            scored.append({
                "scenario_id": s["scenario_id"],
                "scenario_label": s["scenario_label"],
                "utility": utility,
                "summary": sumry,
            })

        scored.sort(key=lambda x: x["utility"], reverse=True)
        winner = scored[0]
        runner_up = scored[1] if len(scored) > 1 else None

        reasons = []
        reasons.append(
            f"Recommended Strategy: **{winner['scenario_label']}** "
            f"(Utility Score: {winner['utility']:.1f})."
        )

        win_sum = winner["summary"]
        reasons.append(
            f"Maintains an optimal average Health Score of **{win_sum['average_health_score']} pts** "
            f"with minimum battery reserve at **{win_sum['min_battery_pct']}%** "
            f"(Final: {win_sum['final_battery_pct']}%) "
            f"and peak thermal load capped at **{win_sum['max_temperature_c']}°C**."
        )

        if runner_up:
            run_sum = runner_up["summary"]
            diff_health = win_sum["average_health_score"] - run_sum["average_health_score"]
            diff_batt = win_sum["final_battery_pct"] - run_sum["final_battery_pct"]
            health_phrase = (
                f"+{diff_health:.1f} higher" if diff_health >= 0 else f"{abs(diff_health):.1f} lower"
            )
            batt_phrase = (
                f"+{diff_batt:.1f}%" if diff_batt >= 0 else f"{diff_batt:.1f}%"
            )
            reasons.append(
                f"Compared to '{runner_up['scenario_label']}', this strategy provides {health_phrase} "
                f"health-score margin and {batt_phrase} battery reserve while keeping risk level "
                f"strictly {win_sum['final_risk_level']}."
            )

        return {
            "recommended_scenario_id": winner["scenario_id"],
            "recommended_label": winner["scenario_label"],
            "utility_score": round(winner["utility"], 2),
            "executive_summary": " ".join(reasons),
            "rankings": [
                {
                    "scenario_id": s["scenario_id"],
                    "scenario_label": s["scenario_label"],
                    "utility": round(s["utility"], 2),
                    "summary": s["summary"],
                }
                for s in scored
            ],
        }
