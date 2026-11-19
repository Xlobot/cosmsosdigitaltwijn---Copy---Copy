#!/usr/bin/env bash
echo "========================================================"
echo "  Starting COSMOS Telemetry Generator REST API Service"
echo "========================================================"
python3 generator_api.py --port 8080 --interval 1.0

