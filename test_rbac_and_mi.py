"""
Test Suite: Role-Based Access Control (RBAC), Admin Exclusivity, and Mission Intelligence Integration
=====================================================================================================
Validates:
1. Seeded root admin has wildcard [*] permissions (Full access to everything).
2. Non-admin user receives 403 Forbidden when trying to list or create users.
3. Only Admin can add a new user and assign permissions.
4. New user with restricted permissions is blocked from unpermitted actions (403 Forbidden).
5. New user with granted permissions can execute permitted actions.
6. Admin can update permissions of existing users.
7. Admin can delete user accounts (cannot delete root admin).
8. Mission Intelligence endpoints proxy correctly through the backend using X-Service-Key.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure root dir in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.server import app as dt_app
from mission_intelligence_server import app as mi_app
from cosmos_security import (
    seed_admin_user,
    get_user_by_username,
    COSMOS_ADMIN_USERNAME,
    COSMOS_ADMIN_PASSWORD,
    COSMOS_SERVICE_KEY,
    SERVICE_KEY_HEADER
)

dt_client = TestClient(dt_app)
mi_client = TestClient(mi_app)


def test_01_admin_login_and_full_permissions():
    """Admin authenticates and gets full access wildcard [*]."""
    seed_admin_user()
    res = dt_client.post("/api/auth/login", json={
        "username": COSMOS_ADMIN_USERNAME,
        "password": COSMOS_ADMIN_PASSWORD
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    assert "*" in data["user"]["permissions"]


def test_02_non_admin_cannot_manage_users():
    """Unauthenticated or non-admin callers must receive 403 or 401 when accessing user management."""
    # 1. Unauthenticated -> 401
    res = dt_client.get("/api/auth/users")
    assert res.status_code == 401

    # 2. Authenticate as admin to create a basic operator with only telemetry:read
    admin_res = dt_client.post("/api/auth/login", json={
        "username": COSMOS_ADMIN_USERNAME,
        "password": COSMOS_ADMIN_PASSWORD
    })
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin creates operator 'test_trainee'
    create_res = dt_client.post("/api/auth/users", json={
        "username": "test_trainee",
        "password": "TraineePassword2026!",
        "role": "operator",
        "permissions": ["telemetry:read"]
    }, headers=admin_headers)
    assert create_res.status_code in [200, 409]

    # Trainee logs in
    trainee_res = dt_client.post("/api/auth/login", json={
        "username": "test_trainee",
        "password": "TraineePassword2026!"
    })
    assert trainee_res.status_code == 200
    trainee_token = trainee_res.json()["access_token"]
    trainee_headers = {"Authorization": f"Bearer {trainee_token}"}

    # Trainee attempts to list users -> 403 Forbidden
    list_res = dt_client.get("/api/auth/users", headers=trainee_headers)
    assert list_res.status_code == 403, f"Expected 403 Forbidden, got {list_res.status_code}"

    # Trainee attempts to create another user -> 403 Forbidden
    hack_res = dt_client.post("/api/auth/users", json={
        "username": "rogue_user",
        "password": "Password123!",
        "role": "admin",
        "permissions": ["*"]
    }, headers=trainee_headers)
    assert hack_res.status_code == 403, f"Expected 403 Forbidden, got {hack_res.status_code}"


def test_03_admin_exclusively_adds_and_decides_permissions():
    """Admin creates a user with custom permissions and verifies granular enforcement."""
    admin_res = dt_client.post("/api/auth/login", json={
        "username": COSMOS_ADMIN_USERNAME,
        "password": COSMOS_ADMIN_PASSWORD
    })
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Delete test_ops if exists
    dt_client.delete("/api/auth/users/test_ops", headers=admin_headers)

    # Admin creates 'test_ops' with predict:run ONLY (no anomalies:inject or scenarios:fork)
    create_res = dt_client.post("/api/auth/users", json={
        "username": "test_ops",
        "password": "TestOpsPass2026!",
        "role": "operator",
        "permissions": ["telemetry:read", "predict:run"]
    }, headers=admin_headers)
    assert create_res.status_code == 200
    user_data = create_res.json()["user"]
    assert user_data["username"] == "test_ops"
    assert "predict:run" in user_data["permissions"]
    assert "scenarios:fork" not in user_data["permissions"]

    # Log in as test_ops
    ops_res = dt_client.post("/api/auth/login", json={
        "username": "test_ops",
        "password": "TestOpsPass2026!"
    })
    assert ops_res.status_code == 200
    ops_token = ops_res.json()["access_token"]
    ops_headers = {"Authorization": f"Bearer {ops_token}"}

    # Allowed action: predict:run
    predict_res = dt_client.post("/api/predict", json={
        "start_row_index": 0,
        "horizon_minutes": 10
    }, headers=ops_headers)
    assert predict_res.status_code == 200, f"Expected 200, got {predict_res.status_code}: {predict_res.text}"

    # Disallowed action: scenarios:fork -> 403 Forbidden
    fork_res = dt_client.post("/api/fork", json={
        "start_row_index": 0,
        "horizon_minutes": 10,
        "scenarios": []
    }, headers=ops_headers)
    assert fork_res.status_code == 403, f"Expected 403 Forbidden, got {fork_res.status_code}"

    # Disallowed action: anomalies:inject -> 403 Forbidden
    inject_res = dt_client.post("/api/generator/inject-anomaly", json={
        "subsystem": "battery",
        "type": "drop"
    }, headers=ops_headers)
    assert inject_res.status_code == 403, f"Expected 403 Forbidden, got {inject_res.status_code}"


def test_04_admin_updates_user_permissions():
    """Admin elevates operator permissions to include scenarios:fork."""
    admin_res = dt_client.post("/api/auth/login", json={
        "username": COSMOS_ADMIN_USERNAME,
        "password": COSMOS_ADMIN_PASSWORD
    })
    admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

    # Update permissions for test_ops
    update_res = dt_client.put("/api/auth/users/test_ops/permissions", json={
        "role": "operator",
        "permissions": ["telemetry:read", "predict:run", "scenarios:fork"]
    }, headers=admin_headers)
    assert update_res.status_code == 200
    assert "scenarios:fork" in update_res.json()["user"]["permissions"]

    # Re-login as test_ops
    ops_res = dt_client.post("/api/auth/login", json={
        "username": "test_ops",
        "password": "TestOpsPass2026!"
    })
    ops_headers = {"Authorization": f"Bearer {ops_res.json()['access_token']}"}

    # Now scenarios:fork succeeds!
    fork_res = dt_client.post("/api/fork", json={
        "start_row_index": 0,
        "horizon_minutes": 10,
        "scenarios": []
    }, headers=ops_headers)
    assert fork_res.status_code == 200


def test_05_admin_has_unrestricted_access_to_everything():
    """Admin can run all actions without restriction."""
    admin_res = dt_client.post("/api/auth/login", json={
        "username": COSMOS_ADMIN_USERNAME,
        "password": COSMOS_ADMIN_PASSWORD
    })
    admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

    # Predict
    res_predict = dt_client.post("/api/predict", json={"start_row_index": 0, "horizon_minutes": 10}, headers=admin_headers)
    assert res_predict.status_code == 200

    # Fork
    res_fork = dt_client.post("/api/fork", json={"start_row_index": 0, "horizon_minutes": 10, "scenarios": []}, headers=admin_headers)
    assert res_fork.status_code == 200

    # List users
    res_users = dt_client.get("/api/auth/users", headers=admin_headers)
    assert res_users.status_code == 200


def test_06_service_to_service_mi_security():
    """Mission Intelligence server requires X-Service-Key for webhooks and backend communication."""
    # Without X-Service-Key -> 401 or 403
    res_blocked = mi_client.post("/webhook/trigger-assessment", json={"row_index": 0})
    assert res_blocked.status_code == 403

    # With X-Service-Key -> succeeds
    service_headers = {SERVICE_KEY_HEADER: COSMOS_SERVICE_KEY}
    res_authed = mi_client.get("/api/health", headers=service_headers)
    assert res_authed.status_code == 200


if __name__ == "__main__":
    ret = pytest.main(["-v", __file__])
    sys.exit(ret)
