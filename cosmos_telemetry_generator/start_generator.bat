@echo off
echo ========================================================
echo   Starting COSMOS Telemetry Generator REST API Service
echo ========================================================
python generator_api.py --port 8080 --interval 1.0
pause

