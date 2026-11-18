import os
import sys
import multiprocessing
import uvicorn

def start_digital_twin():
    print("[Digital Twin] Starting on http://0.0.0.0:8000...")
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, log_level="info")

def start_mission_intelligence():
    print("[Mission Intelligence] Starting on http://0.0.0.0:8001...")
    uvicorn.run("mission_intelligence_server:app", host="0.0.0.0", port=8001, log_level="info")

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    multiprocessing.freeze_support()
    
    p1 = multiprocessing.Process(target=start_digital_twin)
    p2 = multiprocessing.Process(target=start_mission_intelligence)
    
    p1.start()
    p2.start()
    
    try:
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        p1.terminate()
        p2.terminate()
