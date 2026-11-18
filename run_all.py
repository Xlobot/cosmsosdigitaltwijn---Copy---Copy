import os
import sys
import multiprocessing
import uvicorn

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def start_telemetry_generator():
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    print("[Telemetry Generator] Starting on http://0.0.0.0:8080...", flush=True)
    uvicorn.run("cosmos_telemetry_generator.generator_api:app", host="0.0.0.0", port=8080, log_level="info")

def start_digital_twin():
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    print("[Digital Twin & UI] Starting on http://0.0.0.0:8000...", flush=True)
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, log_level="info")

def start_mission_intelligence():
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    print("[Mission Intelligence] Starting on http://0.0.0.0:8001...", flush=True)
    uvicorn.run("mission_intelligence_server:app", host="0.0.0.0", port=8001, log_level="info")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    print("=" * 65)
    print("  LAUNCHING COSMOS DIGITAL TWIN FLIGHT SUITE")
    print("  1. Telemetry Generator      -> http://127.0.0.1:8080")
    print("  2. Digital Twin & Cockpit   -> http://127.0.0.1:8000")
    print("  3. Mission Intelligence     -> http://127.0.0.1:8001")
    print("=" * 65, flush=True)

    p_gen = multiprocessing.Process(target=start_telemetry_generator)
    p_dt = multiprocessing.Process(target=start_digital_twin)
    p_mi = multiprocessing.Process(target=start_mission_intelligence)
    
    p_gen.start()
    p_dt.start()
    p_mi.start()
    
    try:
        p_gen.join()
        p_dt.join()
        p_mi.join()
    except KeyboardInterrupt:
        print("\nShutting down all COSMOS services...")
        p_gen.terminate()
        p_dt.terminate()
        p_mi.terminate()
