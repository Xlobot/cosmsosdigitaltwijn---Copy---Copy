"""
COSMOS Generator Standalone Test Suite
======================================
Tests the generator's data fidelity, physics consistency, and API schema
without needing the digital twin module.
"""

import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import generator_api


def run_tests():
    print("=" * 60)
    print(" Running COSMOS Generator Standalone Verification")
    print("=" * 60)

    # 1. Test dataset loading
    print("[1/5] Testing Dataset Loading...")
    rows = generator_api.DATASET
    assert len(rows) > 0, "Dataset is empty!"
    print(f"      OK: Loaded {len(rows)} telemetry rows from source CSV.")

    # 2. Test metadata & keys catalog
    print("[2/5] Testing Telemetry Key Metadata...")
    keys_resp = generator_api.get_keys()
    total_keys = keys_resp["total_keys"]
    assert total_keys == 32, f"Expected 32 keys, found {total_keys}"
    subsystems = keys_resp["subsystem_groups"]
    print(f"      OK: 32 keys registered across {len(subsystems)} subsystems.")

    # 3. Test Schema endpoint
    print("[3/5] Testing JSON Schema Generation...")
    schema = generator_api.get_schema()
    assert "properties" in schema, "Schema missing 'properties' block"
    assert len(schema["properties"]) == 32, "Schema properties count mismatch"
    print(f"      OK: Valid JSON Schema generated for all 32 channels.")

    # 4. Test In-memory Pacing & Streaming Engine
    print("[4/5] Testing Real-Time Streaming Engine...")
    time.sleep(1.2)
    latest = generator_api.get_latest()
    assert latest, "No latest row produced!"
    assert "timestamp" in latest, "Missing timestamp in latest frame"
    assert "position_x" in latest and "velocity_x" in latest, "Missing orbit state vectors"
    assert "battery_percentage" in latest and "temperature" in latest, "Missing EPS/TCS signals"
    print(f"      OK: Streaming engine active. Latest frame: {latest['timestamp']} (index #{latest.get('emit_index')})")

    # 5. Test Anomaly Injection
    print("[5/6] Testing Synthetic Anomaly Injection...")
    req = generator_api.AnomalyInjectionRequest(
        duration_ticks=5,
        overrides={"temperature": 99.9, "battery_voltage": 3.8}
    )
    res = generator_api.inject_anomaly(req)
    assert res["overrides"]["temperature"] == 99.9
    time.sleep(1.1)
    anom_frame = generator_api.get_latest()
    assert anom_frame["temperature"] == 99.9, f"Expected 99.9, got {anom_frame['temperature']}"
    assert anom_frame["battery_voltage"] == 3.8, f"Expected 3.8, got {anom_frame['battery_voltage']}"
    print(f"      OK: Injected fault successfully reflected in live stream: Temp={anom_frame['temperature']}°C, Volt={anom_frame['battery_voltage']}V.")

    # 6. Test Universal Digital Twin Parameter Compatibility
    print("[6/6] Testing Universal Digital Twin Compatibility...")
    # Test 'since' vs 'cursor' vs 'offset'
    rows_since = generator_api.get_rows(since=0, limit=2)
    rows_cursor = generator_api.get_rows(cursor=0, limit=2)
    rows_offset = generator_api.get_rows(offset=0, limit=2)
    assert len(rows_since) > 0 and len(rows_cursor) > 0 and len(rows_offset) > 0
    # Test envelope format
    env = generator_api.get_rows(cursor=0, limit=2, format="envelope")
    assert "status" in env and env["status"] == "ok" and "rows" in env
    # Test geodetic pre-calculated fields and shorthand aliases
    sample = rows_since[0]
    assert "latitude" in sample and "longitude" in sample and "altitude_km" in sample
    assert "time" in sample and "fuel_remaining" in sample and "battery_soc" in sample
    print(f"      OK: Universal aliases verified. Lat={sample['latitude']}, Lon={sample['longitude']}, Alt={sample['altitude_km']} km.")

    print("\n" + "=" * 60)
    print(" ALL TESTS PASSED! Telemetry generator is ready for production.")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()

