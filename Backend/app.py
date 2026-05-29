# ─── Themis's Domain Flask API ────────────────────────────────────────────────────────────
# Entry point. Defines every route, validates inputs, and returns JSON.
# All SQL lives in queries.py. All credentials live in config.py.
#
# Run:
#   python app.py
#
# Server starts at http://localhost:5000

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import mysql.connector
import requests
import bcrypt
import threading
import time
import logging
import os
import mimetypes
from pathlib import Path
from werkzeug.utils import secure_filename
import re
import dns.resolver

if __package__:
    from . import config
    from .db_connection import init_pool, get_db
    from . import queries
    from .assignment_algorithm import process_pending_complaints
    from . import email_utils
else:
    import config
    from db_connection import init_pool, get_db
    import queries
    from assignment_algorithm import process_pending_complaints
    import email_utils

def verify_email_mx(email):
    """
    Checks if the email has a valid format and its domain has valid MX records.
    Returns (is_valid, reason)
    """
    if not email:
        return False, "Email address is required."
        
    # Standard email regex pattern
    pattern = r'^[\w\.\+\-]+\@([\w\-]+\.)+[\w\-]{2,4}$'
    if not re.match(pattern, email):
        return False, "Invalid email format."
        
    try:
        domain = email.split('@')[1]
    except IndexError:
        return False, "Invalid email format (missing domain)."
        
    try:
        # Perform DNS MX record lookup
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5.0
        resolver.lifetime = 5.0
        mx_records = resolver.resolve(domain, 'MX')
        if len(mx_records) > 0:
            return True, "Email domain has valid MX records."
    except dns.resolver.NXDOMAIN:
        return False, f"Domain '{domain}' does not exist."
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False, f"Domain '{domain}' does not have a mail exchange server configured."
    except dns.exception.Timeout:
        return False, "DNS lookup timed out."
    except Exception as e:
        return False, f"DNS lookup failed: {str(e)}"
        
    return False, f"No MX records found for domain '{domain}'."



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGIN)

# Configure evidence upload parameters
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB file size limit


# ──────────────────────────────────────────────────────────────────────────────
# Background Job: Automated Case Assignment Scheduler
# ──────────────────────────────────────────────────────────────────────────────

def run_assignment_scheduler():
    """
    Background thread that periodically assigns
    pending complaints to officers based on case severity and officer availability.
    """
    try:
        interval_seconds = max(10, int(os.getenv("ASSIGNMENT_SCHEDULER_INTERVAL_SECONDS", "60")))
    except ValueError:
        interval_seconds = 60
    logger.info(f"[SCHEDULER] Case assignment scheduler started; interval={interval_seconds}s")
    while True:
        try:
            time.sleep(interval_seconds)
            logger.debug("[SCHEDULER] Running pending complaint assignment check...")
            results = process_pending_complaints()
            
            if results["processed"] > 0 or results["errors"] > 0:
                logger.info(
                    f"[SCHEDULER] Assignment run completed: "
                    f"{results['processed']} processed, {results['errors']} errors"
                )
        except Exception as e:
            logger.error(f"[SCHEDULER] Error in assignment scheduler: {str(e)}")


def start_assignment_scheduler():
    """
    Starts the assignment scheduler in a background daemon thread.
    Called during application startup.
    """
    scheduler_thread = threading.Thread(target=run_assignment_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("[STARTUP] Assignment scheduler thread started")


def startup_services():
    """
    Initializes process-local services for both Gunicorn and local Flask runs.
    Gunicorn imports `Backend.app:app`, so this cannot live only in __main__.
    """
    init_pool()
    queries.ensure_auth_schema()
    if os.getenv("ENABLE_ASSIGNMENT_SCHEDULER", "true").lower() == "true":
        start_assignment_scheduler()


startup_services()


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

VALID_STATUSES       = {"Pending Review", "Recommended", "Assigned", "Active", "Solved", "Closed", "Rejected"}
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


def _parse_officer_id_header():
    """Reads X-Officer-Id header. Returns (officer_id, error_response) or (id, None)."""
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return None, _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return None, _err("Invalid X-Officer-Id header", 400)
    session_token = request.headers.get("X-Session-Token")
    if not queries.validate_officer_session(officer_id, session_token):
        return None, _err("Unauthorized: Invalid or expired officer session", 401)
    return officer_id, None


def _parse_officer_id_for_file_request():
    """
    Reads officer identity for evidence file links.
    Browser <a>, <img>, <video>, and <audio> requests cannot send custom headers,
    so these GET-only file routes also accept X-Officer-Id as a query parameter.
    """
    officer_id_str = request.headers.get("X-Officer-Id") or request.args.get("X-Officer-Id")
    if not officer_id_str:
        return None, _err("Unauthorized: Missing X-Officer-Id header or query parameter", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return None, _err("Invalid X-Officer-Id value", 400)
    session_token = request.headers.get("X-Session-Token") or request.args.get("X-Session-Token")
    if not queries.validate_officer_session(officer_id, session_token):
        return None, _err("Unauthorized: Invalid or expired officer session", 401)
    return officer_id, None


@app.before_request
def _require_valid_officer_session():
    """
    Any request that identifies an officer must also carry that officer's active
    session token. This covers routes that still parse X-Officer-Id inline.
    """
    if request.endpoint in {"officer_login", "officer_logout", "serve_frontend", "health"}:
        return None

    officer_id_str = request.headers.get("X-Officer-Id") or request.args.get("X-Officer-Id")
    if not officer_id_str:
        return None

    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id value", 400)

    session_token = request.headers.get("X-Session-Token") or request.args.get("X-Session-Token")
    if not queries.validate_officer_session(officer_id, session_token):
        return _err("Unauthorized: Invalid or expired officer session", 401)
    return None


def _row_to_dict(cursor, row):
    """Converts a DB row tuple into a dict keyed by column names."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_list(cursor, rows):
    """Converts DB rows to list of dicts."""
    return [_row_to_dict(cursor, r) for r in rows]


def _is_admin(officer: dict) -> bool:
    """Check if officer has admin role."""
    return (officer.get("role") or "").lower() == "admin"


def _officer_may_decide_access_request(officer: dict, case_id: int) -> bool:
    """
    Admin may always decide.
    Only the highest-ranked officer assigned to a case may approve/reject requests.
    Returns True if authorized, False otherwise.
    """
    if _is_admin(officer):
        return True
    
    # Check if officer is assigned to the case
    if not queries.officer_is_assigned_to_case(officer["officer_id"], case_id):
        return False
    
    # Check if officer is the highest-ranked on this case
    highest_officer = queries.get_highest_ranked_officer_on_case(case_id)
    if highest_officer and highest_officer["officer_id"] == officer["officer_id"]:
        return True
    
    return False


def _officer_may_update_case_status(officer: dict, case_id: int) -> bool:
    """
    Only admins may update case status.
    Returns True if authorized, False otherwise.
    """
    return _is_admin(officer)


def _verify_captcha(token):
    """
    Verifies reCAPTCHA v2 token with Google.
    Returns: (is_valid, score, error_msg)
      is_valid: True if CAPTCHA verification passed
      score: None for v2 (v2 doesn't return a score, unlike v3)
      error_msg: Error message if verification failed
    """
    if not config.RECAPTCHA_SECRET_KEY:
        # If secret key not configured, allow the request to proceed
        return (True, None, None)
    
    if not token:
        # Token is required for v2
        print(f"[CAPTCHA] ERROR: Empty token received")
        return (False, None, "CAPTCHA verification failed - no token provided")
    
    try:
        print(f"[CAPTCHA] Verifying v2 token with Google (secret key: {config.RECAPTCHA_SECRET_KEY[:10]}...)")
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": config.RECAPTCHA_SECRET_KEY,
                "response": token
            },
            timeout=5
        )
        result = response.json()
        
        print(f"[CAPTCHA] Google v2 response: {result}")
        
        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            print(f"[CAPTCHA] v2 Verification failed: {error_codes}")
            error_msg = f"CAPTCHA verification failed"
            if error_codes:
                error_msg += f" ({', '.join(error_codes)})"
            return (False, None, error_msg)
        
        # For v2, we just check success. No score available.
        print(f"[CAPTCHA] v2 Verification successful")
        return (True, None, None)
    except Exception as e:
        print(f"[CAPTCHA] Error during v2 verification: {str(e)}")
        return (False, None, f"CAPTCHA verification error: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Quick ping to confirm the server is alive."""
    return _ok(message="Themis's Domain API is operational")


# ──────────────────────────────────────────────────────────────────────────────
# CASES  —  /cases
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/cases", methods=["GET"])
@app.route("/api/cases", methods=["GET"])
def get_cases():
    """
    Returns filtered cases from the database with pagination support.
    Query parameters:
      - status, crime_type, location, search (Filters)
      - page (default: 1)
      - limit (default: 16)
    """
    status     = request.args.get("status")
    crime_type = request.args.get("crime_type")
    location   = request.args.get("location")
    search     = request.args.get("search")

    # Pagination parameters
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = max(1, int(request.args.get("limit", 16)))
    except ValueError:
        page = 1
        limit = 16

    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)

    try:
        # Check officer identity and role for visibility boundary enforcement
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)

        role = officer.get("role")
        # Exception Rule: bypass for 'admin' or 'inspector'
        bypass_visibility = (role in ("admin", "inspector"))

        total_records = queries.count_cases(
            status=status,
            crime_type=crime_type,
            location=location,
            search=search,
            officer_id=officer_id,
            bypass_visibility=bypass_visibility
        )
        total_pages = (total_records + limit - 1) // limit  # Ceiling division

        paginated_cases = queries.get_all_cases(
            status=status,
            crime_type=crime_type,
            location=location,
            search=search,
            officer_id=officer_id,
            bypass_visibility=bypass_visibility,
            limit=limit,
            offset=(page - 1) * limit,
        )

        return _ok(
            data=paginated_cases,
            pagination={
                "total_records": total_records,
                "total_pages": total_pages,
                "current_page": page,
                "limit": limit
            }
        )
    except Exception as e:
        return _err(f"Database error while fetching cases: {str(e)}", 500)

@app.route("/cases/<int:case_id>", methods=["GET"])
@app.route("/api/cases/<int:case_id>", methods=["GET"])
def get_case(case_id):
    """
    GET /cases/<case_id>
    Returns a single case with assigned officer IDs.
    """
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)

    try:
        # Check officer identity and role for visibility boundary enforcement
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)

        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)

        role = officer.get("role")
        # Enforce visibility rules for single case retrieval
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied to this case record", 403)

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
      status         — Pending Review | Recommended | Assigned | Active | Solved | Closed | Rejected
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

    complainant_name    = (body.get("complainant_name")    or "").strip() or None
    complainant_contact = (body.get("complainant_contact") or "").strip() or None
    complainant_aadhaar = (body.get("complainant_aadhaar") or "").strip() or None
    source              = "officer"   # officer-filed case

    try:
        new_id = queries.insert_case(
            title, description, crime_type, status, location, complaint_mode,
            complainant_name, complainant_contact, complainant_aadhaar, source
        )
        return jsonify({
            "success":         True,
            "case_id":         new_id,
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
    Status changes require admin role.

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

    # If status is being updated, enforce authorization
    if "status" in body:
        officer_id, err = _parse_officer_id_header()
        if err:
            return err
        
        try:
            officer = queries.get_officer_by_id(officer_id)
            if not officer:
                return _err("Unauthorized: Officer record not found", 401)
            
            if not _officer_may_update_case_status(officer, case_id):
                return _err("Unauthorized: Only admins may update case status", 403)
        except mysql.connector.Error as e:
            return _err(f"Database error: {str(e)}", 500)

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


@app.route("/cases/<int:case_id>/highest-ranked", methods=["GET"])
def get_case_highest_ranked(case_id):
    """
    GET /cases/<case_id>/highest-ranked
    Returns the highest-ranked officer assigned to a case. No admin role required;
    used by frontend to determine which officer may approve access-requests or
    update status without fetching the full officers list.
    """
    try:
        officer = queries.get_highest_ranked_officer_on_case(case_id)
        if not officer:
            return _err(f"No officers assigned to case {case_id}", 404)
        return _ok(data=officer)
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


@app.route("/officers/available", methods=["GET"])
def get_available_officers():
    """
    GET /officers/available?case_id=<case_id>
    Returns all officers NOT currently assigned to the given case.
    Used by the admin modal to show available officers for reassignment.
    """
    case_id_param = request.args.get("case_id", type=int)
    if case_id_param is None:
        return _err("case_id query parameter is required")
    
    try:
        all_officers = queries.get_all_officers()
        case = queries.get_case_by_id(case_id_param)
        if not case:
            return _err(f"Case {case_id_param} not found", 404)
        
        assigned_ids = set(case.get("officer_ids", []))
        available = [o for o in all_officers if o["officer_id"] not in assigned_ids]
        return _ok(available)
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
# ADMIN OFFICER REASSIGNMENT  —  /case-officer/add, /case-officer/remove
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/case-officer/add", methods=["POST"])
def admin_add_officer_to_case():
    """
    POST /case-officer/add
    Admin-only endpoint to dynamically add an officer to an active case.
    Sends email notification to the officer.
    
    Body: { case_id*, officer_id* }
    Header: X-Officer-Id required (must be admin)
    
    Returns: { success, message, assignment }
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
    
    body = request.get_json(silent=True) or {}
    case_id = body.get("case_id")
    new_officer_id = body.get("officer_id")
    
    if case_id is None:
        return _err("case_id is required")
    if new_officer_id is None:
        return _err("officer_id is required")
    
    try:
        # 1. Verify requester is admin
        requester = queries.get_officer_by_id(officer_id)
        if not requester:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(requester):
            return _err("Unauthorized: Admin role required to add officers to cases", 403)
        
        # 2. Verify case exists
        case = queries.get_case_by_id(int(case_id))
        if not case:
            return _err(f"Case {case_id} does not exist", 404)
        
        # 3. Verify new officer exists
        new_officer = queries.get_officer_by_id(int(new_officer_id))
        if not new_officer:
            return _err(f"Officer {new_officer_id} does not exist", 404)
        
        # 4. Check if already assigned (avoid duplicates)
        if queries.officer_is_assigned_to_case(int(new_officer_id), int(case_id)):
            return _err(f"Officer {new_officer_id} is already assigned to case {case_id}", 400)
        
        # 5. Add officer to case
        rows = queries.assign_officer(int(case_id), int(new_officer_id))
        if rows == 0:
            return _err("Failed to add officer to case", 500)
        
        # 6. Send email notification asynchronously
        email_utils.send_officer_assignment_notification_async(
            int(case_id), int(new_officer_id), "added"
        )
        
        logger.info(f"[REASSIGNMENT] Officer {new_officer_id} added to case {case_id} by admin {officer_id}")
        
        return _ok(
            message=f"Officer {new_officer.get('name')} successfully added to case {_format_case_id(case_id)}. Notification email sent.",
            assignment={
                "case_id": int(case_id),
                "officer_id": int(new_officer_id),
                "officer_name": new_officer.get("name"),
                "officer_rank": new_officer.get("rank"),
                "action": "added"
            }
        )
    
    except ValueError as ve:
        return _err(f"Invalid parameter format: {str(ve)}", 400)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[REASSIGNMENT] Error adding officer: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/case-officer/remove", methods=["POST"])
def admin_remove_officer_from_case():
    """
    POST /case-officer/remove
    Admin-only endpoint to dynamically remove an officer from an active case.
    Sends email notification to the officer.
    
    Body: { case_id*, officer_id* }
    Header: X-Officer-Id required (must be admin)
    
    Returns: { success, message, assignment }
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
    
    body = request.get_json(silent=True) or {}
    case_id = body.get("case_id")
    remove_officer_id = body.get("officer_id")
    
    if case_id is None:
        return _err("case_id is required")
    if remove_officer_id is None:
        return _err("officer_id is required")
    
    try:
        # 1. Verify requester is admin
        requester = queries.get_officer_by_id(officer_id)
        if not requester:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(requester):
            return _err("Unauthorized: Admin role required to remove officers from cases", 403)
        
        # 2. Verify case exists
        case = queries.get_case_by_id(int(case_id))
        if not case:
            return _err(f"Case {case_id} does not exist", 404)
        
        # 3. Verify officer exists
        remove_officer = queries.get_officer_by_id(int(remove_officer_id))
        if not remove_officer:
            return _err(f"Officer {remove_officer_id} does not exist", 404)
        
        # 4. Check if assignment exists
        if not queries.officer_is_assigned_to_case(int(remove_officer_id), int(case_id)):
            return _err(f"Officer {remove_officer_id} is not assigned to case {case_id}", 404)
        
        # 5. Remove officer from case
        rows = queries.unassign_officer(int(case_id), int(remove_officer_id))
        if rows == 0:
            return _err("Failed to remove officer from case", 500)
        
        # 6. Send email notification asynchronously
        email_utils.send_officer_assignment_notification_async(
            int(case_id), int(remove_officer_id), "removed"
        )
        
        logger.info(f"[REASSIGNMENT] Officer {remove_officer_id} removed from case {case_id} by admin {officer_id}")
        
        return _ok(
            message=f"Officer {remove_officer.get('name')} successfully removed from case {_format_case_id(case_id)}. Notification email sent.",
            assignment={
                "case_id": int(case_id),
                "officer_id": int(remove_officer_id),
                "officer_name": remove_officer.get("name"),
                "officer_rank": remove_officer.get("rank"),
                "action": "removed"
            }
        )
    
    except ValueError as ve:
        return _err(f"Invalid parameter format: {str(ve)}", 400)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[REASSIGNMENT] Error removing officer: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/<int:case_id>/request-dossier", methods=["POST"])
def request_case_dossier_email(case_id):
    """
    POST /cases/<case_id>/request-dossier
    Allows an officer to request an updated case dossier PDF, teammate list,
    and case details to be sent to their email.
    
    Header: X-Officer-Id required
    
    Returns: { success, message }
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to the case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Check if officer has an email
        if not officer.get("email"):
            return _err("Request failed: You do not have an email address configured in the system", 400)
            
        # 5. Dispatch email notification asynchronously
        email_utils.send_dossier_update_notification_async(case_id, officer_id)
        
        logger.info(f"[DOSSIER REQUEST] Officer {officer_id} requested updated dossier for case {case_id}")
        
        display_id = _format_case_id(case_id)
        return _ok(message=f"An updated case dossier PDF for case {display_id} has been requested and will be emailed to you shortly.")
        
    except Exception as e:
        logger.error(f"[DOSSIER REQUEST] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# TIMELINE & EVIDENCE ENDPOINTS
# Route mapping:
#   GET  /cases/<case_id>/updates
#   POST /cases/<case_id>/updates
#   GET  /cases/<case_id>/evidence
#   POST /cases/<case_id>/evidence
#   GET  /cases/evidence/file/<case_id>/<filename>
#   DELETE /cases/evidence/<evidence_id>
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/cases/<int:case_id>/updates", methods=["GET"])
def get_case_updates_route(case_id):
    """
    GET /cases/<case_id>/updates
    Retrieves chronological timeline investigation updates for a case.
    Requires X-Officer-Id auth header and Visibility clearance.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Fetch timeline updates
        updates = queries.get_case_updates(case_id)
        return _ok(updates)
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[TIMELINE GET] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/<int:case_id>/updates", methods=["POST"])
def add_case_update_route(case_id):
    """
    POST /cases/<case_id>/updates
    Allows an authorized officer to append a timeline investigation update.
    Requires X-Officer-Id auth header and Visibility clearance.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    body = request.get_json(silent=True) or {}
    update_text = (body.get("update_text") or "").strip()
    
    if not update_text:
        return _err("update_text is required")
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Insert update record
        update_id = queries.insert_case_update(case_id, officer_id, update_text)
        logger.info(f"[TIMELINE ADD] Officer {officer_id} added timeline update {update_id} for case {case_id}")
        
        return _ok(
            message="Timeline update successfully appended.",
            update={
                "update_id": update_id,
                "case_id": case_id,
                "officer_id": officer_id,
                "officer_name": officer.get("name"),
                "officer_rank": officer.get("rank"),
                "update_text": update_text,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
        )
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[TIMELINE ADD] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/<int:case_id>/evidence", methods=["GET"])
def get_case_evidence_route(case_id):
    """
    GET /cases/<case_id>/evidence
    Retrieves evidence metadata items for a case.
    Requires X-Officer-Id auth header and Visibility clearance.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Fetch evidence list
        evidence = queries.get_case_evidence(case_id)
        return _ok(evidence)
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[EVIDENCE GET] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


# Whitelist of allowed file extensions
ALLOWED_EVIDENCE_EXTENSIONS = {"pdf", "jpeg", "jpg", "png", "mp4"}

@app.route("/cases/<int:case_id>/evidence", methods=["POST"])
def upload_case_evidence_route(case_id):
    """
    POST /cases/<case_id>/evidence
    Handles secure evidence file uploads. Stores the file on disk and meta in DB.
    Requires X-Officer-Id auth header and Visibility clearance.
    Strictly restricts uploads to PDF, JPEG/JPG, PNG, MP4 up to 10MB.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    # Check max content size strictly
    if request.content_length and request.content_length > 10 * 1024 * 1024:
        return _err("File is too large. Safe limit is 10MB", 413)
        
    if 'file' not in request.files:
        return _err("No file provided in the upload request")
        
    file = request.files['file']
    description = request.form.get("description", "").strip() or None
    
    if file.filename == '':
        return _err("No file selected for upload")
        
    # Extract extension safely
    original_name = file.filename
    ext = (original_name.rsplit('.', 1)[-1] if '.' in original_name else '').lower()
    
    # 1. Security extension check: reject anything not in the whitelist
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        return _err(f"Upload failed: File type .{ext} is not allowed. Only PDF, JPEG, PNG, and MP4 are permitted.", 400)
        
    # Verify file content length via post-read check to prevent bypasses
    file.seek(0, os.SEEK_END)
    actual_size = file.tell()
    file.seek(0)
    if actual_size > 10 * 1024 * 1024:
        return _err("File is too large. Safe limit is 10MB", 400)
        
    try:
        # 2. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 3. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 4. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 5. Sanitize and organize paths
        secure_filename_str = secure_filename(original_name)
        if not secure_filename_str or secure_filename_str in ('.', '..'):
            timestamp = int(time.time())
            secure_filename_str = f"evidence_{timestamp}.{ext}" if ext else f"evidence_{timestamp}"
            
        timestamp_prefix = f"{int(time.time())}_"
        unique_filename = f"{timestamp_prefix}{secure_filename_str}"
            
        case_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"case_{case_id}")
        os.makedirs(case_dir, exist_ok=True)
        
        final_path = os.path.join(case_dir, unique_filename)
        
        if not os.path.abspath(final_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return _err("Path traversal attempt detected", 400)
            
        file.save(final_path)
        
        mime_type, _ = mimetypes.guess_type(final_path)
        mime_type = mime_type or 'application/octet-stream'
        
        file_size = os.path.getsize(final_path)
        
        relative_path = f"case_{case_id}/{unique_filename}"
        
        evidence_id = queries.insert_case_evidence(
            case_id=case_id,
            officer_id=officer_id,
            file_name=unique_filename,
            original_name=original_name,
            file_path=final_path,
            mime_type=mime_type,
            file_size=file_size,
            description=description
        )
        
        logger.info(f"[EVIDENCE UPLOAD] Officer {officer_id} uploaded evidence {evidence_id} for case {case_id}")
        
        # 6. Dispatch email notification asynchronously to admin and assigned officers
        email_utils.send_evidence_email_async(case_id, officer_id, evidence_id)
        
        return _ok(
            message="Evidence file successfully uploaded.",
            evidence={
                "evidence_id": evidence_id,
                "case_id": case_id,
                "officer_id": officer_id,
                "officer_name": officer.get("name"),
                "file_name": unique_filename,
                "original_name": original_name,
                "mime_type": mime_type,
                "file_size": file_size,
                "description": description,
                "relative_path": relative_path,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
        )
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[EVIDENCE UPLOAD] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/evidence/file/<int:case_id>/<string:filename>", methods=["GET"])
def serve_evidence_file_route(case_id, filename):
    """
    GET /cases/evidence/file/<case_id>/<filename>
    Secure static serving endpoint. Checks officer authorization before sending file.
    Requires X-Officer-Id auth header or query parameter and Visibility clearance.
    """
    officer_id, err = _parse_officer_id_for_file_request()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Serve file securely
        case_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"case_{case_id}")
        final_path = os.path.join(case_dir, filename)
        
        if not os.path.abspath(final_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return _err("Access denied", 400)
            
        if not os.path.exists(final_path):
            return _err("Evidence file not found on disk", 404)
            
        return send_from_directory(case_dir, filename)
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[EVIDENCE SERVE] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/<int:case_id>/evidence/<string:filename>/download", methods=["GET"])
def download_evidence_file_route(case_id, filename):
    """
    GET /cases/<case_id>/evidence/<filename>/download
    Secure downloading endpoint for evidence. Enforces authentication and case visibility.
    Forces download via as_attachment=True.
    """
    officer_id, err = _parse_officer_id_for_file_request()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Verify case exists
        case = queries.get_case_by_id(case_id)
        if not case:
            return _err(f"Case {case_id} not found", 404)
            
        # 3. Check authorization (must be admin, inspector, or assigned to case)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector"):
            if officer_id not in case.get("officer_ids", []):
                return _err("Access denied: You are not assigned to this case", 403)
                
        # 4. Serve file securely for download
        case_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"case_{case_id}")
        final_path = os.path.join(case_dir, filename)
        
        if not os.path.abspath(final_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return _err("Access denied", 400)
            
        if not os.path.exists(final_path):
            return _err("Evidence file not found on disk", 404)
            
        return send_from_directory(case_dir, filename, as_attachment=True)
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[EVIDENCE DOWNLOAD] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/cases/evidence/<int:evidence_id>", methods=["DELETE"])
def delete_case_evidence_route(evidence_id):
    """
    DELETE /cases/evidence/<evidence_id>
    Removes evidence record from DB and cleans up the physical file to prevent orphans.
    Requires X-Officer-Id auth header. Admins, inspectors, or uploader only.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
        
    try:
        # 1. Verify officer exists
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
            
        # 2. Fetch evidence metadata
        evidence = queries.get_evidence_by_id(evidence_id)
        if not evidence:
            return _err(f"Evidence {evidence_id} not found", 404)
            
        # 3. Check authorization (admins, inspectors, or uploading officer uploader)
        role = (officer.get("role") or "").lower()
        if role not in ("admin", "inspector") and officer_id != evidence["officer_id"]:
            return _err("Access denied: You are not authorized to delete this evidence", 403)
            
        # 4. Delete physical file from filesystem to prevent orphans
        full_path = evidence.get("file_path")
        if full_path and os.path.exists(full_path):
            if os.path.abspath(full_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
                try:
                    os.remove(full_path)
                    logger.info(f"[EVIDENCE DELETION] Deleted file on disk: {full_path}")
                except Exception as fe:
                    logger.error(f"[EVIDENCE DELETION] Disk cleanup failed for {full_path}: {str(fe)}")
            else:
                logger.warning(f"[EVIDENCE DELETION] Security check failed: Path out of bounds: {full_path}")
                
        # 5. Remove DB row
        queries.delete_case_evidence(evidence_id)
        logger.info(f"[EVIDENCE DELETION] Evidence {evidence_id} deleted by officer {officer_id}")
        
        return _ok(message="Evidence metadata and physical file successfully deleted.")
        
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)
    except Exception as e:
        logger.error(f"[EVIDENCE DELETION] Error: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
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
# AUTOMATED ASSIGNMENTS  —  /assignments
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/assignments/pending", methods=["GET"])
def get_pending_assignments():
    """
    GET /assignments/pending
    Returns all pending complaints that are waiting to be automatically assigned to officers.
    This shows the queue of cases waiting for the assignment algorithm to process.
    """
    try:
        pending = queries.get_public_complaints(status="Pending")
        return _ok(pending_count=len(pending), complaints=pending)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/assignments/process", methods=["POST"])
def trigger_assignment_process():
    """
    POST /assignments/process
    Manually triggers the automated assignment algorithm to process all pending complaints.
    Useful for SHO override or testing the assignment process.
    Returns: {success, processed, errors, details}
    """
    try:
        results = process_pending_complaints()
        return _ok(
            processed=results["processed"],
            errors=results["errors"],
            details=results["details"]
        )
    except Exception as e:
        logger.error(f"[API] Error in manual assignment trigger: {str(e)}")
        return _err(f"Assignment process error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC PORTAL  —  /public/complaint  /public/access-request  /public/otp/*  /public/verify-email
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/public/verify-email", methods=["POST"])
def verify_email_route():
    """
    POST /public/verify-email
    Validates email format and queries DNS MX records for the domain.
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    
    if not email:
        return jsonify({
            "success": True,
            "valid": False,
            "reason": "Email address is required."
        }), 200
        
    is_valid, reason = verify_email_mx(email)
    return jsonify({
        "success": True,
        "valid": is_valid,
        "reason": reason
    }), 200


@app.route("/public/otp/send", methods=["POST"])
def send_otp():
    """
    POST /public/otp/send
    Generates and sends a 6-digit OTP to the user's email address.
    Rate limited to 3 sends per 10 minutes.
    """
    import random
    if __package__:
        from .email_utils import send_verification_email
        from .otp_store import otp_store
    else:
        from email_utils import send_verification_email
        from otp_store import otp_store

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()

    if not email:
        return _err("Email address is required to send OTP.", 400)

    is_valid, reason = verify_email_mx(email)
    if not is_valid:
        return _err(reason, 400)

    key = email.lower()
    if not otp_store.can_send_otp(key):
        return _err("Too many OTP requests. Please wait before trying again.", 429)

    otp = f"{random.randint(100000, 999999)}"
    otp_store.save_otp(key, otp, ttl=120)
    otp_store.record_send(key)
    success, msg = send_verification_email(key, otp)
    if not success:
        return _err(msg, 500)

    return jsonify({
        "success": True,
        "message": "OTP sent successfully to email.",
        "expires_in": 120
    }), 200


@app.route("/public/otp/verify", methods=["POST"])
def verify_otp():
    """
    POST /public/otp/verify
    Verifies the OTP and returns a verification token on success.
    """
    import random
    if __package__:
        from .otp_store import otp_store
    else:
        from otp_store import otp_store

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    otp = (body.get("otp") or "").strip()

    if not email:
        return _err("Email address is required.", 400)
    if not otp:
        return _err("OTP is required.", 400)

    key = email.lower()
    success, result_or_err = otp_store.verify_otp(key, otp)

    if not success:
        return _err(result_or_err, 400)

    return jsonify({
        "success": True,
        "verified": True,
        "token": result_or_err
    }), 200


@app.route("/public/complaint", methods=["POST"])
def public_complaint():
    """
    POST /public/complaint
    Adds a citizen complaint to public_complaints staging and creates a preliminary cases row
    with status Pending Review for intake tracking.
    Body: { name*, contact*, aadhaar*, email, crime_type*, location*,
            complaint_mode, incident_desc*, captcha_token*, email_verification_token }
    Returns: { success, reference }   (reference = PC-XXX format)
    """
    body                     = request.get_json(silent=True) or {}
    captcha_token            = (body.get("captcha_token") or "").strip()
    verification_token       = (body.get("email_verification_token") or "").strip()
    
    # Verify CAPTCHA first
    is_valid, score, error_msg = _verify_captcha(captcha_token)
    if not is_valid:
        return _err(error_msg or "CAPTCHA verification failed", 403)
    
    name           = (body.get("name")           or "").strip()
    contact        = (body.get("contact")        or "").strip()
    email          = (body.get("email")          or "").strip()
    aadhaar        = (body.get("aadhaar")        or "").strip()
    crime_type     = (body.get("crime_type")     or "Other").strip()
    location       = (body.get("location")       or "").strip()
    complaint_mode = (body.get("complaint_mode") or "Online").strip()
    incident_desc  = (body.get("incident_desc")  or "").strip()

    if not name:
        return _err("name is required")
    if not contact:
        return _err("contact is required")
    if not email:
        return _err("email is required")
    if not location:
        return _err("location is required")
    if not incident_desc:
        return _err("incident_desc is required")
    if not aadhaar or not aadhaar.isdigit() or len(aadhaar) != 12:
        return _err("aadhaar must be exactly 12 digits")
    if crime_type not in VALID_CRIME_TYPES:
        crime_type = "Other"
    if complaint_mode not in VALID_COMPLAINT_MODES:
        complaint_mode = "Online"

    if not verification_token:
        return _err("Email verification is required.", 400)

    if __package__:
        from .otp_store import otp_store
    else:
        from otp_store import otp_store
    if not otp_store.verify_token(email.lower(), verification_token):
        return _err("Invalid or expired verification token. Please verify again.", 400)

    try:
        new_id = queries.submit_public_complaint(
            name, contact, email, aadhaar,
            crime_type, location, complaint_mode, incident_desc
        )
        return jsonify({
            "success":   True,
            "complaint_id": new_id,
            "reference": f"PC-{str(new_id).zfill(3)}",
        }), 201
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)



@app.route("/public/access-request", methods=["POST"])
def public_access_request():
    """
    POST /public/access-request
    Logs a citizen request for case access in the case_access_requests table.
    Body: { case_id*, requester_name*, requester_email*, requester_number*, reason*, captcha_token* }
    """
    body            = request.get_json(silent=True) or {}
    captcha_token   = (body.get("captcha_token") or "").strip()
    
    # Verify reCAPTCHA first
    is_valid, score, error_msg = _verify_captcha(captcha_token)
    if not is_valid:
        return _err(error_msg or "CAPTCHA verification failed", 403)
    
    case_id          = (body.get("case_id") or "").strip()
    requester_name   = (body.get("requester_name") or "").strip()
    requester_email  = (body.get("requester_email") or "").strip()
    requester_number = (body.get("requester_number") or "").strip()
    reason           = (body.get("reason") or "").strip()

    if not case_id:
        return _err("case_id is required")
    if not requester_name:
        return _err("requester_name is required")
    if not requester_email:
        return _err("requester_email is required")
    if not requester_number:
        return _err("contact number is required")
    if not reason:
        return _err("reason is required")

    # Parse display case ID (BLR-XXX -> integer PK, or check if it's plain integer)
    raw_case_id = case_id
    parsed_case_id = None
    if raw_case_id.upper().startswith("BLR-"):
        try:
            parsed_case_id = int(raw_case_id.split("-")[1])
        except (IndexError, ValueError):
            return _err("Invalid Case ID format. Must be BLR-XXX or a numeric ID")
    else:
        try:
            parsed_case_id = int(raw_case_id)
        except ValueError:
            return _err("Invalid Case ID format. Must be BLR-XXX or a numeric ID")

    try:
        # Check if the target case dossier exists
        case = queries.get_case_by_id(parsed_case_id)
        if not case:
            return _err(f"Case with dossier ID {raw_case_id} not found in system records", 404)
            
        new_request_id = queries.submit_case_access_request(
            parsed_case_id, requester_name, requester_email, requester_number, reason
        )
        return jsonify({
            "success": True,
            "request_id": new_request_id,
            "message": "Access request successfully submitted for officer review."
        }), 201
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/public/cases", methods=["GET"])
def public_browse_cases():
    """
    GET /public/cases
    Returns public cases for citizen browsing/discovery.
    Query parameters:
      - status: filter by case status (Active, Solved, Closed, or All)
      - crime_type: filter by crime type
      - location: filter by location (partial match)
      - search: search in case title
    No authentication required — public endpoint.
    """
    status = request.args.get("status")
    crime_type = request.args.get("crime_type")
    location = request.args.get("location")
    search = request.args.get("search")

    try:
        cases = queries.get_public_cases(
            status=status,
            crime_type=crime_type,
            location=location,
            search=search
        )
        return _ok(data=cases)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/api/access-requests", methods=["GET"])
def get_access_requests():
    """
    GET /api/access-requests
    Lists access requests filed for review, based on officer authority visibility boundary.
    Header: X-Officer-Id required.
    """
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)

    try:
        # Check officer identity and role for visibility boundary enforcement
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)

        role = officer.get("role")
        bypass_visibility = (role in ("admin", "inspector"))

        requests_list = queries.get_case_access_requests(
            officer_id=officer_id,
            bypass_visibility=bypass_visibility
        )
        return _ok(requests_list)
    except mysql.connector.Error as e:
        return _err(f"Database error while fetching access requests: {str(e)}", 500)


@app.route("/api/access-requests/<int:request_id>/approve", methods=["POST"])
def approve_access_request(request_id):
    """
    POST /api/access-requests/<request_id>/approve
    Approves the case access request, updates DB state, and sends email + PDF async.
    Header: X-Officer-Id required.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err

    try:
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)

        req = queries.get_access_request_by_id(request_id)
        if not req:
            return _err(f"Access request {request_id} not found", 404)
        if req.get("status") != "Pending":
            return _err(f"Access request is already processed (Status: {req.get('status')})", 400)
        if not _officer_may_decide_access_request(officer, req["case_id"]):
            return _err("Unauthorized: Only the highest-ranked officer on this case or admin may approve requests", 403)

        rows = queries.update_access_request_status(request_id, "Accepted", officer_id)
        if not rows:
            return _err("Request already processed or could not be updated", 400)

        email_utils.send_decision_email_async(request_id, "Accepted", officer_id)

        return _ok(message=f"Access request {request_id} has been approved. Dispatching dossier via email...")
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/api/access-requests/<int:request_id>/reject", methods=["POST"])
def reject_access_request(request_id):
    """
    POST /api/access-requests/<request_id>/reject
    Declines the case access request, updates DB state, and sends notification email async.
    Header: X-Officer-Id required.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err

    try:
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)

        req = queries.get_access_request_by_id(request_id)
        if not req:
            return _err(f"Access request {request_id} not found", 404)
        if req.get("status") != "Pending":
            return _err(f"Access request is already processed (Status: {req.get('status')})", 400)
        if not _officer_may_decide_access_request(officer, req["case_id"]):
            return _err("Unauthorized: Only the highest-ranked officer on this case or admin may reject requests", 403)

        rows = queries.update_access_request_status(request_id, "Rejected", officer_id)
        if not rows:
            return _err("Request already processed or could not be updated", 400)

        email_utils.send_decision_email_async(request_id, "Rejected", officer_id)

        return _ok(message=f"Access request {request_id} has been declined. Dispatching decline notification email...")
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)




# ──────────────────────────────────────────────────────────────────────────────
# STATS  —  /stats
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/stats", methods=["GET"])
def public_stats():
    """
    GET /stats
    Returns real DB counts for the landing page stats strip.
    No auth required — public endpoint.
    """
    try:
        return _ok(queries.get_public_stats())
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN DASHBOARD  —  /admin/*
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/admin/cases", methods=["GET"])
def admin_get_all_cases():
    """
    GET /admin/cases
    Returns ALL cases (bypass visibility) for admin dashboard.
    Admin role required.
    Optional filters: status, crime_type, location, search
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
    
    try:
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(officer):
            return _err("Unauthorized: Admin role required", 403)
        
        status = request.args.get("status")
        crime_type = request.args.get("crime_type")
        location = request.args.get("location")
        search = request.args.get("search")
        
        cases = queries.get_all_cases(
            status=status,
            crime_type=crime_type,
            location=location,
            search=search,
            bypass_visibility=True
        )
        
        return _ok(_enrich_cases(cases))
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard_stats():
    """
    GET /admin/dashboard
    Returns aggregated statistics for admin dashboard.
    Admin role required.
    """
    officer_id, err = _parse_officer_id_header()
    if err:
        return err
    
    try:
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(officer):
            return _err("Unauthorized: Admin role required", 403)
        
        conn = get_db()
        cur = conn.cursor()
        try:
            # Total counts
            cur.execute(
                """SELECT
                     COUNT(*) AS total_cases,
                     COALESCE(SUM(`status` = 'Active'), 0) AS active_cases,
                     COALESCE(SUM(`status` = 'Solved'), 0) AS solved_cases,
                     COALESCE(SUM(`status` = 'Closed'), 0) AS closed_cases,
                     COALESCE(SUM(`status` = 'Pending Review'), 0) AS pending_review_cases,
                     COALESCE(SUM(`status` = 'Recommended'), 0) AS recommended_cases,
                     COALESCE(SUM(`status` = 'Assigned'), 0) AS assigned_cases,
                     COALESCE(SUM(`status` = 'Rejected'), 0) AS rejected_cases
                   FROM cases"""
            )
            counts = cur.fetchone()
            (
                total_cases,
                active_cases,
                solved_cases,
                closed_cases,
                pending_review_cases,
                recommended_cases,
                assigned_cases,
                rejected_cases,
            ) = [int(value or 0) for value in counts]
            
            cur.execute("SELECT COUNT(*) FROM officers")
            total_officers = cur.fetchone()[0]
            
            # Case distribution by type
            cur.execute("SELECT crime_type, COUNT(*) FROM cases GROUP BY crime_type")
            crime_dist = dict(cur.fetchall())
            
            # Case distribution by status
            cur.execute("SELECT `status`, COUNT(*) FROM cases GROUP BY `status`")
            status_dist = dict(cur.fetchall())
            
            # Officer workload
            cur.execute("""
                SELECT 
                    o.officer_id,
                    o.`name`,
                    o.`rank`,
                    o.`role`,
                    COUNT(DISTINCT co.case_id) as case_count
                FROM officers o
                LEFT JOIN case_officer co ON o.officer_id = co.officer_id
                GROUP BY o.officer_id
                ORDER BY case_count DESC
            """)
            officer_workload = _rows_to_list(cur, cur.fetchall())
            
            stats = {
                "cases": {
                    "total": total_cases,
                    "pending_review": pending_review_cases,
                    "recommended": recommended_cases,
                    "assigned": assigned_cases,
                    "active": active_cases,
                    "solved": solved_cases,
                    "closed": closed_cases,
                    "rejected": rejected_cases
                },
                "officers": {
                    "total": total_officers
                },
                "distributions": {
                    "by_crime_type": crime_dist,
                    "by_status": status_dist
                },
                "officer_workload": officer_workload
            }
            
            return _ok(stats)
        finally:
            cur.close()
            conn.close()
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# AUTH  —  /auth/login
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/auth/login", methods=["POST"])
def officer_login():
    """
    POST /auth/login
    Body: { badge_id*, password*, captcha_token* }
    badge_id = distinct officer badge ID (e.g. BPD-7821)

    Returns: { success, officer: { officer_id, name, rank, role, badge, ... } }
    The frontend uses `role` to gate write actions:
      role = 'inspector'  → can add/edit cases (P1)
      role = 'viewer'     → read-only (P2)

    No JWT in this MVP — role is trusted from the response and checked
    server-side on write endpoints via the X-Officer-Id header.
    """
    body           = request.get_json(silent=True) or {}
    captcha_token  = (body.get("captcha_token") or "").strip()
    
    # Verify CAPTCHA first
    is_valid, score, error_msg = _verify_captcha(captcha_token)
    if not is_valid:
        return _err(error_msg or "CAPTCHA verification failed", 403)
    
    # Support both badge_id and legacy identifier for backward compatibility/robustness
    badge_id = (body.get("badge_id") or body.get("identifier") or "").strip()
    password = (body.get("password")   or "").strip()
    force    = bool(body.get("force", False))

    if not badge_id:
        return _err("badge_id is required")
    if not password:
        return _err("password is required")

    try:
        # 1. Identification & Lookup Workflow:
        # Look up by distinct Officer Badge ID.
        officer = queries.get_officer_by_badge(badge_id)
        # If no matching officer row is found, immediately return an explicit JSON error
        # ("Invalid credentials") without running hashing computations.
        if not officer:
            return _err("Invalid credentials", 401)

        # 2. Secure Password Hashing & Verification:
        stored_hash = officer.get("password_hash")
        if not stored_hash:
            return _err("Invalid credentials", 401)

        # Core Correction: Fix reversed/buggy comparison logic
        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return _err("Invalid credentials", 401)

        officer_id = officer["officer_id"]
        if queries.officer_has_active_session(officer_id):
            if not force:
                return _err("This officer is already logged in on another device. Please log out there first.", 409)
            # force=True: revoke all existing sessions so a fresh login can proceed
            queries.revoke_all_officer_sessions(officer_id)

        ttl_hours = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
        session_token, session_expires_at = queries.create_officer_session(
            officer_id,
            ttl_hours,
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        )

        # Remove password_hash for security before sending to the client
        officer.pop("password_hash", None)

        # Enrich officer dict with case metrics and defaults
        queries.enrich_officer_details(officer)
        officer["session_token"] = session_token
        officer["session_expires_at"] = session_expires_at

        return _ok(officer=officer)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/auth/logout", methods=["POST"])
def officer_logout():
    """
    POST /auth/logout
    Body: { officer_id*, session_token* }
    Revokes the active session so the same officer can log in elsewhere.
    """
    body = request.get_json(silent=True) or {}
    officer_id = body.get("officer_id") or request.headers.get("X-Officer-Id")
    session_token = (body.get("session_token") or request.headers.get("X-Session-Token") or "").strip()

    if not officer_id:
        return _err("officer_id is required", 400)
    if not session_token:
        return _err("session_token is required", 400)

    try:
        rows = queries.revoke_officer_session(int(officer_id), session_token)
        return _ok(message="Logged out successfully", revoked=rows > 0)
    except ValueError:
        return _err("Invalid officer_id", 400)
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC COMPLAINTS (officer review)  —  /public-complaints
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/public-complaints", methods=["GET"])
def list_public_complaints():
    """
    GET /public-complaints?status=Pending
    Returns staging complaints for officer review dashboard.
    """
    status = request.args.get("status")
    try:
        return _ok(queries.get_public_complaints(status))
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/public-complaints/<int:complaint_id>/promote", methods=["POST"])
def promote_complaint(complaint_id):
    """
    POST /public-complaints/<id>/promote
    Promotes a staging complaint to a full case.
    Header: X-Officer-Id required.
    """
    officer_id = request.headers.get("X-Officer-Id")
    if not officer_id:
        return _err("X-Officer-Id header required", 401)
    try:
        new_case_id = queries.promote_complaint(complaint_id, int(officer_id))
        if not new_case_id:
            return _err(f"Complaint {complaint_id} not found", 404)
        return _ok(case_id=new_case_id, case_id_display=_format_case_id(new_case_id))
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/public-complaints/<int:complaint_id>/reject", methods=["POST"])
def reject_complaint(complaint_id):
    """
    POST /public-complaints/<id>/reject
    Header: X-Officer-Id required.
    """
    officer_id = request.headers.get("X-Officer-Id")
    if not officer_id:
        return _err("X-Officer-Id header required", 401)
    try:
        rows = queries.reject_complaint(complaint_id, int(officer_id))
        if not rows:
            return _err(f"Complaint {complaint_id} not found", 404)
        return _ok()
    except mysql.connector.Error as e:
        return _err(f"Database error: {str(e)}", 500)


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
# ADMIN: ASSIGNMENT RECOMMENDATIONS
# Admin-reviewed recommendation workflow for public complaints
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/admin/recommendations", methods=["GET"])
@app.route("/api/admin/recommendations", methods=["GET"])
def get_recommendations():
    """
    Returns pending/approved/rejected recommendations with filtering.
    Query parameters:
      - status: 'pending', 'approved', 'rejected' (default: all)
      - limit (default: 50)
    Admin only.
    """
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)
    
    try:
        # Verify admin role
        officer = queries.get_officer_by_id(officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(officer):
            return _err("Forbidden: Admin access required", 403)
        
        status = request.args.get("status")  # Optional filter
        try:
            limit = max(1, int(request.args.get("limit", 50)))
        except ValueError:
            limit = 50
        
        conn = get_db()
        cur = conn.cursor()
        try:
            # Build query
            where_clause = ""
            params = []
            if status:
                where_clause = "WHERE ar.status = %s"
                params.append(status)
            
            query = f"""
                SELECT 
                    ar.recommendation_id,
                    ar.complaint_id,
                    pc.complainant_name,
                    pc.crime_type,
                    pc.location,
                    ar.recommended_officer_ids,
                    ar.admin_approved_officer_ids,
                    ar.status,
                    ar.created_at,
                    ar.approved_at,
                    COALESCE(o.`name`, 'System') AS approved_by_name
                FROM assignment_recommendations ar
                JOIN public_complaints pc ON ar.complaint_id = pc.complaint_id
                LEFT JOIN officers o ON ar.approved_by = o.officer_id
                {where_clause}
                ORDER BY ar.created_at DESC
                LIMIT %s
            """
            params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            recommendations = _rows_to_list(cur, rows)
            
            import json
            for rec in recommendations:
                if rec.get("recommended_officer_ids"):
                    rec["recommended_officer_ids"] = json.loads(rec["recommended_officer_ids"])
                if rec.get("admin_approved_officer_ids"):
                    rec["admin_approved_officer_ids"] = json.loads(rec["admin_approved_officer_ids"])
            
            return _ok(data=recommendations)
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        return _err(f"Database error: {str(e)}", 500)


@app.route("/admin/recommendations/<int:recommendation_id>/approve", methods=["POST"])
@app.route("/api/admin/recommendations/<int:recommendation_id>/approve", methods=["POST"])
def approve_recommendation(recommendation_id):
    """
    Approves a recommendation and creates the case + assignments.
    Admin can optionally modify officer list before approving.
    Request body: { "officer_ids": [1, 2, 3] } (optional; uses recommended if omitted)
    Admin only.
    """
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        admin_officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)
    
    try:
        # Verify admin role
        officer = queries.get_officer_by_id(admin_officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(officer):
            return _err("Forbidden: Admin access required", 403)
        
        # Parse optional officer list modification
        final_officer_ids = None
        try:
            body = request.get_json() or {}
            if "officer_ids" in body:
                final_officer_ids = body["officer_ids"]
                if not isinstance(final_officer_ids, list):
                    return _err("Invalid officer_ids: must be a list", 400)
        except Exception:
            return _err("Invalid JSON body", 400)
        
        # Call algorithm to approve recommendation
        if __package__:
            from .assignment_algorithm import approve_recommendation as approve_rec
        else:
            from assignment_algorithm import approve_recommendation as approve_rec
        case_id = approve_rec(recommendation_id, admin_officer_id, final_officer_ids)
        
        if case_id is None:
            return _err("Failed to approve recommendation or create case", 500)
        
        return _ok(data={
            "recommendation_id": recommendation_id,
            "case_id": case_id,
            "status": "approved"
        })
    except Exception as e:
        logger.error(f"Error approving recommendation {recommendation_id}: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


@app.route("/admin/recommendations/<int:recommendation_id>/reject", methods=["POST"])
@app.route("/api/admin/recommendations/<int:recommendation_id>/reject", methods=["POST"])
def reject_recommendation(recommendation_id):
    """
    Rejects a recommendation (prevents it from being approved).
    Request body: { "reason": "Optional rejection reason" }
    Admin only.
    """
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        admin_officer_id = int(officer_id_str)
    except ValueError:
        return _err("Invalid X-Officer-Id header", 400)
    
    try:
        # Verify admin role
        officer = queries.get_officer_by_id(admin_officer_id)
        if not officer:
            return _err("Unauthorized: Officer record not found", 401)
        
        if not _is_admin(officer):
            return _err("Forbidden: Admin access required", 403)
        
        reason = None
        try:
            body = request.get_json() or {}
            reason = body.get("reason")
        except Exception:
            pass
        
        # Update recommendation status to rejected
        conn = get_db()
        cur = conn.cursor()
        try:
            # Transition the linked case's status back to 'Pending Review'
            cur.execute(
                "SELECT complaint_id FROM assignment_recommendations WHERE recommendation_id = %s",
                (recommendation_id,)
            )
            comp_row = cur.fetchone()
            if comp_row:
                complaint_id = comp_row[0]
                cur.execute(
                    "SELECT promoted_case_id FROM public_complaints WHERE complaint_id = %s",
                    (complaint_id,)
                )
                case_row = cur.fetchone()
                if case_row and case_row[0]:
                    cur.execute(
                        "UPDATE cases SET `status` = 'Pending Review', last_updated = NOW() WHERE case_id = %s",
                        (case_row[0],)
                    )

            cur.execute(
                """UPDATE assignment_recommendations
                   SET status = 'rejected', rejection_reason = %s,
                       approved_by = %s, approved_at = NOW()
                   WHERE recommendation_id = %s AND status = 'pending'""",
                (reason, admin_officer_id, recommendation_id)
            )
            
            if cur.rowcount == 0:
                conn.close()
                return _err("Recommendation not found or already processed", 404)
            
            conn.commit()
            
            return _ok(data={
                "recommendation_id": recommendation_id,
                "status": "rejected",
                "reason": reason
            })
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error rejecting recommendation {recommendation_id}: {str(e)}")
        return _err(f"Internal server error: {str(e)}", 500)


# ──────────────────────────────────────────────────────────────────────────────
# FRONTEND
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def serve_frontend():
    frontend_path = (
        Path(__file__).resolve().parent.parent
        / "Frontend"
        / "crms_frontend.html"
    )
    if not frontend_path.exists():
        return jsonify({
            "success": False,
            "error": f"Frontend file not found: {frontend_path}"
        }), 404

    return send_file(frontend_path)

# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Themis's Domain Flask API — Bengaluru Police Department")
    print("=" * 60)
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
