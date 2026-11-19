import os
import sys
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("=" * 60)
    print("  COSMOS Telemetry Generator REST API Service")
    print("  Running at: http://localhost:8080")
    print("  Interactive Swagger UI: http://localhost:8080/docs")
    print("  Digital Twin Ingest Endpoint: http://localhost:8080/rows")
    print("=" * 60, flush=True)
    uvicorn.run("cosmos_telemetry_generator.generator_api:app", host="0.0.0.0", port=8080, log_level="info")
