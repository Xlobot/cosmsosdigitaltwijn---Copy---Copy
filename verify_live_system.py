import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def request_json(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"detail": err_body}

print("=" * 60)
print(" VERIFYING LIVE COSMOS DIGITAL TWIN & RBAC SYSTEM")
print("=" * 60)

# 1. Admin Login
status, admin_data = request_json(f"{BASE}/api/auth/login", method="POST", data={
    "username": "admin",
    "password": "CosmosFlightOps2026!"
})
print(f"[1] Admin Login -> HTTP {status}")
assert status == 200
admin_token = admin_data["access_token"]
admin_perms = admin_data["user"]["permissions"]
print(f"    Logged in as: {admin_data['user']['username']} (Role: {admin_data['user']['role']})")
print(f"    Permissions: {admin_perms} (Has wildcard: {'*' in admin_perms})")
assert "*" in admin_perms

# 2. System Status (Authenticated)
status, data = request_json(f"{BASE}/api/status", token=admin_token)
print(f"\n[2] /api/status -> HTTP {status}")
assert status == 200
print(f"    Status: {data.get('status')}, Generator: {data.get('generator', {}).get('status')}")

# 3. Admin can list all users
status, users_data = request_json(f"{BASE}/api/auth/users", token=admin_token)
print(f"\n[3] Admin List Users -> HTTP {status}")
assert status == 200
print(f"    Found {len(users_data.get('users', []))} registered user accounts.")

# 4. Admin creates a new restricted operator
test_username = "flight_observer_1"
# Delete if exists
request_json(f"{BASE}/api/auth/users/{test_username}", method="DELETE", token=admin_token)

status, new_user_res = request_json(f"{BASE}/api/auth/users", method="POST", data={
    "username": test_username,
    "password": "ObserverSecret2026!",
    "role": "operator",
    "permissions": ["telemetry:read"]  # Only telemetry, no predict, no fork, no inject
}, token=admin_token)
print(f"\n[4] Admin Adds New User '{test_username}' with permissions ['telemetry:read'] -> HTTP {status}")
assert status == 200
print(f"    User created: {new_user_res.get('user', {}).get('username')} with permissions: {new_user_res.get('user', {}).get('permissions')}")

# 5. New restricted operator logs in
status, op_data = request_json(f"{BASE}/api/auth/login", method="POST", data={
    "username": test_username,
    "password": "ObserverSecret2026!"
})
print(f"\n[5] Restricted Operator Login -> HTTP {status}")
assert status == 200
op_token = op_data["access_token"]
op_perms = op_data["user"]["permissions"]
print(f"    Logged in as: {op_data['user']['username']}, Permissions: {op_perms}")

# 6. Restricted operator attempts to create another user -> MUST FAIL 403 Forbidden
status, rogue_res = request_json(f"{BASE}/api/auth/users", method="POST", data={
    "username": "rogue_op",
    "password": "Password123!",
    "role": "admin"
}, token=op_token)
print(f"\n[6] Non-Admin attempts to add new user -> HTTP {status} (Expected 403 Forbidden)")
assert status == 403
print(f"    Detail: {rogue_res.get('detail')}")

# 7. Restricted operator attempts unpermitted action (POST /api/predict) -> MUST FAIL 403 Forbidden
status, pred_res = request_json(f"{BASE}/api/predict", method="POST", data={
    "start_row_index": 0,
    "horizon_minutes": 15
}, token=op_token)
print(f"\n[7] Operator without 'predict:run' tries to run prediction -> HTTP {status} (Expected 403 Forbidden)")
assert status == 403
print(f"    Detail: {pred_res.get('detail')}")

# 8. Admin executes prediction -> SUCCEEDS 200 OK (Admin has access to everything)
status, admin_pred = request_json(f"{BASE}/api/predict", method="POST", data={
    "start_row_index": 0,
    "horizon_minutes": 15
}, token=admin_token)
print(f"\n[8] Admin executes prediction (Wildcard access to everything) -> HTTP {status}")
assert status == 200
print(f"    Success: Predicted nominal trajectory points: {len(admin_pred.get('nominal_prediction', {}).get('trajectory', []))}")

# 9. Mission Intelligence Proxy Health & Assessment
status, mi_health = request_json(f"{BASE}/api/mi/health", token=admin_token)
print(f"\n[9] Mission Intelligence Gateway Health -> HTTP {status}")
assert status == 200
print(f"    MI Status: {mi_health.get('mission_intelligence_status')}")

# 10. Mission Intelligence History
status, mi_hist = request_json(f"{BASE}/api/mi/history", token=admin_token)
print(f"\n[10] Mission Intelligence History -> HTTP {status}")
assert status == 200
print(f"    MI Total Logged Decisions: {mi_hist.get('total')}")

print("\n" + "=" * 60)
print(" ALL 10 VERIFICATION CHECKS PASSED WITH FLYING COLORS! ")
print("=" * 60)
