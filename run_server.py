import os
import sys
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Bind to 0.0.0.0 to support localhost, 127.0.0.1, and IPv6 loopback
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, log_level="info")
