import os
import sys
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("[Mission Intelligence] Launching standalone MI server on port 8001...")
    uvicorn.run("mission_intelligence_server:app", host="0.0.0.0", port=8001, log_level="info")
