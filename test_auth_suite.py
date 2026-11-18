import urllib.request
import urllib.error
import json
import sqlite3
import jwt

BASE_DT = 'http://127.0.0.1:8000'
BASE_MI = 'http://127.0.0.1:8001'
BASE_GEN = 'http://127.0.0.1:8080'

with open('.env') as f:
    env = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#'))

SERVICE_KEY = env['COSMOS_SERVICE_KEY']
JWT_SECRET = env['JWT_SECRET_KEY']

print('=' * 60)
print(' RUNNING COMPREHENSIVE COSMOS AUTHENTICATION TEST SUITE')
print('=' * 60)

# 1. Test invalid login
print('\n[1] Testing invalid login credentials...')
try:
    req = urllib.request.Request(
        f'{BASE_DT}/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': 'WrongPassword123'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)
    assert False, 'Invalid login should have failed!'
except urllib.error.HTTPError as e:
    assert e.code == 401, f'Expected 401, got {e.code}'
    print('    PASS: Rejected invalid password with HTTP 401.')

# 2. Test valid login with seeded admin
print('\n[2] Testing valid admin login via POST /api/auth/login...')
req = urllib.request.Request(
    f'{BASE_DT}/api/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'CosmosFlightOps2026!'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    token = data['access_token']
    expires_in = data['expires_in']
    assert token, 'Token missing!'
    assert expires_in == 900, f'Expected 900s (15 min), got {expires_in}'
    print(f'    PASS: Login succeeded! Token type: {data["token_type"]}, expires_in: {expires_in}s (15 min).')

# 3. Verify JWT claims & expiration
print('\n[3] Verifying PyJWT claims & 15-min lifespan...')
decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
assert decoded['sub'] == 'admin', 'Subject mismatch'
assert decoded['role'] == 'admin', 'Role mismatch'
delta = decoded['exp'] - decoded['iat']
assert delta == 900, f'Expected 900s delta, got {delta}'
print(f'    PASS: JWT claims validated! sub: {decoded["sub"]}, role: {decoded["role"]}, lifespan: {delta}s.')

# 4. Test protected endpoint without token
print('\n[4] Testing protected Digital Twin endpoint (/api/state) without auth...')
try:
    urllib.request.urlopen(f'{BASE_DT}/api/state')
    assert False, 'Unauthenticated request should have failed!'
except urllib.error.HTTPError as e:
    assert e.code == 401, f'Expected 401, got {e.code}'
    print('    PASS: Blocked unauthenticated access with HTTP 401.')

# 5. Test protected endpoint with user JWT token
print('\n[5] Testing protected Digital Twin endpoint (/api/state) WITH user JWT token...')
req = urllib.request.Request(
    f'{BASE_DT}/api/state?index=0',
    headers={'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req) as resp:
    state = json.loads(resp.read().decode())
    assert state.get('satellite_id') == 'ISS-25544', 'State invalid'
    print(f'    PASS: Access granted with Bearer token! Satellite: {state["satellite_id"]}, Health: {state["health_score"]}.')

# 6. Test Generator service without X-Service-Key
print('\n[6] Testing Generator (/rows) without X-Service-Key...')
try:
    urllib.request.urlopen(f'{BASE_GEN}/rows?since=0&limit=5')
    assert False, 'Unauthenticated generator call should have failed!'
except urllib.error.HTTPError as e:
    assert e.code == 403, f'Expected 403, got {e.code}'
    print('    PASS: Blocked call without X-Service-Key with HTTP 403 Forbidden.')

# 7. Test Generator service WITH X-Service-Key
print('\n[7] Testing Generator (/rows) WITH X-Service-Key header...')
req = urllib.request.Request(
    f'{BASE_GEN}/rows?since=0&limit=5',
    headers={'X-Service-Key': SERVICE_KEY}
)
with urllib.request.urlopen(req) as resp:
    rows = json.loads(resp.read().decode())
    print(f'    PASS: Access granted with X-Service-Key! Retrieved {len(rows)} live rows from Generator.')

# 8. Test Mission Intelligence webhook without X-Service-Key
print('\n[8] Testing MI webhook (/webhook/trigger-assessment) without X-Service-Key...')
try:
    req = urllib.request.Request(
        f'{BASE_MI}/webhook/trigger-assessment',
        data=json.dumps({'row_index': 0}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)
    assert False, 'Unauthenticated webhook should have failed!'
except urllib.error.HTTPError as e:
    assert e.code == 403, f'Expected 403, got {e.code}'
    print('    PASS: Blocked webhook without X-Service-Key with HTTP 403 Forbidden.')

# 9. Test Mission Intelligence webhook WITH X-Service-Key
print('\n[9] Testing MI webhook (/webhook/trigger-assessment) WITH X-Service-Key...')
req = urllib.request.Request(
    f'{BASE_MI}/webhook/trigger-assessment',
    data=json.dumps({'row_index': 0, 'horizon_minutes': 30, 'run_scenarios': False}).encode(),
    headers={'Content-Type': 'application/json', 'X-Service-Key': SERVICE_KEY}
)
with urllib.request.urlopen(req) as resp:
    assessment = json.loads(resp.read().decode())
    print(f'    PASS: Webhook succeeded with X-Service-Key! Assessment timestamp: {assessment.get("assessment_timestamp", "OK")}.')

# 10. Verify SQLite database storage & Argon2 hash
print('\n[10] Verifying SQLite database and Argon2 password hashing (no plaintext)...')
conn = sqlite3.connect('cosmos_users.db')
c = conn.cursor()
c.execute('SELECT username, hashed_password, role, created_at FROM users WHERE username = "admin"')
row = c.fetchone()
conn.close()
assert row is not None, 'Admin not in SQLite!'
u, h, r, dt = row
assert 'CosmosFlightOps2026!' not in h, 'Plaintext password detected!'
assert h.startswith('$argon2id$'), f'Expected Argon2id hash, got {h[:20]}'
print(f'    PASS: User "{u}" stored in SQLite with Argon2id hash: {h[:35]}... (no plaintext).')

print('\n' + '=' * 60)
print(' ALL 10 AUTHENTICATION & SECURITY TESTS PASSED!')
print('=' * 60)
