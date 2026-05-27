"""
Smoke tests for CRMS backend (non-destructive).
This script monkeypatches `queries` and `assignment_algorithm` functions to avoid a real DB,
then uses Flask test_client to call several endpoints and prints results.
"""
import sys, os, traceback, json
# Ensure Backend is importable
sys.path.insert(0, os.path.join(os.getcwd(), 'Backend'))

try:
    import app as backend_app
    from app import app as flask_app
    import queries
    import assignment_algorithm
except Exception:
    traceback.print_exc()
    raise

# --- Monkeypatch lightweight stubs ---

def _stub_get_public_stats():
    return {
        "total_cases": 0,
        "active_cases": 0,
        "solved_cases": 0,
    }

queries.get_public_stats = _stub_get_public_stats
queries.get_public_complaints = lambda status=None: []
queries.get_case_by_id = lambda cid: {"case_id": cid, "officer_ids": [1, 2]}

def _get_officer_by_id(oid):
    mapping = {
        1: {"officer_id": 1, "name": "Inspector A", "rank": "Inspector", "role": "inspector"},
        2: {"officer_id": 2, "name": "Constable B", "rank": "Constable", "role": "P1"},
        99: {"officer_id": 99, "name": "Admin", "rank": "Inspector", "role": "admin"},
    }
    return mapping.get(oid)

queries.get_officer_by_id = _get_officer_by_id
queries.get_highest_ranked_officer_on_case = lambda case_id: _get_officer_by_id(1)

assignment_algorithm.process_pending_complaints = lambda: {"processed": 0, "errors": 0, "details": []}
assignment_algorithm.approve_recommendation = lambda rec_id, admin_officer_id, final_officer_ids=None: 123
assignment_algorithm.AUTO_APPROVE_SCHEDULER = True

# Test client
client = flask_app.test_client()

endpoints = [
    ("GET", "/"),
    ("GET", "/stats"),
    ("GET", "/assignments/pending"),
    ("POST", "/assignments/process"),
    ("GET", "/cases/1/officers"),
    ("GET", "/cases/1/highest-ranked"),
]

# Admin approve endpoint requires header
admin_approve = ("POST", "/admin/recommendations/1/approve")

results = []

print("Running smoke tests...")
for method, path in endpoints:
    try:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path)
        try:
            data = resp.get_json()
        except Exception:
            data = resp.data.decode('utf-8')[:200]
        results.append((path, resp.status_code, data))
        print(path, resp.status_code, type(data))
    except Exception as e:
        print(path, "EXCEPTION:")
        traceback.print_exc()

# Test admin approve with header
try:
    headers = {"X-Officer-Id": "99"}
    resp = client.post(admin_approve[1], headers=headers, json={})
    try:
        data = resp.get_json()
    except Exception:
        data = resp.data.decode('utf-8')[:200]
    print(admin_approve[1], resp.status_code, type(data))
    results.append((admin_approve[1], resp.status_code, data))
except Exception:
    traceback.print_exc()

print('\nSummary:')
for path, status, data in results:
    print(f"{path} -> {status} -> {json.dumps(data) if not isinstance(data, str) else data}")

# Exit non-zero if any endpoint returned 5xx
any_5xx = any(500 <= s < 600 for _, s, _ in results)
if any_5xx:
    print('\nSome endpoints returned 5xx')
    sys.exit(2)

print('\nAll smoke tests completed')
