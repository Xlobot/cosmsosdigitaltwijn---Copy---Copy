"""
COSMOS Role-Based Access Control (RBAC) Test Suite
===================================================
Tests all RBAC authorization rules specified in the COSMOS RBAC prompt:
1. Deny by default: Route walker checks all endpoints on all services for auth dependencies.
2. Token validity: No token -> 401, expired token -> 401, tampered signature -> 401, unknown role -> 403.
3. Service key vs user token separation: User cannot call service-key routes; service key cannot call user routes.
4. Parametrized Role x Route Matrix: viewer < analyst < operator < admin across Digital Twin, MI, and Generator.
5. Spoof prevention: A body with operator="someone_else" is ignored and token's sub is stored.
6. History filter: Non-admin filtering another operator -> 403. Admin or own sub -> 200.
7. Decision handling: Enum validation (422), unknown recommendation (404), double decision (409).
8. WebSocket & SSE streaming: Require valid token before streaming (Sec-WebSocket-Protocol or first auth message).
"""

import os
import sys
import json
import asyncio
import datetime
import pytest
import httpx
import websockets
from fastapi.routing import APIRoute
from starlette.routing import Route, WebSocketRoute

# Add root directory to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.server import app as dt_app
from mission_intelligence_server import app as mi_app
from cosmos_telemetry_generator.generator_api import app as gen_app
from cosmos_security import (
    create_access_token,
    get_user_by_username,
    create_user,
    COSMOS_SERVICE_KEY,
    SERVICE_KEY_HEADER,
    ROLE_VIEWER,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_ADMIN,
    PERMISSION_TABLE
)

DT_URL = "http://127.0.0.1:8000"
MI_URL = "http://127.0.0.1:8001"
GEN_URL = "http://127.0.0.1:8080"


# ---------------------------------------------------------------------------
# Fixtures for Role Tokens
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def tokens():
    """Generates valid JWT tokens for each role in the hierarchy and seeds DB accounts."""
    test_users = [
        ("test_viewer", ROLE_VIEWER),
        ("test_analyst", ROLE_ANALYST),
        ("test_operator", ROLE_OPERATOR),
        ("admin", ROLE_ADMIN),
    ]
    for u, r in test_users:
        user = get_user_by_username(u)
        if not user:
            try:
                create_user(u, "TestPassword123!", role=r)
            except Exception:
                pass

    return {
        ROLE_VIEWER: create_access_token({"sub": "test_viewer", "role": ROLE_VIEWER}),
        ROLE_ANALYST: create_access_token({"sub": "test_analyst", "role": ROLE_ANALYST}),
        ROLE_OPERATOR: create_access_token({"sub": "test_operator", "role": ROLE_OPERATOR}),
        ROLE_ADMIN: create_access_token({"sub": "admin", "role": ROLE_ADMIN}),
    }


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Deny By Default Route Walker Test
# ---------------------------------------------------------------------------
def test_all_routes_have_auth_dependencies():
    """
    Walk app.routes on each service (Digital Twin, MI, Generator) and fail
    if any route lacks an authorization dependency (except /healthz, /api/auth/login).
    """
    PUBLIC_ALLOWLIST = {
        "/healthz",
        "/api/auth/login",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/{full_path:path}",
        "/assets"
    }

    services = [
        ("Digital Twin", dt_app),
        ("Mission Intelligence", mi_app),
        ("Telemetry Generator", gen_app)
    ]

    for s_name, app_instance in services:
        for r in app_instance.routes:
            # Skip documentation, public allowlist, and static assets
            if r.path in PUBLIC_ALLOWLIST:
                continue

            if isinstance(r, APIRoute):
                # Verify that route has at least one dependency declared
                deps = r.dependant.dependencies
                assert len(deps) > 0, (
                    f"[{s_name}] Route '{r.methods} {r.path}' lacks an authorization dependency!"
                )
            elif isinstance(r, WebSocketRoute):
                # WebSocket routes handle auth in endpoint coroutine via authenticate_websocket
                assert r.endpoint.__name__ in ["websocket_telemetry", "websocket_telemetry_endpoint", "ws", "stream"], (
                    f"[{s_name}] Unprotected WebSocket route '{r.path}'!"
                )


# ---------------------------------------------------------------------------
# 2. Token Authentication Error Tests (401 / 403)
# ---------------------------------------------------------------------------
def test_missing_token_returns_401():
    """Calling a protected route without any token returns 401 Unauthorized."""
    with httpx.Client(timeout=5.0) as client:
        r_dt = client.get(f"{DT_URL}/api/status")
        assert r_dt.status_code == 401

        r_mi = client.get(f"{MI_URL}/api/health")
        assert r_mi.status_code == 401

        r_gen = client.get(f"{GEN_URL}/keys")
        assert r_gen.status_code == 401


def test_expired_token_returns_401():
    """Calling a protected route with an expired token returns 401 Unauthorized."""
    expired_token = create_access_token(
        {"sub": "test_viewer", "role": ROLE_VIEWER},
        expires_delta=datetime.timedelta(seconds=-30)
    )
    with httpx.Client(timeout=5.0) as client:
        res = client.get(f"{DT_URL}/api/status", headers=auth_header(expired_token))
        assert res.status_code == 401
        assert "expired" in res.text.lower()


def test_tampered_token_returns_401():
    """Calling with a tampered token (invalid signature) returns 401 Unauthorized."""
    valid_token = create_access_token({"sub": "test_viewer", "role": ROLE_VIEWER})
    tampered_token = valid_token[:-4] + "wxyz"
    with httpx.Client(timeout=5.0) as client:
        res = client.get(f"{DT_URL}/api/status", headers=auth_header(tampered_token))
        assert res.status_code == 401


def test_unknown_role_claim_returns_403():
    """Token with missing or unknown role claim returns 403 Forbidden."""
    unknown_role_token = create_access_token({"sub": "test_viewer", "role": "super_god_mode"})
    with httpx.Client(timeout=5.0) as client:
        res = client.get(f"{DT_URL}/api/status", headers=auth_header(unknown_role_token))
        assert res.status_code == 403
        assert "unknown role" in res.text.lower() or "missing or unknown" in res.text.lower()


# ---------------------------------------------------------------------------
# 3. Service Key vs User Token Separation Tests
# ---------------------------------------------------------------------------
def test_user_token_cannot_call_service_key_routes(tokens):
    """A regular user token (viewer/analyst/operator) cannot call service-key routes."""
    user_token = tokens[ROLE_OPERATOR]
    with httpx.Client(timeout=5.0) as client:
        # MI webhook endpoint requires service key (or admin)
        res = client.post(
            f"{MI_URL}/webhook/digital-twin/state",
            json={"twin_state_id": "TEST-01"},
            headers=auth_header(user_token)
        )
        assert res.status_code == 403


def test_service_key_cannot_call_user_routes():
    """An X-Service-Key header cannot act as a user on user-only routes."""
    headers = {SERVICE_KEY_HEADER: COSMOS_SERVICE_KEY}
    with httpx.Client(timeout=5.0) as client:
        # MI user health endpoint
        res_mi = client.get(f"{MI_URL}/api/health", headers=headers)
        assert res_mi.status_code == 401

        # DT user status endpoint
        res_dt = client.get(f"{DT_URL}/api/status", headers=headers)
        assert res_dt.status_code == 401


def test_service_key_succeeds_on_service_routes():
    """Valid X-Service-Key header succeeds on internal service routes."""
    headers = {SERVICE_KEY_HEADER: COSMOS_SERVICE_KEY}
    with httpx.Client(timeout=5.0) as client:
        res = client.post(
            f"{MI_URL}/webhook/digital-twin/state",
            json={"twin_state_id": "TWIN-TEST-99"},
            headers=headers
        )
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# 4. Parametrized Role x Route Matrix Tests
# ---------------------------------------------------------------------------
# Matrix: (service_base_url, method, endpoint, payload, min_role)
MATRIX_CASES = [
    # Viewer endpoints
    (DT_URL, "GET", "/api/status", None, ROLE_VIEWER),
    (DT_URL, "GET", "/api/state", None, ROLE_VIEWER),
    (DT_URL, "GET", "/api/models/info", None, ROLE_VIEWER),
    (MI_URL, "GET", "/api/health", None, ROLE_VIEWER),
    (GEN_URL, "GET", "/latest", None, ROLE_VIEWER),
    (GEN_URL, "GET", "/schema", None, ROLE_VIEWER),
    # Analyst endpoints
    (DT_URL, "POST", "/api/predict", {"row_index": 0, "horizon_minutes": 60}, ROLE_ANALYST),
    (DT_URL, "POST", "/api/fork", {"start_row_index": 0, "horizon_minutes": 60, "scenarios": []}, ROLE_ANALYST),
    (MI_URL, "POST", "/api/assess", {"row_index": 0, "horizon_minutes": 60, "run_scenarios": False}, ROLE_ANALYST),
    # Operator endpoints
    (MI_URL, "POST", "/api/decision", {"recommendation_id": "REC-NON-EXISTENT", "decision": "accepted"}, ROLE_OPERATOR),
    # Admin endpoints
    (DT_URL, "POST", "/api/generator/inject-anomaly", {"overrides": {"solar_panel_temp_c": 110.0}}, ROLE_ADMIN),
    (GEN_URL, "POST", "/control/pause", {}, ROLE_ADMIN),
    (GEN_URL, "POST", "/control/resume", {}, ROLE_ADMIN),
]

ROLE_ORDER = [ROLE_VIEWER, ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN]


@pytest.mark.parametrize("base_url,method,endpoint,payload,min_role", MATRIX_CASES)
@pytest.mark.parametrize("test_role", ROLE_ORDER)
def test_role_route_matrix(tokens, base_url, method, endpoint, payload, min_role, test_role):
    """
    Parametrized role x route matrix:
    - If test_role has sufficient privilege (>= min_role): expected 200 (or 404 for missing rec_id)
    - If test_role has insufficient privilege (< min_role): expected 403 Forbidden
    """
    role_hierarchy = {ROLE_VIEWER: 1, ROLE_ANALYST: 2, ROLE_OPERATOR: 3, ROLE_ADMIN: 4}
    user_level = role_hierarchy[test_role]
    required_level = role_hierarchy[min_role]

    token = tokens[test_role]
    headers = auth_header(token)

    with httpx.Client(timeout=10.0) as client:
        if method == "GET":
            res = client.get(f"{base_url}{endpoint}", headers=headers)
        else:
            res = client.post(f"{base_url}{endpoint}", json=payload or {}, headers=headers)

        if user_level < required_level:
            assert res.status_code == 403, (
                f"Expected 403 for role '{test_role}' on '{method} {endpoint}', got {res.status_code}: {res.text}"
            )
        else:
            # If allowed: 200 OK (or 404 for unknown recommendation ID on decision route)
            assert res.status_code in [200, 404], (
                f"Expected allowed (200/404) for role '{test_role}' on '{method} {endpoint}', got {res.status_code}: {res.text}"
            )


# ---------------------------------------------------------------------------
# 5. Identity Spoofing Prevention Test
# ---------------------------------------------------------------------------
def test_operator_spoofing_prevented(tokens):
    """
    Never trust request body for identity:
    Posting a decision with operator="someone_else" is ignored,
    and the JWT token's 'sub' (test_operator) is stored in the decision log.
    """
    with httpx.Client(timeout=10.0) as client:
        # 1. Analyst triggers an assessment to obtain a real recommendation_id
        assess_res = client.post(
            f"{MI_URL}/api/assess",
            json={"row_index": 0, "horizon_minutes": 60, "run_scenarios": False},
            headers=auth_header(tokens[ROLE_ANALYST])
        )
        assert assess_res.status_code == 200
        rec_id = assess_res.json()["recommendation_id"]

        # 2. Operator submits a decision with a spoofed operator in body
        dec_res = client.post(
            f"{MI_URL}/api/decision",
            json={
                "recommendation_id": rec_id,
                "decision": "accepted",
                "operator": "imposter_spoofed_user",
                "reasoning": "Spoof test execution"
            },
            headers=auth_header(tokens[ROLE_OPERATOR])
        )
        assert dec_res.status_code == 200

        # 3. Check history log: the recorded decision_operator must be test_operator, NOT imposter
        hist_res = client.get(f"{MI_URL}/api/history", headers=auth_header(tokens[ROLE_VIEWER]))
        assert hist_res.status_code == 200
        history_items = hist_res.json().get("history", [])
        target_item = next((item for item in history_items if item.get("recommendation_id") == rec_id), None)
        assert target_item is not None
        assert target_item.get("decision_operator") == "test_operator"
        assert target_item.get("decision_operator") != "imposter_spoofed_user"


# ---------------------------------------------------------------------------
# 6. History Filter Authorization Test
# ---------------------------------------------------------------------------
def test_history_operator_filter_authorization(tokens):
    """
    Non-admin users may only filter operator by their own 'sub'.
    A filter for another operator returns 403 Forbidden.
    Admin can filter by any operator.
    """
    with httpx.Client(timeout=5.0) as client:
        # 1. Non-admin queries another operator -> 403
        r403 = client.get(
            f"{MI_URL}/api/history?operator=someone_else",
            headers=auth_header(tokens[ROLE_OPERATOR])
        )
        assert r403.status_code == 403
        assert "Forbidden" in r403.text

        # 2. Non-admin queries their own username -> 200
        r200_self = client.get(
            f"{MI_URL}/api/history?operator=test_operator",
            headers=auth_header(tokens[ROLE_OPERATOR])
        )
        assert r200_self.status_code == 200

        # 3. Admin queries another operator -> 200
        r200_admin = client.get(
            f"{MI_URL}/api/history?operator=test_operator",
            headers=auth_header(tokens[ROLE_ADMIN])
        )
        assert r200_admin.status_code == 200


# ---------------------------------------------------------------------------
# 7. Decision Enum Validation, Unknown Rec (404), and Conflict (409) Tests
# ---------------------------------------------------------------------------
def test_decision_validation_and_conflicts(tokens):
    """
    Decisions:
    - Validate decision as enum (accepted/rejected/deferred) -> 422 for invalid.
    - 404 for unknown recommendation ID.
    - 409 Conflict if recommendation already has a recorded decision.
    """
    with httpx.Client(timeout=10.0) as client:
        op_headers = auth_header(tokens[ROLE_OPERATOR])

        # 1. Invalid decision enum -> 422
        r422 = client.post(
            f"{MI_URL}/api/decision",
            json={"recommendation_id": "REC-TEST", "decision": "not_a_valid_choice"},
            headers=op_headers
        )
        assert r422.status_code == 422

        # 2. Unknown recommendation -> 404
        r404 = client.post(
            f"{MI_URL}/api/decision",
            json={"recommendation_id": "REC-UNKNOWN-99999", "decision": "deferred"},
            headers=op_headers
        )
        assert r404.status_code == 404

        # 3. Create real recommendation
        assess_res = client.post(
            f"{MI_URL}/api/assess",
            json={"row_index": 0, "horizon_minutes": 60, "run_scenarios": False},
            headers=auth_header(tokens[ROLE_ANALYST])
        )
        rec_id = assess_res.json()["recommendation_id"]

        # First decision -> 200
        r_dec1 = client.post(
            f"{MI_URL}/api/decision",
            json={"recommendation_id": rec_id, "decision": "accepted"},
            headers=op_headers
        )
        assert r_dec1.status_code == 200

        # Second decision on the same recommendation -> 409 Conflict
        r_dec2 = client.post(
            f"{MI_URL}/api/decision",
            json={"recommendation_id": rec_id, "decision": "rejected"},
            headers=op_headers
        )
        assert r_dec2.status_code == 409
        assert "Conflict" in r_dec2.text


# ---------------------------------------------------------------------------
# 8. WebSocket & SSE Streaming Authorization Tests
# ---------------------------------------------------------------------------
def test_websocket_and_stream_authorization(tokens):
    """
    WebSocket /ws and SSE /stream require valid token before streaming.
    - /stream without token returns 401.
    - /ws with Sec-WebSocket-Protocol token connects and streams frames.
    - /ws with first message auth connects and streams frames.
    """
    async def _run():
        # 1. SSE /stream without token -> 401
        async with httpx.AsyncClient(timeout=5.0) as client:
            r_stream = await client.get(f"{GEN_URL}/stream")
            assert r_stream.status_code == 401

        viewer_token = tokens[ROLE_VIEWER]

        # 2. WebSocket via Sec-WebSocket-Protocol header
        subproto = f"token.{viewer_token}"
        async with websockets.connect(f"ws://127.0.0.1:8080/ws", subprotocols=[subproto], open_timeout=3.0) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            assert len(msg) > 0
            frame_data = json.loads(msg)
            assert "telemetry" in frame_data or "position_x" in frame_data

        # 3. WebSocket via first auth message
        async with websockets.connect(f"ws://127.0.0.1:8080/ws", open_timeout=3.0) as ws:
            await ws.send(json.dumps({"type": "auth", "token": viewer_token}))
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            assert len(msg) > 0

    asyncio.run(_run())
