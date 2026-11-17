# Mission Intelligence Module for COSMOS

## Overview

Mission Intelligence is a **completely separate, independent server** for COSMOS (Cognitive Mission Intelligence Platform) that provides decision support for satellite operations. It analyzes mission conditions, identifies risks, evaluates possible actions, compares outcomes, and provides explainable recommendations to human operators.

**Critical Design Principle:** 
- Mission Intelligence runs as a **separate standalone server** on port 8001
- The Digital Twin server runs independently on port 8000
- Mission Intelligence connects to Digital Twin via REST API (read-only)
- **No Digital Twin code has been modified**

## Architecture

### Components

1. **Digital Twin Data Adapter** (`dt_adapter.py`)
   - Fetches and normalizes outputs from the Digital Twin via REST API
   - Handles missing, stale, or invalid data safely
   - Read-only integration - no modifications to Digital Twin

2. **Mission Situation Assessor** (`situation_assessor.py`)
   - Combines Digital Twin outputs, telemetry, health assessments, and mission context
   - Summarizes current and predicted mission situation
   - Clearly distinguishes observations from predictions

3. **Risk Assessment Engine** (`risk_engine.py`)
   - Identifies anomalies, concerning trends, predicted threshold crossings
   - Assesses subsystem risks and potential mission impacts
   - Uses existing Health Engine results and configurable rules

4. **Candidate Action Generator** (`action_generator.py`)
   - Generates feasible candidate actions based on evidence and constraints
   - Actions include: monitor, investigate, payload adjustment, thermal adjustment, orbit maneuvers
   - Context-aware - only generates actions that make sense for the situation

5. **Scenario Evaluator** (`scenario_evaluator.py`)
   - Evaluates candidate actions using Digital Twin's what-if capabilities
   - Compares outcomes against baseline using supported metrics
   - Reuses existing scenario capabilities through their current interfaces

6. **Recommendation Engine** (`recommendation_engine.py`)
   - Ranks candidate actions using transparent criteria
   - Criteria: risk reduction, health improvement, resource cost, feasibility, uncertainty
   - Explains why each action is recommended with trade-offs

7. **Explanation Engine** (`explanation_engine.py`)
   - Provides comprehensive explanations for recommendations
   - Includes: identified issue, supporting evidence, Digital Twin prediction, expected benefit
   - Documents risks, trade-offs, assumptions, missing information, and uncertainty

8. **Decision Log** (`decision_log.py`)
   - Records recommendations and operator decisions (accepted, rejected, deferred)
   - Preserves timestamps and reasoning
   - Stored in JSON file for portability

### Digital Twin Integration Interface

Mission Intelligence integrates with the Digital Twin through these existing REST API endpoints:

- **State**: `GET /api/state?index={row}` - Current telemetry + health scores
- **Prediction**: `POST /api/predict` - Forward propagation with validation
- **Scenarios**: `POST /api/fork` - Multi-scenario comparison (what-if analysis)
- **Anomalies**: `GET /api/anomalies` - Curated anomaly events
- **Status**: `GET /api/status` - Digital Twin health status

**No Digital Twin source files were modified.**

## Files Created

### Mission Intelligence Server (1 new file)

1. `mission_intelligence_server.py` - Standalone Mission Intelligence server (port 8001)

### Backend (11 new files in `backend/mission_intelligence/`)

1. `__init__.py` - Module initialization and exports
2. `config.py` - Configuration thresholds, rules, and operational constraints
3. `dt_adapter.py` - Digital Twin Data Adapter (read-only API integration)
4. `situation_assessor.py` - Mission Situation Assessor
5. `risk_engine.py` - Risk Assessment Engine
6. `action_generator.py` - Candidate Action Generator
7. `scenario_evaluator.py` - Scenario Evaluation
8. `recommendation_engine.py` - Recommendation and Ranking Engine
9. `explanation_engine.py` - Explanation Engine
10. `decision_log.py` - Decision Log
11. `api.py` - Mission Intelligence API coordinator

### Backend Modified (0 files)

**IMPORTANT: No Digital Twin files were modified.** The Digital Twin remains completely unchanged.

### Frontend (1 new file)

1. `frontend/src/components/MissionIntelligenceTab.jsx` - Mission Intelligence dashboard tab

### Frontend Modified (1 file)

1. `frontend/src/App.jsx` - Added Mission Intelligence tab to navigation

### Other

1. `backend/requirements.txt` - Added httpx dependency for async HTTP requests

## Data Sources

### Primary Data Sources

1. **cosmos_twin_dataset.xlsx** - ISS replay data (demo/replay only, 4,320 rows)
   - Purpose: Demonstration and replay
   - Status: Simulated/replay data, not live spacecraft
   - Limitations: Health labels are formula-based, only 3 anomaly events

2. **ESA-Mission1** - Real spacecraft telemetry with labeled anomalies
   - Location: `D:\mission_intelligence\extracted_esa\ESA-Mission1\`
   - Purpose: Validation of anomaly detection
   - Status: Real spacecraft data
   - Files: anomaly_types.csv, channels.csv, labels.csv, channel data

3. **SMAP/MSL (archive)** - NASA spacecraft data with labeled anomalies
   - Location: `D:\mission_intelligence\extracted_archive\`
   - Purpose: Validation of anomaly detection
   - Status: Real spacecraft data
   - File: labeled_anomalies.csv

### Data Usage Notes

- **cosmos_twin_dataset.xlsx** is used for the main demo/replay functionality
- ESA and SMAP/MSL datasets are available for validation but not currently integrated into the main workflow
- All data sources are clearly distinguished (simulated vs real)
- No telemetry, ground truth, predictions, or mission constraints are invented

## Installation and Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- Existing COSMOS Digital Twin installed and working

### Backend Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

The required packages are:
- fastapi
- uvicorn
- httpx (for async HTTP requests to Digital Twin)
- pandas
- numpy
- joblib
- openpyxl

2. No additional configuration needed - Mission Intelligence auto-initializes on startup

### Frontend Setup

1. No additional dependencies needed - uses existing React setup
2. Mission Intelligence tab will appear automatically in the navigation

### Running the System

**IMPORTANT: You need to run TWO separate servers**

1. **Start the Digital Twin server** (in Terminal 1):
```bash
python run_server.py
```
The Digital Twin will start on `http://0.0.0.0:8000`

2. **Start the Mission Intelligence server** (in Terminal 2):
```bash
python mission_intelligence_server.py
```
The Mission Intelligence server will start on `http://0.0.0.0:8001`

3. **Start the frontend** (in Terminal 3):
```bash
cd frontend
npm run dev
```
The frontend will start on `http://localhost:5173` (or 5174 if 5173 is in use)

4. Open the browser to the frontend URL

5. Navigate to the "Mission Intelligence" tab in the navigation

### Environment Variables (Optional)

You can customize the Digital Twin URL by setting an environment variable:
```bash
set DIGITAL_TWIN_URL=http://127.0.0.1:8000
python mission_intelligence_server.py
```

## API Endpoints

### Mission Intelligence Server (Port 8001)

#### GET /
Root endpoint.

**Response:**
```json
{
  "service": "COSMOS Mission Intelligence",
  "status": "ONLINE",
  "digital_twin_url": "http://127.0.0.1:8000"
}
```

#### GET /api/health
Check health of Mission Intelligence and Digital Twin connection.

**Response:**
```json
{
  "mission_intelligence_status": "ONLINE",
  "digital_twin_status": { ... },
  "components": {
    "dt_adapter": "ONLINE",
    "situation_assessor": "ONLINE",
    "risk_engine": "ONLINE",
    "action_generator": "ONLINE",
    "scenario_evaluator": "ONLINE",
    "recommendation_engine": "ONLINE",
    "explanation_engine": "ONLINE",
    "decision_log": "ONLINE"
  },
  "checked_at": "2026-10-25T04:53:45.884917"
}
```

#### POST /api/assess
Get complete Mission Intelligence assessment.

**Request Body:**
```json
{
  "row_index": 0,
  "horizon_minutes": 60,
  "run_scenarios": true
}
```

**Response:**
```json
{
  "assessed_at": "2026-10-25T04:53:49.701978",
  "row_index": 100,
  "horizon_minutes": 60,
  "recommendation_id": "REC-20261025045349-1",
  "situation": { ... },
  "risk_assessment": { ... },
  "candidate_actions": [ ... ],
  "scenario_evaluation": { ... },
  "ranked_actions": { ... },
  "explanation": { ... },
  "data_availability": { ... }
}
```

#### POST /api/decision
Submit operator decision on a recommendation.

**Request Body:**
```json
{
  "recommendation_id": "REC-20261025045349-1",
  "decision": "accepted",
  "reasoning": "Accepted based on MI recommendation",
  "operator": "operator"
}
```

**Response:**
```json
{
  "success": true,
  "recommendation_id": "REC-20261025045349-1",
  "decision": "accepted",
  "timestamp": "2026-10-25T04:55:00.000000"
}
```

#### GET /api/history
Get decision history.

**Query Parameters:**
- `limit` (optional): Maximum number of entries (default: 10)
- `operator` (optional): Filter by operator

**Response:**
```json
{
  "history": [ ... ],
  "statistics": {
    "total_recommendations": 10,
    "decisions_made": 8,
    "accepted": 5,
    "rejected": 2,
    "deferred": 1,
    "pending": 2,
    "acceptance_rate": 62.5
  },
  "retrieved_at": "2026-10-25T04:55:00.000000"
}
```

### Digital Twin Server (Port 8000) - Unchanged

The Digital Twin server remains completely unchanged with its original endpoints:
- `GET /api/status`
- `GET /api/state`
- `GET /api/timeline`
- `GET /api/anomalies`
- `GET /api/dataset/all`
- `POST /api/predict`
- `POST /api/fork`
- `GET /api/models/info`

## Testing Results

### Component Tests

1. **Digital Twin Data Adapter** ✓
   - Successfully fetches state from Digital Twin API
   - Handles missing/stale data with appropriate status flags
   - HTTP client properly initialized and closed

2. **Mission Situation Assessor** ✓
   - Correctly assesses current situation from Digital Twin state
   - Distinguishes observations from predictions
   - Identifies concerns and subsystem status

3. **Risk Assessment Engine** ✓
   - Evaluates all risk rules correctly
   - Groups risks by severity and subsystem
   - Calculates overall risk level accurately

4. **Candidate Action Generator** ✓
   - Generates context-appropriate actions
   - Includes control parameters for Digital Twin scenarios
   - Provides rationale for each action

5. **Scenario Evaluator** ✓
   - Successfully calls Digital Twin fork API
   - Compares scenarios across multiple metrics
   - Returns structured comparison data

6. **Recommendation Engine** ✓
   - Ranks actions using weighted criteria
   - Provides justification and trade-offs
   - Selects best recommendation

7. **Explanation Engine** ✓
   - Generates comprehensive explanations
   - Traces evidence to data sources
   - Documents assumptions and uncertainty

8. **Decision Log** ✓
   - Successfully logs recommendations
   - Records operator decisions
   - Retrieves history and statistics

### Integration Tests

1. **Digital Twin API Integration** ✓
   - All Digital Twin endpoints accessible
   - Data properly normalized and consumed
   - Error handling for API failures

2. **Full Assessment Flow** ✓
   - Complete assessment generated successfully
   - All components coordinated correctly
   - Response includes all expected fields

3. **Health Check** ✓
   - Mission Intelligence status: ONLINE
   - Digital Twin status: ONLINE
   - All components reported as ONLINE

### Digital Twin Verification

**Confirmed: No Digital Twin source files were modified.**

Files verified as unchanged:
- `backend/ml_engine.py`
- `backend/scenario_engine.py`
- `backend/data_manager.py`
- `backend/orbit_propagator.py`

## Dashboard Features

The Mission Intelligence dashboard tab includes:

1. **Mission Situation**
   - Overall status (NOMINAL, MEDIUM_RISK, HIGH_RISK, CRITICAL)
   - Health score with color coding
   - Battery percentage and status
   - Temperature and status
   - Active concerns list

2. **Risk Assessment**
   - Risk count by severity (CRITICAL, HIGH, MEDIUM, LOW)
   - Triggered risk rules with descriptions
   - Subsystem risk levels
   - Overall risk level

3. **Recommended Action**
   - Top recommendation with explanation
   - Justification for the recommendation
   - Trade-offs identified
   - Action buttons: Accept, Reject, Defer

4. **Decision History**
   - Recent decisions with timestamps
   - Decision status (accepted, rejected, deferred)
   - Operator information

5. **Controls**
   - Horizon slider (30-120 minutes)
   - Scenario evaluation toggle
   - Refresh button

## Current Limitations

1. **Data Sources**
   - Primary data is from simulated/replay dataset (cosmos_twin_dataset.xlsx)
   - ESA and SMAP/ML datasets available but not fully integrated
   - No live spacecraft telemetry integration

2. **Prediction Accuracy**
   - Health labels in replay data are formula-based, not ground truth
   - Accuracy claims not made without proper validation
   - Validation on ESA/SMAP data planned but not yet implemented

3. **Scenario Evaluation**
   - Scenario evaluation requires Digital Twin to be running
   - If Digital Twin is unavailable, scenarios are skipped
   - Scenario evaluation can be disabled to improve performance

4. **Decision Log**
   - Stored in JSON file (not database)
   - No automated cleanup of old entries
   - Manual cleanup via API available

5. **External Constraints**
   - Mission timeline constraints not yet modeled
   - Ground station availability not considered
   - External dependencies not integrated

## Future Integration Points

1. **Live Data Integration**
   - Connect to live spacecraft telemetry streams
   - Real-time health monitoring
   - Live anomaly detection

2. **Enhanced Validation**
   - Integrate ESA anomaly dataset for baseline testing
   - Implement time-aware cross-validation
   - Compare against trivial baselines

3. **Advanced Scenarios**
   - More complex what-if scenarios
   - Multi-stage maneuver planning
   - Constrained optimization

4. **Decision Log Enhancement**
   - Database backend for scalability
   - Automated analysis of decision patterns
   - Operator performance metrics

5. **External Integration**
   - Mission planning systems
   - Ground station scheduling
   - Communication planning

## Important Notes

1. **Advisory Only**
   - Mission Intelligence only recommends actions
   - Does NOT send spacecraft commands
   - Does NOT connect to live spacecraft control systems
   - Human operator always makes the final decision

2. **Data Transparency**
   - All data sources are clearly identified
   - Simulated data is labeled as such
   - Real data is distinguished from predictions
   - Assumptions are documented

3. **No Claimed Accuracy**
   - No accuracy claims made without proper validation
   - Health scores from replay data are formula-based
   - Validation on real data required before operational use

4. **Digital Twin Integrity**
   - Digital Twin code remains unchanged
   - Read-only integration via REST API
   - Digital Twin continues to work as before
   - No retraining or model replacement

## Support

For issues or questions:
1. Check the health endpoint: `GET /api/mi/health`
2. Review server logs for error messages
3. Verify Digital Twin is running and accessible
4. Check that all dependencies are installed

## License

This module is part of the COSMOS project and follows the same license terms.
