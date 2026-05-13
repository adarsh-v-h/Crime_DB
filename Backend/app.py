# ─── CRMS Flask API ────────────────────────────────────────────────────────────
# Entry point. Defines every route, validates inputs, and returns JSON.
# All SQL lives in queries.py. All credentials live in config.py.
#
# Run:
#   python app.py
#
# Server starts at http://localhost:5000

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

import config
from db_connection import init_pool
import queries

# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGIN)


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

VALID_STATUSES       = {"Active", "Solved", "Closed"}
VALID_CRIME_TYPES    = {"Cyber Fraud", "Theft", "Assault", "Fraud", "Other"}
VALID_COMPLAINT_MODES = {"Online", "Offline"}


def _err(msg, code=400):
    return jsonify({"success": False, "error": msg}), code


def _ok(data=None, **kwargs):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(kwargs)
    return jsonify(body), 200


def _format_case_id(raw_id: int) -> str:
    """Converts integer PK to BLR-XXX display format."""
    return f"BLR-{str(raw_id).zfill(3)}"


def _enrich_cases(case_list):
    """
    Adds the display case_id string (BLR-XXX) alongside the integer case_id.
    The frontend uses BLR-XXX as the display label; the integer is the real PK.
    """
    for c in case_list:
        c["case_id_display"] = _format_case_id(c["case_id"])
    return case_list


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Quick ping to confirm the server is alive."""
    return _ok(message="CRMS API is operational")


# ──────────────────────────────────────────────────────────────────────────────
# CASES  —  /cases
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/cases", methods=["GET"])
def get_cases():
    """
    GET /cases
    Optional query params: status, crime_type, location, search
    Returns all matching cases with officer_ids attached.

    Example:
      GET /cases?status=Active&crime_type=Cyber+Fraud
    """
    status     = request.args.get("status")
    crime_type = request.args.get("crime_type")
    location   = request.args.get("location")
    search     = request.args.get("search")

    try:
        cases = queries.get_all_cases(status, crime_type, location, search)
        return _ok(_enrich_cases(cases))
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/cases/<int:case_id>", methods=["GET"])
def get_case(case_id):
    """
    GET /cases/<case_id>
    Returns a single case with assigned officer IDs.
    """
    try:
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
        case["case_id_display"] = _format_case_id(case_id)
        return _ok(case)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/cases", methods=["POST"])
def add_case():
    """
    POST /cases
    Body (JSON):
      title*         — string
      description    — string
      crime_type*    — Cyber Fraud | Theft | Assault | Fraud | Other
      status         — Active (default) | Solved | Closed
      location*      — string
      complaint_mode — Online (default) | Offline

    Returns: { success, case_id, case_id_display }
    """
    body = request.get_json(silent=True) or {}

    title          = (body.get("title") or "").strip()
    description    = (body.get("description") or "").strip()
    crime_type     = (body.get("crime_type") or "").strip()
    status         = (body.get("status") or "Active").strip()
    location       = (body.get("location") or "").strip()
    complaint_mode = (body.get("complaint_mode") or "Online").strip()

    # Validation
    if not title:
        return _err("title is required")
    if not crime_type:
        return _err("crime_type is required")
    if not location:
        return _err("location is required")
    if status not in VALID_STATUSES:
        return _err(f"status must be one of: {', '.join(VALID_STATUSES)}")
    if crime_type not in VALID_CRIME_TYPES:
        return _err(f"crime_type must be one of: {', '.join(VALID_CRIME_TYPES)}")
    if complaint_mode not in VALID_COMPLAINT_MODES:
        return _err(f"complaint_mode must be Online or Offline")

    try:
        new_id = queries.insert_case(title, description, crime_type, status, location, complaint_mode)
        return jsonify({
            "success":        True,
            "case_id":        new_id,
            "case_id_display": _format_case_id(new_id),
        }), 201
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/cases/<int:case_id>", methods=["PATCH"])
def update_case(case_id):
    """
    PATCH /cases/<case_id>
    Body (JSON): any subset of { title, description, crime_type, status, location, complaint_mode }

    The frontend uses this to update case status from the detail modal.

    Example body: { "status": "Solved" }
    """
    body = request.get_json(silent=True) or {}

    # Validate enum fields if provided
    if "status" in body and body["status"] not in VALID_STATUSES:
        return _err(f"status must be one of: {', '.join(VALID_STATUSES)}")
    if "crime_type" in body and body["crime_type"] not in VALID_CRIME_TYPES:
        return _err(f"crime_type must be one of: {', '.join(VALID_CRIME_TYPES)}")
    if "complaint_mode" in body and body["complaint_mode"] not in VALID_COMPLAINT_MODES:
        return _err("complaint_mode must be Online or Offline")

    try:
        rows = queries.update_case(case_id, body)
        if rows == 0:
            return _err(f"Case {case_id} not found", 404)
        return _ok(updated_case_id=case_id)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/cases/<int:case_id>", methods=["DELETE"])
def delete_case(case_id):
    """
    DELETE /cases/<case_id>
    Hard deletes the case. P1 role only (enforced client-side; add auth middleware for production).
    Recommended: use PATCH to set status=Closed instead.
    """
    try:
        rows = queries.delete_case(case_id)
        if rows == 0:
            return _err(f"Case {case_id} not found", 404)
        return _ok(deleted_case_id=case_id)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# CASES + OFFICERS detail  —  /cases/<id>/officers
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/cases/<int:case_id>/officers", methods=["GET"])
def get_case_officers(case_id):
    """
    GET /cases/<case_id>/officers
    Returns the full case object plus an 'officers' array (not just IDs).
    Used by the case detail modal to show name + rank inline.
    """
    try:
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)

        # Hydrate officer objects
        officers = []
        for oid in case.get("officer_ids", []):
            o = queries.get_officer_by_id(oid)
            if o:
                officers.append(o)

        case["officers"] = officers
        case["case_id_display"] = _format_case_id(case_id)
        return _ok(case)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# OFFICERS  —  /officers
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/officers", methods=["GET"])
def get_officers():
    """
    GET /officers
    Returns all officers with active_cases and solved_cases counts computed via JOINs.
    """
    try:
        officers = queries.get_all_officers()
        return _ok(officers)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/officers", methods=["POST"])
def add_officer():
    """
    POST /officers
    Body: { name*, rank* }
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    rank = (body.get("rank") or "").strip()

    if not name:
        return _err("name is required")
    if not rank:
        return _err("rank is required")

    try:
        new_id = queries.insert_officer(name, rank)
        return jsonify({"success": True, "officer_id": new_id}), 201
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# ASSIGNMENTS  —  /case-officer
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/case-officer", methods=["GET"])
def get_assignments():
    """
    GET /case-officer
    Returns every case–officer pairing as a flat list for the Assignments view.
    Each row: { case_id, case_title, crime_type, status, location, officer_id, officer_name, officer_rank }
    """
    try:
        return _ok(queries.get_all_assignments())
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/case-officer", methods=["POST"])
def assign_officer():
    """
    POST /case-officer
    Body: { case_id*, officer_id* }
    Assigns an officer to a case.
    """
    body       = request.get_json(silent=True) or {}
    case_id    = body.get("case_id")
    officer_id = body.get("officer_id")

    if case_id is None:
        return _err("case_id is required")
    if officer_id is None:
        return _err("officer_id is required")

    try:
        # Verify both exist
        if not queries.get_case_by_id(int(case_id)):
            return _err(f"Case {case_id} does not exist", 404)
        if not queries.get_officer_by_id(int(officer_id)):
            return _err(f"Officer {officer_id} does not exist", 404)

        rows = queries.assign_officer(int(case_id), int(officer_id))
        return _ok(assigned=rows > 0)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/case-officer", methods=["DELETE"])
def unassign_officer():
    """
    DELETE /case-officer
    Body: { case_id*, officer_id* }
    Removes a case–officer assignment.
    """
    body       = request.get_json(silent=True) or {}
    case_id    = body.get("case_id")
    officer_id = body.get("officer_id")

    if case_id is None:
        return _err("case_id is required")
    if officer_id is None:
        return _err("officer_id is required")

    try:
        rows = queries.unassign_officer(int(case_id), int(officer_id))
        if rows == 0:
            return _err("Assignment not found", 404)
        return _ok()
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# ANALYTICS  —  /analytics
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/analytics", methods=["GET"])
def get_analytics():
    """
    GET /analytics
    Returns aggregated data for all four Analytics charts:
      crime_distribution, status_distribution, monthly_trends, location_distribution
    """
    try:
        return _ok(queries.get_analytics())
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC PORTAL  —  /public/complaint  /public/access-request
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/public/complaint", methods=["POST"])
def public_complaint():
    """
    POST /public/complaint
    Called from the public portal File Complaint form.
    No authentication required.
    Body: { name*, contact*, email, crime_type*, location*, complaint_mode, incident_desc* }
    Returns: { success, case_id, reference }
    """
    body           = request.get_json(silent=True) or {}
    name           = (body.get("name") or "").strip()
    contact        = (body.get("contact") or "").strip()
    email          = (body.get("email") or "").strip()
    crime_type     = (body.get("crime_type") or "Other").strip()
    location       = (body.get("location") or "").strip()
    complaint_mode = (body.get("complaint_mode") or "Online").strip()
    incident_desc  = (body.get("incident_desc") or "").strip()

    if not name:
        return _err("name is required")
    if not contact:
        return _err("contact is required")
    if not incident_desc:
        return _err("incident_desc is required")
    if not location:
        return _err("location is required")
    if crime_type not in VALID_CRIME_TYPES:
        crime_type = "Other"
    if complaint_mode not in VALID_COMPLAINT_MODES:
        complaint_mode = "Online"

    try:
        new_id = queries.submit_public_complaint(
            name, contact, email, crime_type, location, complaint_mode, incident_desc
        )
        return jsonify({
            "success":   True,
            "case_id":   new_id,
            "reference": _format_case_id(new_id),
        }), 201
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/public/access-request", methods=["POST"])
def public_access_request():
    """
    POST /public/access-request
    Logs a citizen request for case access.
    In this MVP the request is just acknowledged (logged to console / future table).
    Body: { case_id*, requester_name*, requester_email*, reason* }
    """
    body            = request.get_json(silent=True) or {}
    case_id         = (body.get("case_id") or "").strip()
    requester_name  = (body.get("requester_name") or "").strip()
    requester_email = (body.get("requester_email") or "").strip()
    reason          = (body.get("reason") or "").strip()

    if not case_id:
        return _err("case_id is required")
    if not requester_name:
        return _err("requester_name is required")
    if not requester_email:
        return _err("requester_email is required")
    if not reason:
        return _err("reason is required")

    # Log the request — extend this to insert into an `access_requests` table when ready.
    print(f"[ACCESS REQUEST] Case: {case_id} | From: {requester_name} <{requester_email}> | Reason: {reason}")

    return _ok(message="Access request submitted. You will be notified within 48 hours.")


# ──────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    return _err("Endpoint not found", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return _err("Method not allowed", 405)


@app.errorhandler(500)
def internal_error(e):
    return _err(f"Internal server error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# FRONTEND
# ──────────────────────────────────────────────────────────────────────────────

import os

@app.route("/")
def serve_frontend():
    """Serve crms_frontend.html when visiting http://127.0.0.1:5000"""
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crms_frontend.html")
    if not os.path.exists(frontend_path):
        return _err("crms_frontend.html not found next to app.py — place both files in the same folder", 404)
    with open(frontend_path, "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

# Initialise DB pool at module level so gunicorn/Railway picks it up.
# Safe to call multiple times — only creates the pool once.
print("=" * 60)
print("  CRMS Flask API — Bengaluru Police Department")
print("=" * 60)
init_pool()

if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
