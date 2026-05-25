This file is a merged representation of the entire codebase, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of the entire repository's contents.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
Backend/
  app.py
  assignment_algorithm.py
  config.py
  db_connection.py
  email_utils.py
  migrate_v2.sql
  migrate_v3.sql
  queries.py
  setup_db.sql
Frontend/
  crms_frontend.html
.env.example
.gitignore
LICENCE
Procfile
README.md
requirements.txt
```

# Files

## File: Backend/app.py
````python
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
import requests
import bcrypt
import threading
import time
import logging

import config
from db_connection import init_pool
import queries
from assignment_algorithm import process_pending_complaints
import email_utils


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


# ──────────────────────────────────────────────────────────────────────────────
# Background Job: Automated Case Assignment Scheduler
# ──────────────────────────────────────────────────────────────────────────────

def run_assignment_scheduler():
    """
    Background thread that runs every 10 seconds to automatically assign
    pending complaints to officers based on case severity and officer availability.
    """
    logger.info("[SCHEDULER] Case assignment scheduler started")
    while True:
        try:
            time.sleep(10)
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


def _parse_officer_id_header():
    """Reads X-Officer-Id header. Returns (officer_id, error_response) or (id, None)."""
    officer_id_str = request.headers.get("X-Officer-Id")
    if not officer_id_str:
        return None, _err("Unauthorized: Missing X-Officer-Id header", 401)
    try:
        return int(officer_id_str), None
    except ValueError:
        return None, _err("Invalid X-Officer-Id header", 400)


def _officer_may_decide_access_request(officer: dict, case_id: int) -> bool:
    """
    Admin and inspector may act on any case access request.
    Other roles may only decide requests for cases they are assigned to.
    """
    role = (officer.get("role") or "").lower()
    if role in ("admin", "inspector"):
        return True
    return queries.officer_is_assigned_to_case(officer["officer_id"], case_id)


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
    return _ok(message="CRMS API is operational")


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

        # Fetch filtered cases from the query layer with visibility constraints
        all_filtered_cases = queries.get_all_cases(
            status=status,
            crime_type=crime_type,
            location=location,
            search=search,
            officer_id=officer_id,
            bypass_visibility=bypass_visibility
        )
        
        total_records = len(all_filtered_cases)
        total_pages = (total_records + limit - 1) // limit  # Ceiling division
        
        # Slice array for current page frame
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_cases = all_filtered_cases[start_idx:end_idx]

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
# PUBLIC PORTAL  —  /public/complaint  /public/access-request
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/public/complaint", methods=["POST"])
def public_complaint():
    """
    POST /public/complaint
    Inserts into public_complaints staging table (NOT directly into cases).
    Body: { name*, contact*, aadhaar_last4*, email, crime_type*, location*,
            complaint_mode, incident_desc*, captcha_token* }
    Returns: { success, reference }   (reference = PC-XXX format)
    """
    body           = request.get_json(silent=True) or {}
    captcha_token  = (body.get("captcha_token") or "").strip()
    
    # Verify CAPTCHA first
    is_valid, score, error_msg = _verify_captcha(captcha_token)
    if not is_valid:
        return _err(error_msg or "CAPTCHA verification failed", 403)
    
    name           = (body.get("name")           or "").strip()
    contact        = (body.get("contact")        or "").strip()
    email          = (body.get("email")          or "").strip()
    aadhaar_last4  = (body.get("aadhaar_last4")  or "").strip()
    crime_type     = (body.get("crime_type")     or "Other").strip()
    location       = (body.get("location")       or "").strip()
    complaint_mode = (body.get("complaint_mode") or "Online").strip()
    incident_desc  = (body.get("incident_desc")  or "").strip()

    if not name:
        return _err("name is required")
    if not contact:
        return _err("contact is required")
    if not location:
        return _err("location is required")
    if not incident_desc:
        return _err("incident_desc is required")
    if not aadhaar_last4 or not aadhaar_last4.isdigit() or len(aadhaar_last4) != 4:
        return _err("aadhaar_last4 must be exactly 4 digits")
    if crime_type not in VALID_CRIME_TYPES:
        crime_type = "Other"
    if complaint_mode not in VALID_COMPLAINT_MODES:
        complaint_mode = "Online"

    try:
        new_id = queries.submit_public_complaint(
            name, contact, email, aadhaar_last4,
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
            return _err("Unauthorized: you are not assigned to this case", 403)

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
            return _err("Unauthorized: you are not assigned to this case", 403)

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

        # Remove password_hash for security before sending to the client
        officer.pop("password_hash", None)

        # Enrich officer dict with case metrics and defaults
        queries.enrich_officer_details(officer)

        return _ok(officer=officer)
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
# FRONTEND
# ──────────────────────────────────────────────────────────────────────────────

import os
from flask import send_file
from pathlib import Path
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
    print("  CRMS Flask API — Bengaluru Police Department")
    print("=" * 60)
    init_pool()
    start_assignment_scheduler()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
````

## File: Backend/assignment_algorithm.py
````python
# ─────────────────────────────────────────────────────────────────────────────
# CRMS Automated Case Assignment Algorithm
# ─────────────────────────────────────────────────────────────────────────────
#
# PURPOSE
# Automatically assigns cases from public_complaints to available officers.
# Runs every 10 seconds to process pending complaints.
#
# WORKFLOW
# 1. Fetch all Pending complaints from public_complaints
# 2. Determine severity based on crime_type
# 3. Select best-suited officers based on:
#    - Rank (matching severity requirements)
#    - Current workload (active cases)
#    - Join date (seniority as tiebreaker)
# 4. Create case in cases table with source='public'
# 5. Create case_officer assignments
# 6. Update complaint status to Promoted
#
# SEVERITY MAPPING
# - Critical (Assault):           1 Inspector + 1 Sub-Inspector + 1 Head Constable
# - High (Cyber Fraud):           1 Sub-Inspector + 1 Head Constable
# - Medium (Theft, Fraud, Other): 1 Sub-Inspector + 1 Head Constable
# ─────────────────────────────────────────────────────────────────────────────

from db_connection import get_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_MAP = {
    "Assault": "Critical",
    "Cyber Fraud": "High",
    "Theft": "Medium",
    "Fraud": "Medium",
    "Other": "Medium",
}

# Officer requirements by severity
OFFICER_REQUIREMENTS = {
    "Critical": {
        "Inspector": 1,
        "Sub-Inspector": 1,
        "Head Constable": 1,
    },
    "High": {
        "Sub-Inspector": 1,
        "Head Constable": 1,
    },
    "Medium": {
        "Sub-Inspector": 1,
        "Head Constable": 1,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_dict(cursor, row):
    """Converts a DB row tuple into a dict keyed by column names."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_list(cursor, rows):
    """Converts multiple rows to list of dicts."""
    return [_row_to_dict(cursor, r) for r in rows]


def get_crime_severity(crime_type: str) -> str:
    """
    Maps crime type to severity level.
    Returns: "Critical", "High", or "Medium"
    """
    return SEVERITY_MAP.get(crime_type, "Medium")


def get_officer_workload(officer_id: int) -> int:
    """
    Returns the number of active cases assigned to an officer.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT COUNT(*)
               FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s AND c.status = 'Active'""",
            (officer_id,)
        )
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def get_available_officers_by_rank(rank: str) -> list:
    """
    Fetches all officers of a specific rank, sorted by:
    1. Fewest active cases (ascending workload)
    2. Earliest join_date (senior officers first — tiebreaker)
    
    Returns: list of officer dicts with active_cases count
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT 
                 o.officer_id,
                 o.name,
                 o.rank,
                 o.join_date,
                 COUNT(DISTINCT CASE WHEN c.status = 'Active' THEN co.case_id END) AS active_cases
               FROM officers o
               LEFT JOIN case_officer co ON o.officer_id = co.officer_id
               LEFT JOIN cases c ON co.case_id = c.case_id
               WHERE o.rank = %s
               GROUP BY o.officer_id, o.name, o.rank, o.join_date
               ORDER BY active_cases ASC, o.join_date ASC""",
            (rank,)
        )
        return _rows_to_list(cur, cur.fetchall())
    finally:
        cur.close()
        conn.close()


def select_officers_for_case(crime_type: str) -> list:
    """
    Selects the best-suited officers for a case based on crime severity.
    
    Algorithm:
    1. Determine severity level
    2. Get officer requirements by rank
    3. For each required rank, select the officer with lowest workload
    4. If no officer of that rank exists, log a warning but continue
    
    Returns: list of officer_ids selected for assignment
    """
    severity = get_crime_severity(crime_type)
    requirements = OFFICER_REQUIREMENTS.get(severity, {})
    
    selected_officers = []
    
    for rank, count_needed in requirements.items():
        available = get_available_officers_by_rank(rank)
        
        if not available:
            logger.warning(
                f"No officers available with rank '{rank}' for {crime_type} case. "
                f"Case will be assigned with fewer officers than optimal."
            )
            continue
        
        # Take the first `count_needed` officers (already sorted by workload)
        for i in range(min(count_needed, len(available))):
            selected_officers.append(available[i]["officer_id"])
    
    return selected_officers


def create_case_from_complaint(complaint_id: int, officer_ids: list) -> int:
    """
    Promotes a public complaint to a case in the cases table.
    Creates case_officer assignments for all selected officers.
    Updates public_complaints status to Promoted.
    
    Returns: case_id of the newly created case
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch the complaint details
        cur.execute(
            "SELECT * FROM public_complaints WHERE complaint_id = %s",
            (complaint_id,)
        )
        row = cur.fetchone()
        if not row:
            logger.error(f"Complaint {complaint_id} not found")
            return None
        
        complaint = _row_to_dict(cur, row)
        
        # Create the case in the cases table
        title = f"{complaint['crime_type']} - {complaint['location']}"
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode,
                complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
               VALUES (%s, %s, %s, 'Active', %s, %s, %s, %s, %s, 'public', NOW())""",
            (title, complaint["incident_desc"], complaint["crime_type"], complaint["location"],
             complaint["complaint_mode"], complaint["complainant_name"],
             complaint["contact"], complaint["aadhaar_last4"])
        )
        new_case_id = cur.lastrowid
        
        # Assign officers to the case
        for officer_id in officer_ids:
            cur.execute(
                """INSERT IGNORE INTO case_officer (case_id, officer_id)
                   VALUES (%s, %s)""",
                (new_case_id, officer_id)
            )
        
        # Mark complaint as Promoted
        # reviewed_by is set to the first officer assigned (SHO system)
        reviewed_by = officer_ids[0] if officer_ids else None
        cur.execute(
            """UPDATE public_complaints
               SET `status` = 'Promoted', promoted_case_id = %s,
                   reviewed_by = %s, reviewed_at = NOW()
               WHERE complaint_id = %s""",
            (new_case_id, reviewed_by, complaint_id)
        )
        
        conn.commit()
        return new_case_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating case from complaint {complaint_id}: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()


def process_pending_complaints() -> dict:
    """
    Main entry point for the automated assignment algorithm.
    
    Workflow:
    1. Fetch all Pending complaints from public_complaints
    2. For each complaint:
       a. Determine severity and select officers
       b. Create case and assignments
       c. Mark complaint as Promoted
    
    Returns: dict with results {processed: int, errors: int, details: list}
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch all pending complaints
        cur.execute(
            "SELECT * FROM public_complaints WHERE `status` = 'Pending' ORDER BY submitted_at ASC"
        )
        pending_complaints = _rows_to_list(cur, cur.fetchall())
        
        results = {
            "processed": 0,
            "errors": 0,
            "details": []
        }
        
        for complaint in pending_complaints:
            complaint_id = complaint["complaint_id"]
            crime_type = complaint["crime_type"]
            
            try:
                # Select officers based on crime severity
                officer_ids = select_officers_for_case(crime_type)
                
                if not officer_ids:
                    results["errors"] += 1
                    results["details"].append({
                        "complaint_id": complaint_id,
                        "status": "error",
                        "reason": "No suitable officers available"
                    })
                    logger.warning(f"Could not find suitable officers for complaint {complaint_id}")
                    continue
                
                # Create case and assignments
                case_id = create_case_from_complaint(complaint_id, officer_ids)
                
                if case_id:
                    results["processed"] += 1
                    results["details"].append({
                        "complaint_id": complaint_id,
                        "case_id": case_id,
                        "status": "success",
                        "assigned_to": officer_ids
                    })
                    logger.info(
                        f"Complaint {complaint_id} → Case {case_id} assigned to officers {officer_ids}"
                    )
                else:
                    results["errors"] += 1
                    results["details"].append({
                        "complaint_id": complaint_id,
                        "status": "error",
                        "reason": "Failed to create case"
                    })
                    logger.error(f"Failed to create case for complaint {complaint_id}")
            
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "complaint_id": complaint_id,
                    "status": "error",
                    "reason": str(e)
                })
                logger.error(f"Error processing complaint {complaint_id}: {str(e)}")
        
        return results
    finally:
        cur.close()
        conn.close()
````

## File: Backend/config.py
````python
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def _get_required_env(key):
    """Get a required environment variable or raise error if missing."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}. Please check your .env file.")
    return value

def _get_optional_env(key, default=None):
    """Get an optional environment variable with a default value."""
    return os.getenv(key, default)

# ============================================================================
# DATABASE CONFIGURATION (Required)
# ============================================================================
DB_HOST     = _get_required_env("DB_HOST")
DB_PORT     = int(_get_required_env("DB_PORT"))
DB_USER     = _get_required_env("DB_USER")
DB_PASSWORD = _get_required_env("DB_PASSWORD")
DB_NAME     = _get_required_env("DB_NAME")

# ============================================================================
# FLASK SERVER CONFIGURATION (Required)
# ============================================================================
FLASK_HOST  = _get_required_env("FLASK_HOST")
# Allow either PORT or FLASK_PORT to be set
FLASK_PORT  = int(_get_optional_env("PORT", _get_required_env("FLASK_PORT")))
FLASK_DEBUG = _get_optional_env("FLASK_DEBUG", "false").lower() == "true"

# ============================================================================
# CORS CONFIGURATION (Optional)
# ============================================================================
CORS_ORIGIN = _get_optional_env("CORS_ORIGIN", "*")

# ============================================================================
# reCAPTCHA v2 (Invisible) CONFIGURATION (Required)
# ============================================================================
# All secret/site keys must be provided via environment variables.
# These keys are critical for form security.
RECAPTCHA_SECRET_KEY = _get_required_env("RECAPTCHA_SECRET_KEY")
RECAPTCHA_PUBLIC_KEY = _get_required_env("RECAPTCHA_PUBLIC_KEY")

# ============================================================================
# reCAPTCHA SCORING (Optional - relevant for v3 only)
# ============================================================================
# Note: RECAPTCHA_THRESHOLD is only used for reCAPTCHA v3 scoring
RECAPTCHA_THRESHOLD = float(_get_optional_env("RECAPTCHA_THRESHOLD", "0.5"))
````

## File: Backend/db_connection.py
````python
# ─── CRMS Database Connection ─────────────────────────────────────────────────
# Manages a single MySQL connection pool used across the entire application.
# Every module imports `get_db` from here — never opens its own connection.

import mysql.connector
from mysql.connector import pooling
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

_pool = None

def init_pool():
    """
    Creates the connection pool on first call.
    Called once at startup from app.py.
    """
    global _pool
    _pool = pooling.MySQLConnectionPool(
        pool_name="crms_pool",
        pool_size=5,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )
    print(f"[DB] Connection pool initialised → {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def get_db():
    """
    Returns a connection from the pool.
    Callers are responsible for calling conn.close() to return it to the pool.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool() first.")
    return _pool.get_connection()
````

## File: Backend/email_utils.py
````python
# ─── CRMS Secure Email & PDF Generation Engine ───────────────────────────────
# Handles building high-resolution case dossiers in PDF format and dispatches
# notifications to citizens asynchronously.
# Features a Mock Fallback Mode for seamless offline testing.

import io
import os
import json
import logging
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import queries

logger = logging.getLogger(__name__)


def generate_case_pdf(case):
    """
    Generates a beautifully styled, professional PDF dossier for a case.
    Returns: bytes (the PDF document data)
    """
    buffer = io.BytesIO()
    
    # 1. Initialize Document Template with elegant margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # 2. Define High-End Theme Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'), # Slate 900
        alignment=1, # Center
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#64748B'), # Slate 500
        alignment=1,
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'), # Navy Blue
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'NarrativeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'), # Slate 700
        spaceAfter=8
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#475569') # Slate 600
    )
    
    meta_value_style = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    
    story = []
    
    # 3. Add Letterhead Elements
    story.append(Paragraph("BENGALURU POLICE DEPARTMENT", title_style))
    story.append(Paragraph("CYBERCRIME DIVISION &bull; CORE RECORD ARCHIVE", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Decorative line separating header
    line_table = Table([[""]], colWidths=[504])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 2, colors.HexColor('#059669')), # Emerald Accent Accent
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))
    
    # 4. Meta Information Grid
    display_id = case.get("case_id_display") or f"BLR-{str(case.get('case_id', 0)).zfill(3)}"
    reported_date_str = case.get("case_date_reported") or case.get("date_reported") or "N/A"
    try:
        dt = datetime.fromisoformat(reported_date_str)
        reported_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
        
    meta_data = [
        [
            Paragraph("Dossier Reference ID:", meta_label_style),
            Paragraph(display_id, meta_value_style),
            Paragraph("Jurisdiction Venue:", meta_label_style),
            Paragraph(case.get("case_location") or case.get("location") or "N/A", meta_value_style),
        ],
        [
            Paragraph("Crime Classification:", meta_label_style),
            Paragraph(case.get("case_crime_type") or case.get("crime_type") or "Other", meta_value_style),
            Paragraph("Record Date:", meta_label_style),
            Paragraph(reported_date_str, meta_value_style),
        ],
        [
            Paragraph("Operational Status:", meta_label_style),
            Paragraph(case.get("case_status") or case.get("status") or "Active", meta_value_style),
            Paragraph("Complainant Name:", meta_label_style),
            Paragraph(case.get("complainant_name") or "Anonymous / Guarded", meta_value_style),
        ]
    ]
    
    meta_table = Table(meta_data, colWidths=[120, 132, 110, 142])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')), # Slate 50 background
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#F1F5F9')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # 5. Incident Narrative Section
    story.append(Paragraph("I. INCIDENT NARRATIVE", h2_style))
    desc = case.get("case_description") or case.get("description") or "No further narrative logs are compiled for this case file."
    story.append(Paragraph(desc.replace("\n", "<br/>"), body_style))
    story.append(Spacer(1, 10))
    
    # 6. Official Disclaimer and Security Disclosure
    story.append(Paragraph("II. SYSTEM INTEGRITY & SECURITY DISCLOSURE", h2_style))
    disclaimer_text = (
        "This dossier record is compiled automatically from the Bengaluru Police Department's "
        "Crime Record Management System (CRMS). Access is granted strictly to the approved applicant "
        "and is subject to privacy and judicial security laws. Unauthorized replication, modification, "
        "or sharing of this document is a punishable offense under digital secrecy protocols."
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle('Disclaimer', parent=body_style, fontSize=8, leading=11, textColor=colors.HexColor('#64748B'))))
    story.append(Spacer(1, 20))
    
    # Signature Footer Table
    sig_data = [
        [
            Paragraph("Generated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), meta_value_style),
            Paragraph("<b>CRMS DIGITAL SIGNATURE</b>", ParagraphStyle('Sig', parent=meta_value_style, alignment=2))
        ]
    ]
    sig_table = Table(sig_data, colWidths=[250, 254])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(sig_table)
    
    # 7. Build Document
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def send_decision_email(request_id: int, decision: str, officer_id: int):
    """
    Assembles email content, compiles the PDF dossier (if Accepted), and either:
    1. Sends the email via SMTP (if configured).
    2. Writes a mock email and saves the PDF to `Backend/mock_emails/` (if SMTP isn't configured).
    """
    try:
        # 1. Fetch access request and case details
        request = queries.get_access_request_by_id(request_id)
        if not request:
            logger.error(f"[EMAIL ENGINE] Access request {request_id} not found.")
            return False
            
        # 2. Fetch deciding officer details
        officer = queries.get_officer_by_id(officer_id)
        officer_name = officer.get("name") if officer else "BPD Investigating Officer"
        
        display_id = request.get("case_id_display")
        requester_name = request.get("requester_name")
        requester_email = request.get("requester_email")
        
        # 3. Draft email content based on decision
        subject = ""
        body = ""
        attachment_bytes = None
        attachment_name = ""
        
        if decision.lower() == "accept" or decision.lower() == "accepted":
            subject = f"[CRMS] Secure Case Access Approved - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We are pleased to inform you that your request for access to Case {display_id} "
                f"has been approved by the investigating team.\n\n"
                f"Please find the officially generated and digitally signed case dossier details attached in the "
                f"document: {display_id}.pdf.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            # Generate the PDF attachment
            attachment_bytes = generate_case_pdf(request)
            attachment_name = f"{display_id}.pdf"
            
        else:
            subject = f"[CRMS] Secure Case Access Declined - Case {display_id}"
            body = (
                f"Dear {requester_name},\n\n"
                f"We regret to inform you that your request for access to Case {display_id} "
                f"has been declined by the investigating team at this stage.\n\n"
                f"Bengaluru Police Department Cybercrime Division is unable to grant public clearance for this dossier "
                f"due to sensitive investigation protocols.\n\n"
                f"Best regards,\n"
                f"Bengaluru Police Department CRMS Team\n"
                f"(Deciding Officer: {officer_name})"
            )
            
        # 4. Check SMTP Credentials in Environment
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "587")
        smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "adarshvh2005@gmail.com")
        smtp_from_name = os.getenv("SMTP_FROM_NAME", "Bengaluru Police CRMS Team")
        
        # Determine whether to send for real or run in Mock Mode
        is_smtp_valid = bool(smtp_user and smtp_password)
        
        if is_smtp_valid:
            logger.info(f"[EMAIL ENGINE] Attempting to send live email to {requester_email} via SMTP...")
            try:
                # Compile MIME message
                msg = MIMEMultipart()
                msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
                msg['To'] = requester_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                if attachment_bytes:
                    part = MIMEApplication(attachment_bytes, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)
                    
                # Setup Secure Connection
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, requester_email, msg.as_string())
                server.quit()
                logger.info(f"[EMAIL ENGINE] Live email successfully dispatched to {requester_email}!")
                return True
            except Exception as smtp_err:
                logger.error(f"[EMAIL ENGINE] SMTP dispatch failed: {str(smtp_err)}. Falling back to MOCK mode...")
                # Fallback to Mock Log in case of socket/credential errors
                
        # 5. Offline Fallback: Mock Developer Mode
        logger.info("[EMAIL ENGINE] Running in Mock Developer Mode (Offline)...")
        # Ensure we write inside Backend directory for convenience
        mock_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "mock_emails"
        )
        os.makedirs(mock_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email_filename = f"email_{timestamp}_req_{request_id}_{decision.lower()}.json"
        email_filepath = os.path.join(mock_dir, email_filename)
        
        # Prepare email details log
        email_log = {
            "timestamp": datetime.now().isoformat(),
            "from": f"{smtp_from_name} <{smtp_from_email}>",
            "to": requester_email,
            "subject": subject,
            "body": body,
            "attachment_provided": bool(attachment_bytes),
            "attachment_name": attachment_name
        }
        
        with open(email_filepath, 'w', encoding='utf-8') as f:
            json.dump(email_log, f, indent=4)
            
        logger.info(f"[EMAIL ENGINE] Mock email log saved: {email_filepath}")
        
        # If accepted, save the generated PDF file as well so the user can open it!
        if attachment_bytes:
            pdf_filename = f"{display_id}_{timestamp}.pdf"
            pdf_filepath = os.path.join(mock_dir, pdf_filename)
            with open(pdf_filepath, 'wb') as f:
                f.write(attachment_bytes)
            logger.info(f"[EMAIL ENGINE] Mock PDF dossier saved: {pdf_filepath}")
            
        return True
    except Exception as e:
        logger.error(f"[EMAIL ENGINE] Fatal error in email processor: {str(e)}")
        return False


def send_decision_email_async(request_id: int, decision: str, officer_id: int):
    """
    Dispatches the email sender into a separate daemon thread to prevent UI locking.
    """
    thread = threading.Thread(
        target=send_decision_email,
        args=(request_id, decision, officer_id),
        daemon=True
    )
    thread.start()
    logger.info(f"[EMAIL ENGINE] Background thread dispatched for Request ID: {request_id}")
````

## File: Backend/migrate_v2.sql
````sql
-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v2
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Additive-only migration for authentication + public complaint workflows.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing data
--
-- USAGE
-- mysql -u root -p crms < migrate_v2.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. cases
-- Add complainant verification + intake source fields
-- ═════════════════════════════════════════════════════════════════════════════

ALTER TABLE cases
    ADD COLUMN complainant_name
        VARCHAR(120)
        DEFAULT NULL,

    ADD COLUMN complainant_contact
        VARCHAR(120)
        DEFAULT NULL,

    ADD COLUMN complainant_aadhaar
        CHAR(4)
        DEFAULT NULL,

    ADD COLUMN `source`
        ENUM('public','officer')
        NOT NULL
        DEFAULT 'officer';

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. public_complaints
-- Staging table for citizen-submitted complaints
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public_complaints (

    complaint_id INT NOT NULL AUTO_INCREMENT,

    complainant_name VARCHAR(120) NOT NULL,

    contact VARCHAR(120) NOT NULL,

    email VARCHAR(120) DEFAULT NULL,

    aadhaar_last4 CHAR(4) NOT NULL,

    crime_type VARCHAR(60) NOT NULL,

    `location` VARCHAR(120) NOT NULL,

    incident_desc TEXT NOT NULL,

    complaint_mode
        ENUM('Online','Offline')
        NOT NULL
        DEFAULT 'Online',

    `status`
        ENUM('Pending','Reviewed','Promoted','Rejected')
        NOT NULL
        DEFAULT 'Pending',

    promoted_case_id INT DEFAULT NULL,

    submitted_at DATETIME
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    reviewed_by INT DEFAULT NULL,

    reviewed_at DATETIME DEFAULT NULL,

    PRIMARY KEY (complaint_id),

    CONSTRAINT fk_public_case
        FOREIGN KEY (promoted_case_id)
        REFERENCES cases(case_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_public_reviewed_by
        FOREIGN KEY (reviewed_by)
        REFERENCES officers(officer_id)
        ON DELETE SET NULL

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 4. Seed Development Passwords
--
-- Default password:
--   crms1234
--
-- NOTE:
-- Change before production deployment.
-- ═════════════════════════════════════════════════════════════════════════════

UPDATE officers
SET
    password_hash = '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO',
    `role`        = 'inspector'
WHERE `name` IN (
    'Inspector Arjun Nair',
    'Inspector Vikram Rao',
    'Inspector Meera Iyer'
);

UPDATE officers
SET
    password_hash = '$2b$12$xNpGt.x4sb44bqYlq9GElOo2nHX687qR/qCfg6E6ENBqjpqdsBnbO',
    `role`        = 'viewer'
WHERE `name` NOT IN (
    'Inspector Arjun Nair',
    'Inspector Vikram Rao',
    'Inspector Meera Iyer'
);

-- ═════════════════════════════════════════════════════════════════════════════
-- 5. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'officers columns' AS chk,
    COUNT(*)           AS has_columns
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'crms'
  AND TABLE_NAME   = 'officers'
  AND COLUMN_NAME IN ('role', 'password_hash');

SELECT
    'cases columns' AS chk,
    COUNT(*)        AS has_columns
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'crms'
  AND TABLE_NAME   = 'cases'
  AND COLUMN_NAME IN (
      'complainant_name',
      'complainant_contact',
      'complainant_aadhaar',
      'source'
  );

SELECT
    'public_complaints table' AS chk,
    COUNT(*)                  AS rows_count
FROM public_complaints;

SELECT
    officer_id,
    `name`,
    `role`,
    IF(password_hash IS NOT NULL, 'SET', 'NULL') AS password_status
FROM officers
ORDER BY officer_id;

-- ═════════════════════════════════════════════════════════════════════════════
-- Migration Complete
-- ═════════════════════════════════════════════════════════════════════════════
````

## File: Backend/migrate_v3.sql
````sql
-- ─────────────────────────────────────────────────────────────────────────────
-- CRMS Schema Migration v3
-- Bengaluru Police Department · Crime Record Management System
--
-- PURPOSE
-- Introduce case access request workflow staging table + seed developmental data.
--
-- IMPORTANT
-- - Run AFTER setup_db.sql and migrate_v2.sql
-- - Safe for MySQL 8.x
-- - Does NOT drop existing cases or officers data
--
-- USAGE
-- mysql -u root -p crms < migrate_v3.sql
-- ─────────────────────────────────────────────────────────────────────────────

USE crms;

-- ═════════════════════════════════════════════════════════════════════════════
-- 1. case_access_requests
-- Staging table for citizen-submitted case access requests
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS case_access_requests (
    request_id       INT          NOT NULL AUTO_INCREMENT,
    case_id          INT          NOT NULL,
    requester_name   VARCHAR(120) NOT NULL,
    requester_email  VARCHAR(120) NOT NULL,
    requester_number VARCHAR(20)  NOT NULL,
    reason           TEXT         NOT NULL,
    `status`         ENUM('Pending', 'Rejected', 'Accepted') NOT NULL DEFAULT 'Pending',
    requested_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by       INT          DEFAULT NULL,
    decided_at       DATETIME     DEFAULT NULL,
    
    PRIMARY KEY (request_id),
    
    CONSTRAINT fk_access_request_case
        FOREIGN KEY (case_id)
        REFERENCES cases (case_id)
        ON DELETE CASCADE,
        
    CONSTRAINT fk_access_request_officer
        FOREIGN KEY (decided_by)
        REFERENCES officers (officer_id)
        ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- ═════════════════════════════════════════════════════════════════════════════
-- 2. Seed Development Access Requests
--
-- Note: Case IDs match the seeded case IDs from setup_db.sql:
-- - Case ID 1: Cyber Fraud - Wire Transfer Scam (Assigned to Officer 1 Priya/Arjun)
-- - Case ID 2: Vehicle Theft - Swift Dzire (Assigned to Officer 2 Priya)
-- - Case ID 3: Assault at Commercial Street (Assigned to Officer 4 Deepa/Ravi)
-- ═════════════════════════════════════════════════════════════════════════════

INSERT INTO case_access_requests 
    (case_id, requester_name, requester_email, requester_number, reason, `status`, requested_at, decided_by, decided_at)
VALUES
(
    1, 
    'Arvind Swamy', 
    'arvind.swamy@example.com', 
    '+91-9845012345', 
    'Legal defense counsel representing the victim requires authorized access to full incident logs and wire transfer forensic reports.', 
    'Pending', 
    NOW() - INTERVAL 1 DAY, 
    NULL, 
    NULL
),
(
    2, 
    'Sunita Rao', 
    'sunita.rao@example.com', 
    '+91-9876543210', 
    'Journalistic enquiry regarding the swift vehicle recovery and GPS tracking efficiency of Bengaluru Police cyber cell.', 
    'Accepted', 
    NOW() - INTERVAL 3 DAY, 
    1, 
    NOW() - INTERVAL 2 DAY
),
(
    3, 
    'Unknown Client', 
    'unknown@privacy.io', 
    '+91-9000000000', 
    'Requests detailed dossier of commercial street altercation logs for private arbitration services.', 
    'Rejected', 
    NOW() - INTERVAL 5 DAY, 
    4, 
    NOW() - INTERVAL 4 DAY
);

-- ═════════════════════════════════════════════════════════════════════════════
-- 3. Verification Queries
-- ═════════════════════════════════════════════════════════════════════════════

SELECT
    'case_access_requests table' AS chk,
    COUNT(*)                     AS rows_count
FROM case_access_requests;

SELECT 
    request_id,
    case_id,
    requester_name,
    `status`
FROM case_access_requests;
````

## File: Backend/queries.py
````python
# ─── CRMS SQL Query Layer ──────────────────────────────────────────────────────
# All raw SQL lives here. app.py never constructs SQL directly.
# Every function opens its own connection, executes, commits if needed, and closes.

from db_connection import get_db
import bcrypt

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _row_to_dict(cursor, row):
    """Converts a DB row tuple into a dict keyed by column names."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_list(cursor, rows):
    return [_row_to_dict(cursor, r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# CASES
# ──────────────────────────────────────────────────────────────────────────────

def get_all_cases(status=None, crime_type=None, location=None, search=None, officer_id=None, bypass_visibility=False):
    """
    Returns all cases, optionally filtered.
    If bypass_visibility is False and officer_id is provided, returns only cases assigned to that officer.
    Also attaches the list of officer_ids for each case (from case_officer).
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql    = "SELECT * FROM cases WHERE 1=1"
        params = []

        if not bypass_visibility and officer_id is not None:
            sql += " AND case_id IN (SELECT case_id FROM case_officer WHERE officer_id = %s)"
            params.append(officer_id)

        if status and status != "All":
            sql += " AND `status` = %s"
            params.append(status)

        if crime_type and crime_type != "All":
            sql += " AND crime_type = %s"
            params.append(crime_type)

        if location:
            sql += " AND `location` LIKE %s"
            params.append(f"%{location}%")

        if search:
            sql += " AND (title LIKE %s OR `location` LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        sql += " ORDER BY date_reported DESC"

        cur.execute(sql, params)
        cases = _rows_to_list(cur, cur.fetchall())

        # Attach officer_ids list to every case
        for case in cases:
            cur.execute(
                "SELECT officer_id FROM case_officer WHERE case_id = %s",
                (case["case_id"],)
            )
            case["officer_ids"] = [r[0] for r in cur.fetchall()]

            # Serialise date/datetime fields to strings for JSON
            for key in ("date_reported", "last_updated"):
                if case.get(key) and hasattr(case[key], "isoformat"):
                    case[key] = case[key].isoformat()

        return cases
    finally:
        cur.close()
        conn.close()


def get_case_by_id(case_id):
    """Returns a single case with its officer_ids, or None if not found."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM cases WHERE case_id = %s", (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        case = _row_to_dict(cur, row)

        cur.execute(
            "SELECT officer_id FROM case_officer WHERE case_id = %s", (case_id,)
        )
        case["officer_ids"] = [r[0] for r in cur.fetchall()]

        for key in ("date_reported", "last_updated"):
            if case.get(key) and hasattr(case[key], "isoformat"):
                case[key] = case[key].isoformat()

        return case
    finally:
        cur.close()
        conn.close()


def insert_case(title, description, crime_type, status, location, complaint_mode,
               complainant_name=None, complainant_contact=None,
               complainant_aadhaar=None, source="officer"):
    """Inserts a new case and returns its new case_id."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode,
                complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (title, description, crime_type, status, location, complaint_mode,
             complainant_name, complainant_contact, complainant_aadhaar, source)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


# Columns in `cases` that are MySQL reserved words and need backtick-quoting
_RESERVED = {"status", "location"}

def update_case(case_id, fields: dict):
    """
    Updates any subset of case fields.
    `fields` is a dict like {"status": "Solved"} or {"title": "...", "location": "..."}.
    Always bumps last_updated via MySQL NOW().
    Reserved column names (status, location) are backtick-quoted automatically.
    """
    if not fields:
        return 0

    allowed = {"title", "description", "crime_type", "status", "location", "complaint_mode"}
    safe    = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return 0

    # Build SET clause — backtick-quote reserved words, always append last_updated = NOW()
    set_parts = []
    params    = []
    for k, v in safe.items():
        col = f"`{k}`" if k in _RESERVED else k
        set_parts.append(f"{col} = %s")
        params.append(v)
    set_parts.append("last_updated = NOW()")
    set_clause = ", ".join(set_parts)
    params.append(case_id)

    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(f"UPDATE cases SET {set_clause} WHERE case_id = %s", params)
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def delete_case(case_id):
    """
    Hard-deletes a case and its case_officer assignments.
    Frontend calls this only for P1 users.
    Prefer update_case(case_id, {"status": "Closed"}) in most workflows.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Remove assignments first (FK constraint)
        cur.execute("DELETE FROM case_officer WHERE case_id = %s", (case_id,))
        cur.execute("DELETE FROM cases WHERE case_id = %s", (case_id,))
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# OFFICERS
# ──────────────────────────────────────────────────────────────────────────────

def get_all_officers():
    """
    Returns all officers with computed active_cases and solved_cases counts
    so the frontend Analytics workload bar renders correctly.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM officers ORDER BY officer_id")
        officers = _rows_to_list(cur, cur.fetchall())

        for officer in officers:
            oid = officer["officer_id"]

            cur.execute(
                """SELECT COUNT(*) FROM case_officer co
                   JOIN cases c ON co.case_id = c.case_id
                   WHERE co.officer_id = %s AND c.status = 'Active'""",
                (oid,)
            )
            officer["active_cases"] = cur.fetchone()[0]

            cur.execute(
                """SELECT COUNT(*) FROM case_officer co
                   JOIN cases c ON co.case_id = c.case_id
                   WHERE co.officer_id = %s AND c.status = 'Solved'""",
                (oid,)
            )
            officer["solved_cases"] = cur.fetchone()[0]

            # Add extras the frontend officer modal shows.
            # These columns may not exist in the minimal schema — supply defaults if absent.
            officer.setdefault("badge",      f"BPD-{1000 + oid}")
            officer.setdefault("station",    "Bengaluru City Police")
            officer.setdefault("phone",      "")
            officer.setdefault("email",      "")
            officer.setdefault("join_date",  "")

        for o in officers:
            o.pop("password_hash", None)   # never send hash to frontend

        return officers
    finally:
        cur.close()
        conn.close()


def get_officer_by_id(officer_id):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM officers WHERE officer_id = %s", (officer_id,))
        row = cur.fetchone()
        if not row:
            return None
        o = _row_to_dict(cur, row)
        o.pop("password_hash", None)
        return o
    finally:
        cur.close()
        conn.close()


def insert_officer(name, rank):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO officers (`name`, `rank`) VALUES (%s, %s)",
            (name, rank)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# ASSIGNMENTS  (case_officer junction)
# ──────────────────────────────────────────────────────────────────────────────

def assign_officer(case_id, officer_id):
    """Inserts a case–officer assignment. Silently ignores duplicate."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT IGNORE INTO case_officer (case_id, officer_id)
               VALUES (%s, %s)""",
            (case_id, officer_id)
        )
        conn.commit()
        return cur.rowcount   # 1 = inserted, 0 = already existed
    finally:
        cur.close()
        conn.close()


def unassign_officer(case_id, officer_id):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM case_officer WHERE case_id = %s AND officer_id = %s",
            (case_id, officer_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def get_all_assignments():
    """
    JOIN query across all three tables.
    Returns one row per case–officer pair — exactly what the Assignments view needs.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT
                 c.case_id,
                 c.title       AS case_title,
                 c.crime_type,
                 c.status,
                 c.location,
                 o.officer_id,
                 o.`name`      AS officer_name,
                 o.`rank`      AS officer_rank
               FROM case_officer co
               JOIN cases    c ON co.case_id    = c.case_id
               JOIN officers o ON co.officer_id = o.officer_id
               ORDER BY c.case_id, o.officer_id"""
        )
        return _rows_to_list(cur, cur.fetchall())
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────

def get_analytics():
    """
    Aggregates used by the Analytics tab:
      - crime_type distribution
      - status distribution
      - monthly counts (last 6 months)
      - location distribution (top 8)
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Crime type distribution
        cur.execute(
            "SELECT crime_type, COUNT(*) AS cnt FROM cases GROUP BY crime_type ORDER BY cnt DESC"
        )
        crime_dist = [{"crime_type": r[0], "count": r[1]} for r in cur.fetchall()]

        # Status distribution
        cur.execute(
            "SELECT `status`, COUNT(*) AS cnt FROM cases GROUP BY `status`"
        )
        status_dist = [{"status": r[0], "count": r[1]} for r in cur.fetchall()]

        # Monthly counts — last 6 months
        cur.execute(
            """SELECT DATE_FORMAT(date_reported, '%b') AS month,
                      MONTH(date_reported)             AS month_num,
                      COUNT(*)                          AS cnt
               FROM cases
               WHERE date_reported >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
               GROUP BY month, month_num
               ORDER BY month_num"""
        )
        monthly = [{"month": r[0], "count": r[2]} for r in cur.fetchall()]

        # Location distribution (top 8)
        cur.execute(
            """SELECT `location`, COUNT(*) AS cnt
               FROM cases
               GROUP BY `location`
               ORDER BY cnt DESC
               LIMIT 8"""
        )
        location_dist = [{"location": r[0], "count": r[1]} for r in cur.fetchall()]

        return {
            "crime_distribution":  crime_dist,
            "status_distribution": status_dist,
            "monthly_trends":      monthly,
            "location_distribution": location_dist,
        }
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC PORTAL — complaint + access request
# ──────────────────────────────────────────────────────────────────────────────

def submit_public_complaint(name, contact, email, aadhaar_last4,
                             crime_type, location, complaint_mode, incident_desc):
    """
    Inserts a citizen complaint into the public_complaints staging table.
    Officers then review and promote to the main cases table.
    Returns the new complaint_id as the citizen's reference number.

    aadhaar_last4: last 4 digits of Aadhaar for basic identity anchoring.
    Never store the full Aadhaar — validate the format before calling this.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO public_complaints
               (complainant_name, contact, email, aadhaar_last4,
                crime_type, `location`, incident_desc, complaint_mode)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (name, contact, email or "", aadhaar_last4,
             crime_type or "Other", location or "",
             incident_desc or "", complaint_mode or "Online")
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def get_public_complaints(status=None):
    """Returns all public complaints (for officer review dashboard)."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = "SELECT * FROM public_complaints WHERE 1=1"
        params = []
        if status:
            sql += " AND `status` = %s"
            params.append(status)
        sql += " ORDER BY submitted_at DESC"
        cur.execute(sql, params)
        rows = _rows_to_list(cur, cur.fetchall())
        for r in rows:
            for key in ("submitted_at", "reviewed_at"):
                if r.get(key) and hasattr(r[key], "isoformat"):
                    r[key] = r[key].isoformat()
        return rows
    finally:
        cur.close()
        conn.close()


def promote_complaint(complaint_id, officer_id):
    """
    Promotes a public_complaint to a full case in the cases table.
    Marks the complaint as Promoted and links the generated case_id back.
    Returns the new case_id.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM public_complaints WHERE complaint_id = %s", (complaint_id,))
        row = cur.fetchone()
        if not row:
            return None
        pc = _row_to_dict(cur, row)

        title = f"{pc['crime_type']} - {pc['location']}"
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode,
                complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
               VALUES (%s, %s, %s, 'Active', %s, %s, %s, %s, %s, 'public', NOW())""",
            (title, pc["incident_desc"], pc["crime_type"], pc["location"],
             pc["complaint_mode"], pc["complainant_name"], pc["contact"], pc["aadhaar_last4"])
        )
        new_case_id = cur.lastrowid

        cur.execute(
            """UPDATE public_complaints
               SET `status` = 'Promoted', promoted_case_id = %s,
                   reviewed_by = %s, reviewed_at = NOW()
               WHERE complaint_id = %s""",
            (new_case_id, officer_id, complaint_id)
        )
        conn.commit()
        return new_case_id
    finally:
        cur.close()
        conn.close()


def reject_complaint(complaint_id, officer_id):
    """Marks a public complaint as Rejected."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """UPDATE public_complaints
               SET `status` = 'Rejected', reviewed_by = %s, reviewed_at = NOW()
               WHERE complaint_id = %s""",
            (officer_id, complaint_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def get_officer_by_badge(badge: str):
    """
    Looks up an officer by their badge ID.
    Returns the complete officer dictionary (including password_hash) or None if not found.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT * FROM officers WHERE badge = %s LIMIT 1", (badge,))
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(cur, row)
    finally:
        cur.close()
        conn.close()


def enrich_officer_details(o: dict):
    """Fills in computed case counts and default details for an officer dict."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        oid = o["officer_id"]
        cur.execute(
            """SELECT COUNT(*) FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s AND c.`status` = 'Active'""",
            (oid,)
        )
        o["active_cases"] = cur.fetchone()[0]

        cur.execute(
            """SELECT COUNT(*) FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s AND c.`status` = 'Solved'""",
            (oid,)
        )
        o["solved_cases"] = cur.fetchone()[0]

        # Supply defaults if absent
        o.setdefault("badge",      f"BPD-{1000 + oid}")
        o.setdefault("station",    "Bengaluru City Police")
        o.setdefault("phone",      "")
        o.setdefault("email",      "")
        o.setdefault("join_date",  "")

        return o
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────────────────

def verify_officer_login(badge_or_name: str, plain_password: str):
    """
    Verifies officer credentials. Accepts badge number or officer name.
    Returns the officer dict (without password_hash) on success, None on failure.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Try badge first, then name
        cur.execute(
            "SELECT * FROM officers WHERE badge = %s OR `name` = %s LIMIT 1",
            (badge_or_name, badge_or_name)
        )
        row = cur.fetchone()
        if not row:
            return None
        o = _row_to_dict(cur, row)

        stored_hash = o.pop("password_hash", None)
        if not stored_hash:
            return None

        if not bcrypt.checkpw(plain_password.encode(), stored_hash.encode()):
            return None

        # Attach computed case counts
        oid = o["officer_id"]
        cur.execute(
            """SELECT COUNT(*) FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s AND c.`status` = 'Active'""",
            (oid,)
        )
        o["active_cases"] = cur.fetchone()[0]
        cur.execute(
            """SELECT COUNT(*) FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s AND c.`status` = 'Solved'""",
            (oid,)
        )
        o["solved_cases"] = cur.fetchone()[0]

        return o   # role is included; frontend uses it to gate write actions
    finally:
        cur.close()
        conn.close()


def set_officer_password(officer_id: int, plain_password: str):
    """Hashes and stores a new password for an officer."""
    hashed = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "UPDATE officers SET password_hash = %s WHERE officer_id = %s",
            (hashed, officer_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# STATS — landing page strip
# ──────────────────────────────────────────────────────────────────────────────

def get_public_stats():
    """
    Aggregates for the public landing page stats strip.
    Returns real counts from the DB — replaces the hardcoded 142 / 89 / 3847 values.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM cases WHERE `status` = 'Active'")
        active_cases = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM cases WHERE `status` = 'Solved'")
        solved_cases = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM officers")
        total_officers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM cases WHERE crime_type = 'Cyber Fraud'")
        cyber_cases = cur.fetchone()[0]

        return {
            "active_cases":   active_cases,
            "solved_cases":   solved_cases,
            "total_officers": total_officers,
            "cyber_cases":    cyber_cases,
        }
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC ACCESS REQUESTS
# ──────────────────────────────────────────────────────────────────────────────

def submit_case_access_request(case_id: int, requester_name: str, requester_email: str, requester_number: str, reason: str):
    """
    Submits a new case access request into case_access_requests staging table.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO case_access_requests
               (case_id, requester_name, requester_email, requester_number, reason, `status`)
               VALUES (%s, %s, %s, %s, %s, 'Pending')""",
            (case_id, requester_name, requester_email, requester_number, reason)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def get_case_access_requests(officer_id: int = None, bypass_visibility: bool = False):
    """
    Fetches all access requests from the DB, with role-based visibility.
    If bypass_visibility is False and officer_id is provided, returns only requests 
    for cases where the officer is assigned.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = """
            SELECT ar.*, c.title AS case_title, c.crime_type AS case_crime_type, c.status AS case_status,
                   o.name AS decided_by_name
            FROM case_access_requests ar
            JOIN cases c ON ar.case_id = c.case_id
            LEFT JOIN officers o ON ar.decided_by = o.officer_id
        """
        params = []
        
        if not bypass_visibility and officer_id is not None:
            sql += " WHERE ar.case_id IN (SELECT case_id FROM case_officer WHERE officer_id = %s)"
            params.append(officer_id)
            
        sql += " ORDER BY ar.requested_at DESC"
        
        cur.execute(sql, params)
        rows = _rows_to_list(cur, cur.fetchall())
        
        for r in rows:
            # Serialise datetime fields for JSON compatibility
            for key in ("requested_at", "decided_at"):
                if r.get(key) and hasattr(r[key], "isoformat"):
                    r[key] = r[key].isoformat()
            # Attach computed display case ID
            r["case_id_display"] = f"BLR-{str(r['case_id']).zfill(3)}"
            
        return rows
    finally:
        cur.close()
        conn.close()


def officer_is_assigned_to_case(officer_id: int, case_id: int) -> bool:
    """Returns True if the officer is assigned to the given case."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM case_officer WHERE officer_id = %s AND case_id = %s LIMIT 1",
            (officer_id, case_id),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def update_access_request_status(request_id: int, status: str, decided_by: int):
    """
    Updates status of an access request and registers the deciding officer.
    Only transitions from Pending — returns 0 if already processed.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """UPDATE case_access_requests
               SET `status` = %s, decided_by = %s, decided_at = NOW()
               WHERE request_id = %s AND `status` = 'Pending'""",
            (status, decided_by, request_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def get_access_request_by_id(request_id: int):
    """
    Retrieves a single access request by ID.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT ar.*, c.title AS case_title, c.crime_type AS case_crime_type, 
                      c.status AS case_status, c.description AS case_description,
                      c.location AS case_location, c.date_reported AS case_date_reported
               FROM case_access_requests ar
               JOIN cases c ON ar.case_id = c.case_id
               WHERE ar.request_id = %s""",
            (request_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        r = _row_to_dict(cur, row)
        
        for key in ("requested_at", "decided_at", "case_date_reported"):
            if r.get(key) and hasattr(r[key], "isoformat"):
                r[key] = r[key].isoformat()
                
        r["case_id_display"] = f"BLR-{str(r['case_id']).zfill(3)}"
        return r
    finally:
        cur.close()
        conn.close()
````

## File: Backend/setup_db.sql
````sql
-- ─── CRMS MySQL Setup ──────────────────────────────────────────────────────
-- Run once to create the schema and seed demo data.
-- Usage: mysql -u adarsh -p < setup_db.sql

CREATE DATABASE IF NOT EXISTS crms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE crms;

-- ─── DROP EXISTING TABLES (clean slate) ───────────────────────────────────────

DROP TABLE IF EXISTS case_officer;
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS officers;

-- ─── TABLE: officers ──────────────────────────────────────────────────────────
-- `rank` and `name` are reserved words in MySQL 8 — must be backtick-quoted.

CREATE TABLE officers (
    officer_id  INT          NOT NULL AUTO_INCREMENT,
    `name`      VARCHAR(120) NOT NULL,
    `rank`      VARCHAR(80)  NOT NULL,
    badge       VARCHAR(20)  DEFAULT NULL,
    station     VARCHAR(120) DEFAULT NULL,
    phone       VARCHAR(20)  DEFAULT NULL,
    email       VARCHAR(120) DEFAULT NULL,
    join_date   DATE         DEFAULT NULL,
    PRIMARY KEY (officer_id)
) ENGINE=InnoDB;

-- ─── TABLE: cases ─────────────────────────────────────────────────────────────
-- `status` and `location` are reserved in some MySQL versions — backtick-quoted.

CREATE TABLE cases (
    case_id        INT          NOT NULL AUTO_INCREMENT,
    title          VARCHAR(255) NOT NULL,
    description    TEXT,
    crime_type     VARCHAR(60)  NOT NULL,
    `status`       ENUM('Active','Solved','Closed') NOT NULL DEFAULT 'Active',
    date_reported  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `location`     VARCHAR(120) NOT NULL,
    complaint_mode ENUM('Online','Offline')         NOT NULL DEFAULT 'Online',
    last_updated   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (case_id)
) ENGINE=InnoDB;

-- ─── TABLE: case_officer (junction) ───────────────────────────────────────────

CREATE TABLE case_officer (
    case_id    INT NOT NULL,
    officer_id INT NOT NULL,
    PRIMARY KEY (case_id, officer_id),
    FOREIGN KEY (case_id)    REFERENCES cases    (case_id)    ON DELETE CASCADE,
    FOREIGN KEY (officer_id) REFERENCES officers (officer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─── SEED: officers ───────────────────────────────────────────────────────────

INSERT INTO officers (`name`, `rank`, badge, station, phone, email, join_date) VALUES
('Inspector Arjun Nair',        'Inspector',      'BPD-7821', 'Cyber Crime Division',  '+91-80-2294-2101', 'arjun.nair@bpd.gov.in',     '2018-03-15'),
('Sub-Inspector Priya Menon',   'Sub-Inspector',  'BPD-6543', 'Whitefield PS',          '+91-80-2845-6789', 'priya.menon@bpd.gov.in',    '2019-07-22'),
('Inspector Vikram Rao',        'Inspector',      'BPD-8912', 'Cyber Crime Division',  '+91-80-2294-2102', 'vikram.rao@bpd.gov.in',     '2017-11-08'),
('Sub-Inspector Deepa Krishnan','Sub-Inspector',  'BPD-5432', 'HSR Layout PS',          '+91-80-2572-3456', 'deepa.krishnan@bpd.gov.in', '2020-01-14'),
('Constable Ravi Kumar',        'Head Constable', 'BPD-3210', 'Commercial Street PS',   '+91-80-2558-9012', 'ravi.kumar@bpd.gov.in',     '2021-05-30'),
('Inspector Meera Iyer',        'Inspector',      'BPD-7654', 'Economic Offences Wing', '+91-80-2221-4567', 'meera.iyer@bpd.gov.in',     '2016-09-03'),
('Sub-Inspector Karthik S',     'Sub-Inspector',  'BPD-4321', 'Cyber Crime Division',  '+91-80-2294-2103', 'karthik.s@bpd.gov.in',      '2019-04-11');

-- ─── SEED: cases ──────────────────────────────────────────────────────────────

INSERT INTO cases (title, description, crime_type, `status`, date_reported, `location`, complaint_mode) VALUES
(
  'Cyber Fraud - Wire Transfer Scam',
  'Victim received fraudulent email impersonating bank official. Rs 12.5L transferred to unknown account. Digital forensics underway.',
  'Cyber Fraud', 'Active', '2026-04-12', 'Koramangala', 'Online'
),
(
  'Vehicle Theft - Swift Dzire',
  'Vehicle stolen from residential parking. Recovered via GPS tracking in Electronic City. Two suspects apprehended.',
  'Theft', 'Solved', '2026-03-28', 'Whitefield', 'Offline'
),
(
  'Assault at Commercial Street',
  'Physical altercation between shop owners. Victim sustained head injuries. CCTV footage obtained. Investigation ongoing.',
  'Assault', 'Active', '2026-04-15', 'Commercial Street', 'Offline'
),
(
  'Real Estate Fraud - Land Document Forgery',
  'Forged land sale deed used to transfer property worth Rs 3.2Cr. Forensic document analysis in progress.',
  'Fraud', 'Active', '2026-04-10', 'Jayanagar', 'Online'
),
(
  'ATM Card Skimming Ring',
  'Multi-city ATM skimming operation dismantled. 47 cloned cards recovered. Rs 8.7L fraud prevented.',
  'Cyber Fraud', 'Solved', '2026-03-05', 'MG Road', 'Online'
),
(
  'Jewelry Heist - Commercial District',
  'Armed robbery at jewelry store. Rs 45L worth of gold ornaments stolen. Case closed after recovery.',
  'Theft', 'Closed', '2026-02-18', 'Commercial Street', 'Offline'
),
(
  'Domestic Violence Report',
  'Multiple domestic violence complaints filed. Protection order issued. Counseling services engaged.',
  'Assault', 'Active', '2026-04-18', 'HSR Layout', 'Online'
),
(
  'Investment Ponzi Scheme',
  'Fraudulent investment scheme targeting retirees. Rs 1.8Cr collected from 34 victims. Financial forensics active.',
  'Fraud', 'Active', '2026-04-08', 'Indiranagar', 'Online'
),
(
  'Data Breach - Fintech Company',
  'Unauthorized database access exposing 2.3M user records. Cyber cell engaged. Server logs under analysis.',
  'Cyber Fraud', 'Active', '2026-04-20', 'Manyata Tech Park', 'Online'
),
(
  'Street Robbery - Mobile Snatching',
  'Motorcycle-mounted snatching. Victim resisted, sustained minor injuries. Suspects identified via CCTV.',
  'Theft', 'Solved', '2026-03-22', 'Brigade Road', 'Offline'
);

-- ─── SEED: case_officer ───────────────────────────────────────────────────────

INSERT INTO case_officer VALUES (1, 1), (1, 3);
INSERT INTO case_officer VALUES (2, 2);
INSERT INTO case_officer VALUES (3, 4), (3, 5);
INSERT INTO case_officer VALUES (4, 1), (4, 6);
INSERT INTO case_officer VALUES (5, 3), (5, 7);
INSERT INTO case_officer VALUES (6, 2), (6, 5);
INSERT INTO case_officer VALUES (7, 4);
INSERT INTO case_officer VALUES (8, 6), (8, 7);
INSERT INTO case_officer VALUES (9, 1), (9, 3), (9, 7);
INSERT INTO case_officer VALUES (10, 2), (10, 5);

-- ─── VERIFY ───────────────────────────────────────────────────────────────────

SELECT 'officers'    AS tbl, COUNT(*) AS `rows` FROM officers
UNION ALL
SELECT 'cases',             COUNT(*)                    FROM cases
UNION ALL
SELECT 'case_officer',      COUNT(*)                    FROM case_officer;
````

## File: Frontend/crms_frontend.html
````html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRMS — Bengaluru Police Intelligence Command</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/framer-motion@10.16.4/dist/framer-motion.js"></script>
    <script>
        (function(){
            const isLocalhost = location.hostname === "localhost" || location.hostname === "127.0.0.1";
            const devSiteKey = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"; // Google test site key (v2 Invisible)
            const prodSiteKey = "6LfLCfIsAAAAAK4ZwH_RMmvAPAi3vtkGKPLAYkuk"; // Your site key (v2 Invisible)
            const siteKey = isLocalhost ? devSiteKey : prodSiteKey;
            console.log("[reCAPTCHA] Loading reCAPTCHA v2 (Invisible) with site key:", siteKey.substring(0, 10) + "...");
            window._recaptcha_site_key = siteKey;
            const s = document.createElement('script');
            s.src = 'https://www.google.com/recaptcha/api.js';
            s.async = true; s.defer = true;
            s.onload = () => console.log("[reCAPTCHA] v2 Script loaded successfully");
            s.onerror = () => console.error("[reCAPTCHA] Failed to load reCAPTCHA script");
            document.head.appendChild(s);
        })();
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        'space': ['Space Grotesk', 'sans-serif'],
                        'inter': ['Inter', 'sans-serif'],
                    },
                    colors: {
                        'accent': '#5E0ED7',
                        'obsidian': '#070c1e',      // Majestic deep midnight indigo
                        'void': '#0b1129',          // Enigmatic dark navy
                        'abyss': '#0f1737',         // Tech-noir dark navy-blue
                        'slate-deep': '#141d45',
                        'slate-mid': '#1b2658',
                        'slate-light': '#243270',
                        'cyan-glow': '#ff9933',     // Indian Saffron (energy, courage, authority)
                        'cyan-dim': '#f97316',      // Deep warm Saffron
                        'blue-electric': '#2563eb', // Ashoka Blue
                        'blue-glow': '#3b82f6',     // Chakra Blue
                        'purple-tactical': '#a855f7', 
                        'purple-glow': '#c084fc',
                        'red-warn': '#ef4444',
                        'red-dim': '#b91c1c',
                        'amber-warn': '#ff9933',
                        'green-tactical': '#10b981', // Indian Tricolor Emerald Green (peace and growth)
                        'green-dim': '#059669',
                    }
                }
            }
        }
    </script>
    <style>
        * { scrollbar-width: thin; scrollbar-color: rgba(255,153,51,0.18) transparent; }
        *::-webkit-scrollbar { width: 4px; }
        *::-webkit-scrollbar-track { background: transparent; }
        *::-webkit-scrollbar-thumb { background: rgba(255,153,51,0.18); border-radius: 4px; }
        body { background: #070c1e; color: #e5e7eb; font-family: 'Inter', sans-serif; overflow-x: hidden; }
        .glass-panel {
            background: rgba(255,255,255,0.02);
            backdrop-filter: blur(24px) saturate(140%);
            -webkit-backdrop-filter: blur(24px) saturate(140%);
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
        }
        .glass-panel-strong {
            background: rgba(255,255,255,0.035);
            backdrop-filter: blur(32px) saturate(160%);
            -webkit-backdrop-filter: blur(32px) saturate(160%);
            border: 1px solid rgba(255,255,255,0.07);
            box-shadow: 0 12px 48px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
        }
        .glow-cyan { box-shadow: 0 0 20px rgba(255,153,51,0.18), 0 0 60px rgba(255,153,51,0.06); }
        .glow-blue { box-shadow: 0 0 20px rgba(59,130,246,0.12), 0 0 60px rgba(59,130,246,0.04); }
        .glow-purple { box-shadow: 0 0 20px rgba(168,85,247,0.12), 0 0 60px rgba(168,85,247,0.04); }
        .glow-green { box-shadow: 0 0 20px rgba(16,185,129,0.12), 0 0 60px rgba(16,185,129,0.04); }
        .text-glow-cyan { text-shadow: 0 0 20px rgba(255,153,51,0.45), 0 0 40px rgba(255,153,51,0.15); }
        .text-glow-blue { text-shadow: 0 0 20px rgba(59,130,246,0.4), 0 0 40px rgba(59,130,246,0.15); }
        .text-glow-purple { text-shadow: 0 0 20px rgba(168,85,247,0.4), 0 0 40px rgba(168,85,247,0.15); }
        .pulse-dot { animation: pulse-glow 2s ease-in-out infinite; }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 4px currentColor, 0 0 12px currentColor; opacity: 1; }
            50% { box-shadow: 0 0 8px currentColor, 0 0 24px currentColor; opacity: 0.7; }
        }
        .scan-line {
            position: absolute; top: 0; left: 0; right: 0; height: 1px;
            background: rgba(255,153,51,0.3);
            animation: scan 4s linear infinite;
            pointer-events: none;
        }
        @keyframes scan {
            0% { top: 0; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
        .grid-bg {
            background-image: 
                linear-gradient(rgba(255,153,51,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,153,51,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
        }
        .radial-glow {
            background: radial-gradient(ellipse at 50% 0%, rgba(255,153,51,0.08) 0%, transparent 60%),
                        radial-gradient(ellipse at 50% 100%, rgba(16,185,129,0.04) 0%, transparent 60%);
        }
        .noise-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
            pointer-events: none; z-index: 9999; opacity: 0.4;
        }
        .particle { position: absolute; border-radius: 50%; pointer-events: none; }
        .card-hover { transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }
        .card-hover:hover {
            transform: translateY(-4px) scale(1.01);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 40px rgba(255,153,51,0.06);
            border-color: rgba(255,153,51,0.15);
        }
        .input-glow:focus {
            outline: none;
            border-color: rgba(255,153,51,0.3);
            box-shadow: 0 0 20px rgba(255,153,51,0.08);
        }
        .btn-primary {
            background: rgba(255,153,51,0.1);
            border: 1px solid rgba(255,153,51,0.25);
            color: #ff9933;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            background: rgba(255,153,51,0.2);
            border-color: rgba(255,153,51,0.5);
            box-shadow: 0 0 30px rgba(255,153,51,0.15);
        }
        .btn-danger {
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.25);
            color: #ef4444;
            transition: all 0.3s ease;
        }
        .btn-danger:hover {
            background: rgba(239,68,68,0.2);
            border-color: rgba(239,68,68,0.5);
            box-shadow: 0 0 30px rgba(239,68,68,0.15);
        }
        .nav-tab {
            position: relative;
            transition: all 0.3s ease;
        }
        .nav-tab::after {
            content: '';
            position: absolute; bottom: -2px; left: 50%; right: 50%; height: 2px;
            background: #ff9933;
            transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(255,153,51,0.5);
        }
        .nav-tab:hover::after, .nav-tab.active::after {
            left: 0; right: 0;
        }
        .nav-tab.active { color: #ff9933; text-shadow: 0 0 10px rgba(255,153,51,0.3); }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-float { animation: float 6s ease-in-out infinite; }
        .animate-fade-up { animation: fadeUp 0.6s ease-out forwards; opacity: 0; }
        .metric-value { font-variant-numeric: tabular-nums; }
        .hex-bg {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='49' viewBox='0 0 28 49'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%23ff9933' fill-opacity='0.02'%3E%3Cpath d='M13.99 9.25l13 7.5v15l-13 7.5L1 31.75v-15l12.99-7.5zM3 17.9v12.7l10.99 6.34 11-6.35V17.9l-11-6.34L3 17.9zM0 15l12.98-7.5V0h-2v6.35L0 12.69v2.3zm0 18.5L12.98 41v8h-2v-6.85L0 35.81v-2.3zM15 0v7.5L27.99 15H28v-2.31h-.01L17 6.35V0h-2zm0 49v-8l12.99-7.5H28v2.31h-.01L17 42.15V49h-2z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        }
        .ashoka-watermark {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 600px;
            height: 600px;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' width='600' height='600'%3E%3Ccircle cx='100' cy='100' r='90' fill='none' stroke='%233b82f6' stroke-width='1.2' stroke-opacity='0.015'/%3E%3Ccircle cx='100' cy='100' r='20' fill='none' stroke='%233b82f6' stroke-width='1.2' stroke-opacity='0.015'/%3E%3Cg stroke='%233b82f6' stroke-width='0.6' stroke-opacity='0.015'%3E%3Cpath d='M100 10v180M10 100h180M36.36 36.36l127.28 127.28M36.36 163.64L163.64 36.36'/%3E%3Cpath d='M100 100L82.68 15.68M100 100l17.32-84.32M100 100L15.68 82.68M100 100l84.32 17.32M100 100l82.68-17.32M100 100l-17.32 84.32M100 100l-84.32-17.32M100 100l17.32 84.32'/%3E%3Cpath d='M100 100l-45-77.94M100 100l45 77.94M100 100l-77.94 45M100 100l77.94-45M100 100l-45 77.94M100 100l45-77.94M100 100l-77.94-45M100 100l77.94 45'/%3E%3C/g%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: center;
            pointer-events: none;
            z-index: 0;
        }
        body.landing-hero .ashoka-watermark,
        body.landing-hero .noise-overlay { display: none; }
        .landing-hero-text { color: #000; font-family: 'Inter', sans-serif; }
        @keyframes crms-spin-slow {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .crms-spin-orb {
            animation: crms-spin-slow 28s linear infinite;
            pointer-events: none;
        }
        .crms-input:focus {
            outline: none;
            box-shadow: 0 0 0 3px rgba(94, 14, 215, 0.2);
        }
    </style>
</head>
<body class="bg-obsidian min-h-screen">
    <div class="ashoka-watermark"></div>
    <div class="noise-overlay"></div>
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect, useRef, useMemo } = React;
        const { motion, AnimatePresence } = window.Motion;

        // ─── API CONFIG ───────────────────────────────────────────────────────
        // Change this to match where your Flask server is running.
        const API_BASE = "http://localhost:5000";
        
        // reCAPTCHA v2 (Invisible) Configuration
        const RECAPTCHA_PUBLIC_KEY = window._recaptcha_site_key || "6LfLCfIsAAAAAK4ZwH_RMmvAPAi3vtkGKPLAYkuk";

        // Generic fetch helper — returns parsed JSON or throws with a readable message.
        const apiFetch = async (path, options = {}) => {
            const { headers, ...rest } = options;
            const res = await fetch(`${API_BASE}${path}`, {
                headers: { 
                    "Content-Type": "application/json",
                    ...(headers || {})
                },
                ...rest,
            });
            const json = await res.json();
            if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
            return json;
        };
        
        // Execute reCAPTCHA v2 and return token
        const executeRecaptcha = async (action = "submit") => {
            const siteKey = window._recaptcha_site_key || RECAPTCHA_PUBLIC_KEY;
            console.log("[reCAPTCHA] Executing reCAPTCHA v2 for action:", action);

            // Wait for grecaptcha to load
            const waitForGrecaptcha = () => new Promise(resolve => {
                if (window.grecaptcha?.render) {
                    return resolve();
                }
                let waited = 0;
                const iv = setInterval(() => {
                    if (window.grecaptcha?.render) {
                        clearInterval(iv);
                        resolve();
                    } else if (waited > 10000) {
                        console.error("[reCAPTCHA] Script failed to load");
                        clearInterval(iv);
                        resolve();
                    }
                    waited += 100;
                }, 100);
            });

            try {
                await waitForGrecaptcha();
                
                if (!window.grecaptcha?.render) {
                    console.error("[reCAPTCHA] grecaptcha.render unavailable");
                    return "";
                }

                return new Promise((resolve) => {
                    // Create modal for CAPTCHA challenge UI (rendered if verification is required)
                    const overlay = document.createElement('div');
                    overlay.style.cssText = `
                        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                        background: rgba(0,0,0,0.65); z-index: 9998;
                        display: flex; align-items: center; justify-content: center;
                        backdrop-filter: blur(3px);
                    `;
                    
                    const container = document.createElement('div');
                    container.style.cssText = `
                        background: #111827; padding: 30px; border-radius: 12px;
                        border: 1px solid #374151; text-align: center;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                    `;
                    
                    const title = document.createElement('p');
                    title.textContent = "Verifying Security Credentials";
                    title.style.cssText = 'margin-bottom: 20px; font-weight: 500; color: #f3f4f6; font-size: 15px; font-family: monospace;';
                    
                    const captchaDiv = document.createElement('div');
                    captchaDiv.id = `g-recaptcha-${Date.now()}`;
                    
                    container.appendChild(title);
                    container.appendChild(captchaDiv);
                    overlay.appendChild(container);
                    document.body.appendChild(overlay);
                    
                    // Track completion
                    let completed = false;
                    const timeoutId = setTimeout(() => {
                        if (!completed) {
                            console.warn("[reCAPTCHA] Timeout (2 min)");
                            overlay.remove();
                            resolve("");
                        }
                    }, 120000);
                    
                    // Callback
                    const callbackName = `onRecaptchaSuccess_${Date.now()}`;
                    window[callbackName] = (token) => {
                        if (completed) return;
                        completed = true;
                        clearTimeout(timeoutId);
                        console.log("[reCAPTCHA] Token received");
                        overlay.remove();
                        try { delete window[callbackName]; } catch(e) {}
                        resolve(token);
                    };
                    
                    try {
                        // 1. Render the reCAPTCHA instance configured explicitly as 'invisible'
                        const widgetId = grecaptcha.render(captchaDiv.id, {
                            sitekey: siteKey,
                            size: 'invisible',
                            callback: callbackName,
                            'error-callback': () => {
                                if (completed) return;
                                completed = true;
                                clearTimeout(timeoutId);
                                console.error("[reCAPTCHA] Execution error encountered");
                                overlay.remove();
                                resolve("");
                            },
                            'expired-callback': () => {
                                console.warn("[reCAPTCHA] Token expired");
                            }
                        });

                        // 2. Explicitly fire the execution challenge programmatically
                        grecaptcha.execute(widgetId);

                    } catch (err) {
                        clearTimeout(timeoutId);
                        console.error("[reCAPTCHA] Render error:", err);
                        overlay.remove();
                        resolve("");
                    }
                });
            } catch (err) {
                console.error("[reCAPTCHA] Error:", err);
                return "";
            }
        };

        // ─── ICONS ────────────────────────────────────────────────────────────
        const Icon = ({ name, size = 20, className = "" }) => {
            const icons = {
                Shield: "<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/>",
                Search: "<circle cx='11' cy='11' r='8'/><path d='m21 21-4.35-4.35'/>",
                Plus: "<path d='M12 5v14M5 12h14'/>",
                Filter: "<polygon points='22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3'/>",
                X: "<path d='M18 6 6 18M6 6l12 12'/>",
                ChevronRight: "<path d='m9 18 6-6-6-6'/>",
                ChevronDown: "<path d='m6 9 6 6 6-6'/>",
                Activity: "<path d='M22 12h-4l-3 9L9 3l-3 9H2'/>",
                Users: "<path d='M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M22 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/>",
                FileText: "<path d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/><polyline points='14 2 14 8 20 8'/><line x1='16' y1='13' x2='8' y2='13'/><line x1='16' y1='17' x2='8' y2='17'/><line x1='10' y1='9' x2='8' y2='9'/>",
                MapPin: "<path d='M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z'/><circle cx='12' cy='10' r='3'/>",
                Clock: "<circle cx='12' cy='12' r='10'/><polyline points='12 6 12 12 16 14'/>",
                BarChart3: "<path d='M3 3v18h18'/><path d='M18 17V9'/><path d='M13 17V5'/><path d='M8 17v-3'/>",
                AlertTriangle: "<path d='m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/>",
                Lock: "<rect x='3' y='11' width='18' height='11' rx='2' ry='2'/><path d='M7 11V7a5 5 0 0 1 10 0v4'/>",
                Unlock: "<rect x='3' y='11' width='18' height='11' rx='2' ry='2'/><path d='M9 11V7a5 5 0 0 1 9.9-1'/>",
                Eye: "<path d='M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z'/><circle cx='12' cy='12' r='3'/>",
                EyeOff: "<path d='M9.88 9.88a3 3 0 1 0 4.24 4.24'/><path d='M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68'/><path d='M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61'/><line x1='2' y1='2' x2='22' y2='22'/>",
                Mail: "<rect x='2' y='4' width='20' height='16' rx='2'/><path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7'/>",
                Phone: "<path d='M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'/>",
                BadgeCheck: "<path d='M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z'/><path d='m9 15 2 2 4-4'/>",
                TrendingUp: "<polyline points='23 6 13.5 15.5 8.5 10.5 1 18'/><polyline points='17 6 23 6 23 12'/>",
                TrendingDown: "<polyline points='23 18 13.5 8.5 8.5 13.5 1 6'/><polyline points='17 18 23 18 23 12'/>",
                Zap: "<polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/>",
                Globe: "<circle cx='12' cy='12' r='10'/><line x1='2' y1='12' x2='22' y2='12'/><path d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/>",
                Cpu: "<rect x='4' y='4' width='16' height='16' rx='2'/><rect x='9' y='9' width='6' height='6'/><path d='M15 2v2'/><path d='M15 20v2'/><path d='M2 15h2'/><path d='M2 9h2'/><path d='M20 15h2'/><path d='M20 9h2'/><path d='M9 2v2'/><path d='M9 20v2'/>",
                Layers: "<polygon points='12 2 2 7 12 12 22 7 12 2'/><polyline points='2 17 12 22 22 17'/><polyline points='2 12 12 17 22 12'/>",
                Radio: "<path d='M4.9 19.1C1 15.2 1 8.8 4.9 4.9'/><path d='M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5'/><circle cx='12' cy='12' r='2'/><path d='M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5'/><path d='M19.1 4.9C23 8.8 23 15.1 19.1 19.1'/>",
                Fingerprint: "<path d='M2 12C2 6.5 6.5 2 12 2a10 10 0 0 1 8 6'/><path d='M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2'/><path d='M17.29 21.02c.12-.6.43-2.3.5-3.02'/><path d='M12 10a2 2 0 0 1 2 2c0 2.3-2 1.8-2 5'/><path d='M11.25 16c-.45-1-.72-2.3-.72-4 0-2 1-3 3-3s3 1 3 3c0 2.3-2 1.8-2 5'/><path d='M17 15c0 1.7-.34 3.3-1 4.5'/><path d='M13.22 22c-.35-.6-.78-1.76-.78-3.5 0-2 1-3 3-3s3 1 3 3c0 2.3-2 1.8-2 5'/><path d='M2 15c.7 1.2 1.7 2.8 3 4'/><path d='M22 15c-.7 1.2-1.7 2.8-3 4'/>",
                Database: "<ellipse cx='12' cy='5' rx='9' ry='3'/><path d='M3 5V19A9 3 0 0 0 21 19V5'/><path d='M3 12A9 3 0 0 0 21 12'/>",
                Target: "<circle cx='12' cy='12' r='10'/><circle cx='12' cy='12' r='6'/><circle cx='12' cy='12' r='2'/>",
                ArrowRight: "<path d='M5 12h14'/><path d='m12 5 7 7-7 7'/>",
                ArrowLeft: "<path d='M19 12H5'/><path d='m12 19-7-7 7-7'/>",
                Menu: "<line x1='4' x2='20' y1='12' y2='12'/><line x1='4' x2='20' y1='6' y2='6'/><line x1='4' x2='20' y1='18' y2='18'/>",
                Bell: "<path d='M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9'/><path d='M10.3 21a1.94 1.94 0 0 0 3.4 0'/>",
                Settings: "<path d='M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z'/><circle cx='12' cy='12' r='3'/>",
                User: "<path d='M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2'/><circle cx='12' cy='7' r='4'/>",
                LogOut: "<path d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4'/><polyline points='16 17 21 12 16 7'/><line x1='21' y1='12' x2='9' y2='12'/>",
                Trash2: "<path d='M3 6h18'/><path d='M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6'/><path d='M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2'/><line x1='10' y1='11' x2='10' y2='17'/><line x1='14' y1='11' x2='14' y2='17'/>",
                Edit: "<path d='M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7'/><path d='M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z'/>",
                MoreVertical: "<circle cx='12' cy='12' r='1'/><circle cx='12' cy='5' r='1'/><circle cx='12' cy='19' r='1'/>",
                CheckCircle: "<path d='M22 11.08V12a10 10 0 1 1-5.93-9.14'/><polyline points='22 4 12 14.01 9 11.01'/>",
                XCircle: "<circle cx='12' cy='12' r='10'/><line x1='15' y1='9' x2='9' y2='15'/><line x1='9' y1='9' x2='15' y2='15'/>",
                Info: "<circle cx='12' cy='12' r='10'/><line x1='12' y1='16' x2='12' y2='12'/><line x1='12' y1='8' x2='12.01' y2='8'/>",
                Hash: "<line x1='4' x2='20' y1='9' y2='9'/><line x1='4' x2='20' y1='15' y2='15'/><line x1='10' x2='8' y1='3' y2='21'/><line x1='16' x2='14' y1='3' y2='21'/>",
                Calendar: "<rect x='3' y='4' width='18' height='18' rx='2' ry='2'/><line x1='16' y1='2' x2='16' y2='6'/><line x1='8' y1='2' x2='8' y2='6'/><line x1='3' y1='10' x2='21' y2='10'/>",
                Briefcase: "<rect x='2' y='7' width='20' height='14' rx='2' ry='2'/><path d='M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'/>",
                Award: "<circle cx='12' cy='8' r='7'/><polyline points='8.21 13.89 7 23 12 20 17 23 15.79 13.88'/>",
                Star: "<polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/>",
                Flame: "<path d='M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z'/>",
                Crosshair: "<circle cx='12' cy='12' r='10'/><line x1='22' y1='12' x2='18' y2='12'/><line x1='6' y1='12' x2='2' y2='12'/><line x1='12' y1='6' x2='12' y2='2'/><line x1='12' y1='22' x2='12' y2='18'/>",
                Wifi: "<path d='M5 12.55a11 11 0 0 1 14.08 0'/><path d='M1.42 9a16 16 0 0 1 21.16 0'/><path d='M8.53 16.11a6 6 0 0 1 6.95 0'/><line x1='12' y1='20' x2='12.01' y2='20'/>",
                Server: "<rect x='2' y='2' width='20' height='8' rx='2' ry='2'/><rect x='2' y='14' width='20' height='8' rx='2' ry='2'/><line x1='6' y1='6' x2='6.01' y2='6'/><line x1='6' y1='18' x2='6.01' y2='18'/>",
                HardDrive: "<line x1='22' y1='12' x2='2' y2='12'/><path d='M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z'/><line x1='6' y1='16' x2='6.01' y2='16'/><line x1='10' y1='16' x2='10.01' y2='16'/>",
                ScanLine: "<path d='M3 7V5a2 2 0 0 1 2-2h2'/><path d='M17 3h2a2 2 0 0 1 2 2v2'/><path d='M21 17v2a2 2 0 0 1-2 2h-2'/><path d='M7 21H5a2 2 0 0 1-2-2v-2'/><line x1='7' y1='12' x2='17' y2='12'/>",
                GitBranch: "<line x1='6' x2='6' y1='3' y2='15'/><circle cx='18' cy='6' r='3'/><circle cx='6' cy='18' r='3'/><path d='M18 9a9 9 0 0 1-9 9'/>",
                GitCommit: "<circle cx='12' cy='12' r='3'/><line x1='3' y1='12' x2='9' y2='12'/><line x1='15' y1='12' x2='21' y2='12'/>",
                GitPullRequest: "<circle cx='18' cy='18' r='3'/><circle cx='6' cy='6' r='3'/><path d='M13 6h3a2 2 0 0 1 2 2v7'/><line x1='6' y1='9' x2='6' y2='21'/>",
                GitMerge: "<circle cx='18' cy='18' r='3'/><circle cx='6' cy='6' r='3'/><path d='M6 9v12a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3'/>",
                Network: "<rect x='16' y='16' width='6' height='6' rx='1'/><rect x='2' y='16' width='6' height='6' rx='1'/><rect x='9' y='2' width='6' height='6' rx='1'/><path d='M12 8v4'/><path d='M6 16v-2a6 6 0 0 1 12 0v2'/>",
                Share2: "<circle cx='18' cy='5' r='3'/><circle cx='6' cy='12' r='3'/><circle cx='18' cy='19' r='3'/><line x1='8.59' y1='13.51' x2='15.42' y2='17.49'/><line x1='15.41' y1='6.51' x2='8.59' y2='10.49'/>",
                Link: "<path d='M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71'/><path d='M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'/>",
                Paperclip: "<path d='m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48'/>",
                ClipboardList: "<rect x='8' y='2' width='8' height='4' rx='1' ry='1'/><path d='M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'/><path d='M12 11h4'/><path d='M12 16h4'/><path d='M8 11h.01'/><path d='M8 16h.01'/>",
                ClipboardCheck: "<rect x='8' y='2' width='8' height='4' rx='1' ry='1'/><path d='M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'/><path d='m9 14 2 2 4-4'/>",
                FileCheck: "<path d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/><polyline points='14 2 14 8 20 8'/><path d='m9 15 2 2 4-4'/>",
                FilePlus: "<path d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/><polyline points='14 2 14 8 20 8'/><line x1='12' y1='18' x2='12' y2='12'/><line x1='9' y1='15' x2='15' y2='15'/>",
                FileMinus: "<path d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/><polyline points='14 2 14 8 20 8'/><line x1='9' y1='15' x2='15' y2='15'/>",
                FileX: "<path d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/><polyline points='14 2 14 8 20 8'/><line x1='9.5' y1='15.5' x2='14.5' y2='10.5'/><line x1='14.5' y1='15.5' x2='9.5' y2='10.5'/>",
                Folder: "<path d='M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/>",
                FolderOpen: "<path d='m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H14a2 2 0 0 1 2 2v2'/>",
                FolderCheck: "<path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><path d='m9 15 2 2 4-4'/>",
                FolderX: "<path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><path d='m9.5 10.5 5 5'/><path d='m14.5 10.5-5 5'/>",
                FolderPlus: "<path d='M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><line x1='12' y1='10' x2='12' y2='16'/><line x1='9' y1='13' x2='15' y2='13'/>",
                FolderMinus: "<path d='M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><line x1='9' y1='13' x2='15' y2='13'/>",
                FolderCog: "<path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><circle cx='18' cy='15' r='3'/>",
                FolderLock: "<path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><rect x='14' y='12' width='8' height='6' rx='1'/><path d='M17 12v-2a2 2 0 1 0-4 0v2'/>",
                FolderSearch: "<path d='M11 15h2a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h2'/><path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><circle cx='17' cy='17' r='3'/><path d='m21 21-1.5-1.5'/>",
                FolderSync: "<path d='M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z'/><path d='M12 10v4h4'/><path d='m22 4-6 6'/><path d='M12 14v-4H8'/><path d='m2 20 6-6'/>",
            };
            const path = icons[name] || "";
            return (
                <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} dangerouslySetInnerHTML={{ __html: path }} />
            );
        };

        // ─── ANIMATED COUNTER ─────────────────────────────────────────────────
        const AnimatedCounter = ({ value, duration = 2000, prefix = "", suffix = "" }) => {
            const [display, setDisplay] = useState(0);
            const ref = useRef(null);
            const [hasAnimated, setHasAnimated] = useState(false);

            useEffect(() => {
                const observer = new IntersectionObserver(
                    ([entry]) => {
                        if (entry.isIntersecting && !hasAnimated) {
                            setHasAnimated(true);
                            const startTime = Date.now();
                            const animate = () => {
                                const elapsed = Date.now() - startTime;
                                const progress = Math.min(elapsed / duration, 1);
                                const eased = 1 - Math.pow(1 - progress, 3);
                                setDisplay(Math.floor(eased * value));
                                if (progress < 1) requestAnimationFrame(animate);
                            };
                            requestAnimationFrame(animate);
                        }
                    },
                    { threshold: 0.3 }
                );
                if (ref.current) observer.observe(ref.current);
                return () => observer.disconnect();
            }, [value, duration, hasAnimated]);

            return (
                <span ref={ref} className="metric-value">{prefix}{display.toLocaleString()}{suffix}</span>
            );
        };

        // ─── PARTICLES ────────────────────────────────────────────────────────
        const Particles = ({ count = 30 }) => {
            const particles = useMemo(() => {
                return Array.from({ length: count }, (_, i) => ({
                    id: i,
                    x: Math.random() * 100,
                    y: Math.random() * 100,
                    size: Math.random() * 3 + 1,
                    duration: Math.random() * 20 + 10,
                    delay: Math.random() * 5,
                    opacity: Math.random() * 0.3 + 0.1,
                }));
            }, [count]);

            return (
                <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
                    {particles.map(p => (
                        <div
                            key={p.id}
                            className="particle"
                            style={{
                                left: `${p.x}%`,
                                top: `${p.y}%`,
                                width: p.size,
                                height: p.size,
                                background: `rgba(0, 229, 255, ${p.opacity})`,
                                animation: `float ${p.duration}s ease-in-out ${p.delay}s infinite`,
                            }}
                        />
                    ))}
                </div>
            );
        };

        // ─── LANDING MOTION VARIANTS ────────────────────────────────────────────
        const LANDING_VIDEO_URL = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260517_222138_3e3205be-3364-417b-a64a-bfe087acbec4.mp4";

        const fadeDown = {
            hidden: { opacity: 0, y: -24 },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.6, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const fadeUp = {
            hidden: { opacity: 0, y: 32 },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.7, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const slideUpReveal = {
            hidden: { opacity: 0, y: "110%" },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.85, delay: 0.15 + i * 0.12, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const CRMS_INPUT = "crms-input w-full rounded-xl border-2 border-black bg-white/80 px-4 py-3 text-sm font-medium text-black placeholder-black/35 transition-all";
        const CRMS_LABEL = "mb-2 block text-[10px] font-semibold uppercase tracking-[0.18em] text-black";
        const CRMS_CARD = "rounded-2xl border-2 border-black bg-white/88 p-6 shadow-lg backdrop-blur-md sm:p-8";

        const HeroVideoBackground = ({ scrim = "bg-white/30" }) => (
            <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
                <video
                    className="absolute inset-0 h-full w-full object-cover"
                    src={LANDING_VIDEO_URL}
                    autoPlay
                    loop
                    muted
                    playsInline
                />
                <div className={`absolute inset-0 ${scrim}`} />
                <div className="crms-spin-orb absolute -left-24 top-1/4 h-[22rem] w-[22rem] rounded-full bg-gradient-to-br from-accent/25 via-purple-400/15 to-transparent blur-3xl sm:h-[28rem] sm:w-[28rem]" />
                <div className="crms-spin-orb absolute -right-32 bottom-0 h-[18rem] w-[18rem] rounded-full bg-gradient-to-tl from-accent/20 via-violet-300/10 to-transparent blur-3xl" style={{ animationDirection: "reverse", animationDuration: "36s" }} />
            </div>
        );

        const CrmsPageHeader = ({ title, subtitle, onBack }) => (
            <motion.header
                className="relative z-20 border-b-2 border-black/10 bg-white/50 backdrop-blur-md"
                initial="hidden"
                animate="visible"
                variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
            >
                <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
                    <motion.div variants={fadeDown} custom={0} className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white/80 sm:h-11 sm:w-11">
                            <Icon name="Shield" size={18} className="text-black" />
                        </div>
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-black">{title}</div>
                            {subtitle && (
                                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-black/65">{subtitle}</div>
                            )}
                        </div>
                    </motion.div>
                    {onBack && (
                        <motion.button
                            type="button"
                            variants={fadeDown}
                            custom={1}
                            onClick={onBack}
                            className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-black transition-opacity hover:opacity-60 sm:text-xs"
                        >
                            <Icon name="ArrowLeft" size={14} />
                            Back to Home
                        </motion.button>
                    )}
                </div>
            </motion.header>
        );

        const CrmsPageShell = ({ children, title, subtitle, onBack, scrim, className = "" }) => {
            useEffect(() => {
                document.body.classList.add("landing-hero");
                return () => document.body.classList.remove("landing-hero");
            }, []);
            return (
                <div className={`landing-hero-text relative min-h-screen min-h-[100dvh] ${className}`}>
                    <HeroVideoBackground scrim={scrim} />
                    <CrmsPageHeader title={title} subtitle={subtitle} onBack={onBack} />
                    <div className="relative z-10">{children}</div>
                </div>
            );
        };

        // ─── LANDING PAGE ─────────────────────────────────────────────────────
        const LandingPage = ({ onNavigate }) => {
            const [liveStats, setLiveStats] = useState({
                active_cases: null, solved_cases: null,
                total_officers: null, cyber_cases: null
            });
            useEffect(() => {
                apiFetch("/stats").then(r => setLiveStats(r.data || r)).catch(() => {});
            }, []);

            useEffect(() => {
                document.body.classList.add("landing-hero");
                return () => document.body.classList.remove("landing-hero");
            }, []);

            const heroStats = [
                { label: "Active Cases", value: liveStats.active_cases },
                { label: "Officers Deployed", value: liveStats.total_officers },
                { label: "Cases Solved", value: liveStats.solved_cases },
            ];

            const headingWords = ["Serve", "Protect", "Justice"];

            return (
                <div className="landing-hero-text relative flex min-h-screen min-h-[100dvh] flex-col overflow-hidden">
                    <HeroVideoBackground scrim="bg-white/25" />

                    {/* Navigation */}
                    <motion.header
                        className="relative z-20 flex items-center justify-between px-5 py-5 sm:px-8 sm:py-6"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
                    >
                        <motion.div variants={fadeDown} custom={0} className="flex items-center gap-3">
                            <div className="flex h-11 w-11 sm:h-12 sm:w-12 items-center justify-center rounded-full border-2 border-black bg-white/80 backdrop-blur-sm">
                                <Icon name="Shield" size={20} className="text-black" />
                            </div>
                            <div className="hidden sm:block">
                                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-black">CRMS</div>
                                <div className="text-[10px] font-semibold uppercase tracking-[0.25em] text-black/70">Bengaluru Police</div>
                            </div>
                        </motion.div>
                    </motion.header>

                    {/* Stats row */}
                    <motion.section
                        className="relative z-10 mt-auto px-5 sm:px-8"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.1 } } }}
                    >
                        <div className="flex flex-col items-end gap-6 sm:gap-8 md:flex-row md:justify-end md:gap-12 lg:gap-16">
                            {heroStats.map((stat, i) => (
                                <motion.div
                                    key={stat.label}
                                    variants={fadeUp}
                                    custom={i}
                                    className="text-right"
                                >
                                    <div className="flex items-baseline justify-end gap-0.5">
                                        <span className="text-2xl font-semibold text-accent sm:text-3xl md:text-4xl">+</span>
                                        <span className="text-3xl font-semibold tabular-nums tracking-tight text-black sm:text-4xl md:text-5xl lg:text-6xl">
                                            {stat.value === null
                                                ? <span className="inline-block h-9 w-16 animate-pulse rounded bg-black/10 sm:h-11 sm:w-20" />
                                                : <AnimatedCounter value={stat.value} />}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-black/80 sm:text-xs">
                                        {stat.label}
                                    </p>
                                </motion.div>
                            ))}
                        </div>
                    </motion.section>

                    {/* Bottom content */}
                    <motion.section
                        className="relative z-10 mt-8 flex flex-1 flex-col justify-end px-5 pb-8 sm:mt-12 sm:px-8 sm:pb-12 md:pb-16"
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={2}
                    >
                        <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end lg:gap-12">
                            <div className="max-w-xl">
                                <motion.p
                                    variants={fadeUp}
                                    custom={0}
                                    className="mb-4 text-[10px] font-semibold uppercase tracking-[0.28em] text-black sm:text-xs"
                                >
                                    Bengaluru Police Department · Crime Record Management
                                </motion.p>

                                <motion.div variants={fadeUp} custom={1} className="mb-6 flex flex-wrap gap-3 sm:gap-4">
                                    <button
                                        type="button"
                                        onClick={() => onNavigate("public")}
                                        className="inline-flex items-center gap-2 rounded-full border-2 border-black bg-black px-6 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 sm:px-8"
                                    >
                                        <Icon name="Globe" size={16} />
                                        Public Portal
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => onNavigate("login")}
                                        className="inline-flex items-center gap-2 rounded-full border-2 border-black bg-white/70 px-6 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-black backdrop-blur-sm transition-opacity hover:opacity-80 sm:px-8"
                                    >
                                        <Icon name="Shield" size={16} />
                                        Staff Dashboard
                                    </button>
                                </motion.div>

                                <motion.p
                                    variants={fadeUp}
                                    custom={2}
                                    className="text-xs font-semibold uppercase leading-relaxed tracking-[0.12em] text-black/90 sm:text-sm sm:leading-relaxed sm:tracking-[0.14em]"
                                >
                                    Advanced intelligence platform for real-time case tracking, officer coordination,
                                    and cybercrime analytics across Bengaluru.
                                </motion.p>
                            </div>

                            <div className="overflow-hidden">
                                {headingWords.map((word, i) => (
                                    <div key={word} className="overflow-hidden">
                                        <motion.h1
                                            variants={slideUpReveal}
                                            initial="hidden"
                                            animate="visible"
                                            custom={i}
                                            className="text-[clamp(3rem,14vw,11rem)] font-semibold uppercase leading-[0.88] tracking-[0.02em] text-black"
                                        >
                                            {word}
                                        </motion.h1>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </motion.section>
                </div>
            );
        };

        // ─── PUBLIC PORTAL ────────────────────────────────────────────────────
        const PublicPortal = ({ onNavigate }) => {
            const [activeTab, setActiveTab] = useState("complaint");
            const [error, setError] = useState("");
            const [formData, setFormData] = useState({
                name: "", contact: "", email: "", aadhaar_last4: "",
                incident_desc: "", crime_type: "", location: ""
            });
            const [aadhaarError, setAadhaarError] = useState("");
            const [submitted, setSubmitted] = useState(false);
            const [accessForm, setAccessForm] = useState({ case_id: "", requester_name: "", requester_email: "", requester_number: "", reason: "" });

            const [accessSubmitted, setAccessSubmitted] = useState(false);

            const [submitting, setSubmitting] = useState(false);
            const [caseRef, setCaseRef] = useState(null);

            const handleComplaintSubmit = async (e) => {
                e.preventDefault();
                // Validate Aadhaar last 4 digits
                const a4 = formData.aadhaar_last4.trim();
                if (!/^[0-9]{4}$/.test(a4)) {
                    setAadhaarError("Enter exactly 4 digits (last 4 of your Aadhaar)");
                    return;
                }
                setAadhaarError("");
                setSubmitting(true);
                try {
                    // Get CAPTCHA token
                    const captchaToken = await executeRecaptcha("complaint");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required");
                        return;
                    }
                    const payload = { ...formData, aadhaar_last4: a4, complaint_mode: "Online", captcha_token: captchaToken };
                    const res = await apiFetch("/public/complaint", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    setCaseRef(res.reference || null);
                    setSubmitted(true);
                } catch (err) {
                    alert("Submission failed: " + err.message);
                } finally {
                    setSubmitting(false);
                }
                setTimeout(() => { setSubmitted(false); setCaseRef(null); }, 8000);
            };

            const handleAccessSubmit = async (e) => {
                e.preventDefault();
                setError("");
                setSubmitting(true);
                try {
                    // Get CAPTCHA token
                    const captchaToken = await executeRecaptcha("access_request");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required for access requests");
                        setSubmitting(false);
                        return;
                    }
                    const payload = { ...accessForm, captcha_token: captchaToken };
                    await apiFetch("/public/access-request", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    setAccessSubmitted(true);
                    setAccessForm({ case_id: "", requester_name: "", requester_email: "", requester_number: "", reason: "" });
                } catch (err) {
                    console.warn("[CRMS] Access request POST failed:", err.message);
                    setError(err.message || "Failed to submit access request.");
                } finally {
                    setSubmitting(false);
                }
                setTimeout(() => setAccessSubmitted(false), 8000);
            };


            return (
                <CrmsPageShell
                    title="CRMS Public Portal"
                    subtitle="Bengaluru Police Department"
                    onBack={() => onNavigate("landing")}
                    scrim="bg-white/40"
                >
                    <motion.div
                        className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-12"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
                    >
                        <motion.div variants={fadeUp} custom={0} className="mb-10 text-center sm:mb-12">
                            <h1 className="mb-3 text-2xl font-semibold uppercase tracking-[0.12em] text-black sm:text-3xl md:text-4xl">Public Services</h1>
                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-black/70 sm:text-sm">File complaints and request case information securely</p>
                        </motion.div>

                        {/* Tabs */}
                        <motion.div variants={fadeUp} custom={1} className="mb-10 flex justify-center">
                            <div className="flex gap-1 rounded-full border-2 border-black bg-white/80 p-1 backdrop-blur-sm">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab("complaint")}
                                    className={`rounded-full px-5 py-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] transition-all sm:px-6 sm:text-xs ${activeTab === "complaint" ? "bg-black text-white" : "text-black/60 hover:text-black"}`}
                                >
                                    <span className="flex items-center gap-2">
                                        <Icon name="FilePlus" size={14} />
                                        File Complaint
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setActiveTab("access")}
                                    className={`rounded-full px-5 py-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] transition-all sm:px-6 sm:text-xs ${activeTab === "access" ? "bg-black text-white" : "text-black/60 hover:text-black"}`}
                                >
                                    <span className="flex items-center gap-2">
                                        <Icon name="Eye" size={14} />
                                        Request Case Access
                                    </span>
                                </button>
                            </div>
                        </motion.div>

                        {/* Complaint Form */}
                        {activeTab === "complaint" && (
                            <motion.div variants={fadeUp} custom={2} className={CRMS_CARD}>
                                <div className="mb-8 flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white">
                                        <Icon name="FileText" size={18} className="text-black" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-black sm:text-xl">File a Complaint</h2>
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/65 sm:text-xs">Submit a new case to the Bengaluru Police</p>
                                    </div>
                                </div>

                                {submitted ? (
                                    <div className="py-12 text-center">
                                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <Icon name="CheckCircle" size={28} className="text-accent" />
                                        </div>
                                        <h3 className="mb-2 text-lg font-semibold uppercase tracking-[0.1em] text-black">Complaint Submitted</h3>
                                        {caseRef && (
                                            <div className="mb-4 inline-flex items-center gap-2 rounded-full border-2 border-black bg-white/80 px-4 py-2">
                                                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-black/60">Your Reference</span>
                                                <span className="font-mono text-lg font-bold text-accent">{caseRef}</span>
                                            </div>
                                        )}
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/70">Complaint logged for officer review. Save your reference number — you will need it to track your case.</p>
                                    </div>
                                ) : (
                                    <form onSubmit={handleComplaintSubmit} className="space-y-5">
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={CRMS_LABEL}>Complainant Name *</label>
                                                <input type="text" required value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="Full name" />
                                            </div>
                                            <div>
                                                <label className={CRMS_LABEL}>Contact Number *</label>
                                                <input type="tel" required value={formData.contact} onChange={e => setFormData({...formData, contact: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="+91-XXXXXXXXXX" />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={CRMS_LABEL}>Email Address</label>
                                                <input type="email" value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="email@example.com" />
                                            </div>
                                            <div>
                                                <label className={CRMS_LABEL}>
                                                    Aadhaar Last 4 Digits *
                                                    <span className="ml-1 font-normal normal-case tracking-normal text-black/50">(identity verification)</span>
                                                </label>
                                                <input type="text" required maxLength={4} inputMode="numeric" pattern="[0-9]{4}"
                                                    value={formData.aadhaar_last4}
                                                    onChange={e => { setFormData({...formData, aadhaar_last4: e.target.value.replace(/\D/,"")}); setAadhaarError(""); }}
                                                    className={`${CRMS_INPUT} font-mono tracking-widest ${aadhaarError ? "border-red-600" : ""}`}
                                                    placeholder="XXXX" />
                                                {aadhaarError && <p className="mt-1 text-xs font-semibold text-red-600">{aadhaarError}</p>}
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={CRMS_LABEL}>Crime Type</label>
                                                <select value={formData.crime_type} onChange={e => setFormData({...formData, crime_type: e.target.value})}
                                                    className={`${CRMS_INPUT} appearance-none`}>
                                                    <option value="">Select type</option>
                                                    <option value="Cyber Fraud">Cyber Fraud</option>
                                                    <option value="Theft">Theft</option>
                                                    <option value="Assault">Assault</option>
                                                    <option value="Fraud">Fraud</option>
                                                    <option value="Other">Other</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className={CRMS_LABEL}>Location</label>
                                                <input type="text" value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="Bengaluru area" />
                                            </div>
                                        </div>
                                        <input type="hidden" value="Online" name="complaint_mode" />
                                        <div>
                                            <label className={CRMS_LABEL}>Incident Description</label>
                                            <textarea value={formData.incident_desc} onChange={e => setFormData({...formData, incident_desc: e.target.value})}
                                                rows={4}
                                                className={`${CRMS_INPUT} resize-none`}
                                                placeholder="Describe the incident in detail..." />
                                        </div>
                                        <button type="submit" disabled={submitting} className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 ${submitting ? "cursor-not-allowed opacity-60" : ""}`}>
                                            <Icon name="FilePlus" size={16} />
                                            {submitting ? "Submitting..." : "Submit Complaint"}
                                        </button>
                                    </form>
                                )}
                            </motion.div>
                        )}

                        {/* Access Request Form */}
                        {activeTab === "access" && (
                            <motion.div variants={fadeUp} custom={2} className={CRMS_CARD}>
                                <div className="mb-8 flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white">
                                        <Icon name="Eye" size={18} className="text-accent" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-black sm:text-xl">Request Case Access</h2>
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/65 sm:text-xs">Request read access to case information</p>
                                    </div>
                                </div>

                                {accessSubmitted ? (
                                    <div className="py-12 text-center">
                                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <Icon name="CheckCircle" size={28} className="text-accent" />
                                        </div>
                                        <h3 className="mb-2 text-lg font-semibold uppercase tracking-[0.1em] text-black">Request Submitted</h3>
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/70">Your access request is under review. You will be notified via email.</p>
                                    </div>
                                ) : (
                                    <form onSubmit={handleAccessSubmit} className="space-y-5">
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={CRMS_LABEL}>Case ID *</label>
                                                <input type="text" required value={accessForm.case_id} onChange={e => setAccessForm({...accessForm, case_id: e.target.value})}
                                                    className={`${CRMS_INPUT} font-mono`} placeholder="e.g. BLR-001" />
                                            </div>
                                            <div>
                                                <label className={CRMS_LABEL}>Contact Number *</label>
                                                <input type="tel" required value={accessForm.requester_number} onChange={e => setAccessForm({...accessForm, requester_number: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="+91-XXXXXXXXXX" />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={CRMS_LABEL}>Your Name *</label>
                                                <input type="text" required value={accessForm.requester_name} onChange={e => setAccessForm({...accessForm, requester_name: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="Full name" />
                                            </div>
                                            <div>
                                                <label className={CRMS_LABEL}>Email *</label>
                                                <input type="email" required value={accessForm.requester_email} onChange={e => setAccessForm({...accessForm, requester_email: e.target.value})}
                                                    className={CRMS_INPUT} placeholder="email@example.com" />
                                            </div>
                                        </div>
                                        <div>
                                            <label className={CRMS_LABEL}>Reason for Access *</label>
                                            <textarea required value={accessForm.reason} onChange={e => setAccessForm({...accessForm, reason: e.target.value})}
                                                rows={3}
                                                className={`${CRMS_INPUT} resize-none`}
                                                placeholder="Explain why you need access to this case..." />
                                        </div>
                                        {error && (
                                            <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                                <Icon name="AlertTriangle" size={14} /> {error}
                                            </div>
                                        )}
                                        <button type="submit" disabled={submitting} className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 ${submitting ? "cursor-not-allowed opacity-60" : ""}`}>
                                            <Icon name={submitting ? "Clock" : "Eye"} size={16} />
                                            {submitting ? "Submitting Request..." : "Submit Access Request"}
                                        </button>
                                    </form>
                                )}
                            </motion.div>
                        )}
                    </motion.div>
                </CrmsPageShell>
            );
        };

        // ─── STAFF DASHBOARD ──────────────────────────────────────────────────
        const StaffDashboard = ({ onNavigate, userRole, officer, onLogout }) => {
            // Filter States
            const [statusFilter, setStatusFilter] = useState("All");
            const [typeFilter, setTypeFilter] = useState("All");
            const [searchQuery, setSearchQuery] = useState("");
            
            // Core Data & Pagination States
            const [cases, setCases] = useState([]);
            const [currentPage, setCurrentPage] = useState(1);
            const [totalPages, setTotalPages] = useState(1);
            const [totalRecords, setTotalRecords] = useState(0);
            
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState(null);
            const [selectedCase, setSelectedCase] = useState(null);

            // Tab State
            const [activeSubTab, setActiveSubTab] = useState("dossiers");
            
            // Access Requests States
            const [requests, setRequests] = useState([]);
            const [requestsLoading, setRequestsLoading] = useState(false);
            const [requestsError, setRequestsError] = useState(null);
            const [decidingRequestId, setDecidingRequestId] = useState(null);
            const [requestActionMessage, setRequestActionMessage] = useState(null);

            const loadAccessRequests = async () => {
                setRequestsLoading(true);
                setRequestsError(null);
                try {
                    const response = await apiFetch("/api/access-requests", {
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (response.success) {
                        setRequests(response.data || []);
                    } else {
                        setRequestsError(response.error || "Failed to load access requests.");
                    }
                } catch (err) {
                    console.error("[CRMS Engine] Requests load error:", err);
                    setRequestsError(err.message || "Failed to contact authorization server.");
                } finally {
                    setRequestsLoading(false);
                }
            };

            useEffect(() => {
                if (officer) {
                    loadAccessRequests();
                }
            }, [activeSubTab, officer]);

            const handleDecide = async (requestId, action) => {
                setDecidingRequestId(requestId);
                setRequestActionMessage(null);
                try {
                    const response = await apiFetch(`/api/access-requests/${requestId}/${action}`, {
                        method: "POST",
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (response.success) {
                        setRequestActionMessage(response.message || `Request ${action === "approve" ? "approved" : "declined"}.`);
                        await loadAccessRequests();
                    } else {
                        setRequestsError(response.error || "Action failed.");
                    }
                } catch (err) {
                    setRequestsError(err.message || "Action failed.");
                } finally {
                    setDecidingRequestId(null);
                }
            };

            const requestStatusBadge = (status) => {
                const styles = {
                    Pending: "bg-amber-100 text-amber-900 border-amber-400",
                    Accepted: "bg-emerald-100 text-emerald-900 border-emerald-500",
                    Rejected: "bg-rose-100 text-rose-900 border-rose-400",
                };
                return (
                    <span className={`rounded-full border-2 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${styles[status] || styles.Pending}`}>
                        {status}
                    </span>
                );
            };
            
            const pendingCount = requests.filter(r => r.status === "Pending").length;


            // Fetch live data from backend whenever filters or page changes
            useEffect(() => {
                const loadCases = async () => {
                    setLoading(true);
                    setError(null);
                    try {
                        let queryParams = new URLSearchParams({
                            page: currentPage,
                            limit: 16
                        });
                        
                        if (statusFilter !== "All") queryParams.append("status", statusFilter);
                        if (typeFilter !== "All") queryParams.append("crime_type", typeFilter);
                        if (searchQuery.trim() !== "") queryParams.append("search", searchQuery.trim());

                        const response = await apiFetch(`/api/cases?${queryParams.toString()}`, {
                            headers: {
                                "X-Officer-Id": officer?.officer_id?.toString()
                            }
                        });
                        if (response.success) {
                            setCases(response.data || []);
                            if (response.pagination) {
                                setTotalPages(response.pagination.total_pages || 1);
                                setTotalRecords(response.pagination.total_records || 0);
                            }
                        } else {
                            setError(response.error || "Failed to sync system records.");
                        }
                    } catch (err) {
                        console.error("[CRMS Engine] Sync error:", err);
                        setError(err.message || "Network isolation protocol failure.");
                    } finally {
                        setLoading(false);
                    }
                };

                loadCases();
            }, [statusFilter, typeFilter, searchQuery, currentPage]);

            // Reset back to page 1 if search or status filters change
            const handleFilterChange = (type, val) => {
                setCurrentPage(1);
                if (type === "status") setStatusFilter(val);
                if (type === "type") setTypeFilter(val);
            };

            // Handle case status update
            const handleCaseStatusUpdate = async (caseId, newStatus) => {
                try {
                    const response = await apiFetch(`/cases/${caseId}`, {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json",
                            "X-Officer-Id": officer?.officer_id?.toString()
                        },
                        body: JSON.stringify({ status: newStatus })
                    });

                    if (response.success) {
                        // Update the selected case in the modal
                        setSelectedCase(prev => ({
                            ...prev,
                            status: newStatus
                        }));
                        
                        // Reload cases to reflect the change
                        setCurrentPage(1);
                        setStatusFilter("All");
                        setTypeFilter("All");
                        setSearchQuery("");
                        
                        // Show success message
                        console.log(`[CASE UPDATE] Case ${caseId} status updated to ${newStatus}`);
                    } else {
                        setError(response.error || "Failed to update case status");
                        console.error("[CASE UPDATE] Error:", response.error);
                    }
                } catch (err) {
                    setError(`Failed to update case status: ${err.message}`);
                    console.error("[CASE UPDATE] Network error:", err);
                }
            };

            return (
                <CrmsPageShell
                    title="Bengaluru Police · Intralink"
                    subtitle="Officer Command Dashboard"
                    onBack={() => onNavigate("landing")}
                    scrim="bg-white/42"
                >
                    <div className="border-b-2 border-black/10 bg-white/55 backdrop-blur-md">
                        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-8">
                            <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/70 sm:text-xs">
                                Operator: <span className="text-black">{officer?.name || "UNKNOWN"}</span>
                                <span className="text-accent"> ({userRole?.toUpperCase()})</span>
                            </div>
                            <button
                                type="button"
                                onClick={onLogout}
                                className="rounded-full border-2 border-black bg-black px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-white transition-opacity hover:opacity-80 sm:text-xs"
                            >
                                Sign Out
                            </button>
                        </div>
                    </div>

                    <motion.div
                        className="mx-auto max-w-[1600px] space-y-6 p-5 sm:p-6 lg:p-8"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06 } } }}
                    >
                        {/* SUB TAB NAVIGATION BAR */}
                        <motion.div variants={fadeUp} custom={0} className="mb-6 flex gap-4 border-b-2 border-black/15 sm:gap-6">
                            <button
                                type="button"
                                onClick={() => setActiveSubTab("dossiers")}
                                className={`pb-3 text-[10px] font-semibold uppercase tracking-[0.14em] transition-all border-b-2 sm:text-xs ${
                                    activeSubTab === "dossiers"
                                        ? "border-accent text-black"
                                        : "border-transparent text-black/50 hover:text-black"
                                }`}
                            >
                                Case Dossiers
                            </button>
                            <button
                                type="button"
                                onClick={() => setActiveSubTab("requests")}
                                className={`relative pb-3 text-[10px] font-semibold uppercase tracking-[0.14em] transition-all border-b-2 sm:text-xs ${
                                    activeSubTab === "requests"
                                        ? "border-accent text-black"
                                        : "border-transparent text-black/50 hover:text-black"
                                }`}
                            >
                                Access Requests
                                {pendingCount > 0 && (
                                    <span className="ml-2 animate-pulse rounded-full border-2 border-black bg-accent px-2 py-0.5 text-[10px] font-bold text-white">
                                        {pendingCount}
                                    </span>
                                )}
                            </button>
                        </motion.div>

                        {activeSubTab === "dossiers" && (
                            <>
                            {/* CONTROL CONSOLE */}

                        <motion.div variants={fadeUp} custom={1} className={`${CRMS_CARD} flex flex-col items-center justify-between gap-4 p-4 md:flex-row`}>
                            <div className="relative w-full md:w-96">
                                <input 
                                    type="text" 
                                    placeholder="Search dossier records..." 
                                    value={searchQuery}
                                    onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                                    className={`${CRMS_INPUT} pl-10 py-2.5 text-xs`}
                                />
                                <span className="absolute left-3 top-3 text-accent text-sm">+</span>
                            </div>
                            
                            <div className="flex w-full flex-wrap items-center gap-3 md:w-auto">
                                <select 
                                    value={statusFilter} 
                                    onChange={(e) => handleFilterChange("status", e.target.value)}
                                    className={`${CRMS_INPUT} w-auto py-2.5 text-[10px] uppercase tracking-[0.1em]`}
                                >
                                    <option value="All">Status: All</option>
                                    <option value="Active">Active</option>
                                    <option value="Solved">Solved</option>
                                    <option value="Closed">Closed</option>
                                </select>

                                <select 
                                    value={typeFilter} 
                                    onChange={(e) => handleFilterChange("type", e.target.value)}
                                    className={`${CRMS_INPUT} w-auto py-2.5 text-[10px] uppercase tracking-[0.1em]`}
                                >
                                    <option value="All">Classification: All</option>
                                    <option value="Cyber Fraud">Cyber Fraud</option>
                                    <option value="Theft">Theft</option>
                                    <option value="Assault">Assault</option>
                                    <option value="Fraud">Financial Fraud</option>
                                    <option value="Other">Other</option>
                                </select>
                            </div>
                        </motion.div>

                        {error && (
                            <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                <Icon name="AlertTriangle" size={14} />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* CASE DOSSIER GRID */}
                        {loading ? (
                            <div className={`${CRMS_CARD} flex h-96 w-full flex-col items-center justify-center space-y-3`}>
                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/60">Querying central database...</p>
                            </div>
                        ) : cases.length === 0 ? (
                            <div className={`${CRMS_CARD} flex h-96 w-full flex-col items-center justify-center space-y-2 border-dashed`}>
                                <p className="text-sm font-semibold uppercase tracking-[0.12em] text-black">No dossiers found</p>
                                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/55">No entries match your current filters.</p>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                    {cases.map((c) => {
                                        const statusColors = {
                                            Active: "bg-amber-100 text-amber-900 border-amber-400",
                                            Solved: "bg-emerald-100 text-emerald-900 border-emerald-500",
                                            Closed: "bg-black/5 text-black/60 border-black/20"
                                        };
                                        return (
                                            <div 
                                                key={c.case_id} 
                                                onClick={() => setSelectedCase(c)}
                                                className={`${CRMS_CARD} group relative flex cursor-pointer flex-col justify-between p-5 transition-all hover:shadow-xl`}
                                            >
                                                <div>
                                                    <div className="mb-3 flex items-center justify-between">
                                                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/60 transition-colors group-hover:text-accent">
                                                            {c.display_id || `BLR-${String(c.case_id).padStart(3, '0')}`}
                                                        </span>
                                                        <span className={`rounded-full border-2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] ${statusColors[c.status] || statusColors.Active}`}>
                                                            {c.status}
                                                        </span>
                                                    </div>
                                                    <h3 className="mb-1 line-clamp-1 text-[15px] font-semibold text-black group-hover:text-accent">
                                                        {c.title}
                                                    </h3>
                                                    <p className="mb-4 line-clamp-2 text-xs font-medium leading-relaxed text-black/65">
                                                        {c.description || "No file logs details provided."}
                                                    </p>
                                                </div>
                                                
                                                <div className="mt-2 flex items-center justify-between border-t-2 border-black/10 pt-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-black/55">
                                                    <div><span className="text-accent">+</span> {c.crime_type}</div>
                                                    <div className="flex items-center gap-1">
                                                        <Icon name="MapPin" size={12} className="text-accent" />
                                                        {c.location || "N/A"}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* INDUSTRIAL PAGINATION BAR */}
                                <div className={`${CRMS_CARD} flex flex-wrap items-center justify-between gap-3 px-6 py-4 text-xs`}>
                                    <div className="font-semibold uppercase tracking-[0.1em] text-black/65">
                                        Showing <span className="text-black">{cases.length}</span> of <span className="text-black">{totalRecords}</span> entries
                                    </div>
                                    
                                    <div className="flex items-center gap-2">
                                        <button 
                                            type="button"
                                            disabled={currentPage === 1}
                                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                            className="rounded-full border-2 border-black bg-white/80 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black transition-all hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                                        >
                                            Prev
                                        </button>
                                        
                                        <div className="select-none rounded-full border-2 border-black/20 bg-white/60 px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black/70">
                                            Page <span className="text-accent">{currentPage}</span> / {totalPages}
                                        </div>

                                        <button 
                                            type="button"
                                            disabled={currentPage === totalPages}
                                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                            className="rounded-full border-2 border-black bg-white/80 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black transition-all hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                                        >
                                            Next
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                            </>
                        )}

                        {activeSubTab === "requests" && (
                            <div className="space-y-4">
                                {requestActionMessage && (
                                    <div className="rounded-xl border-2 border-emerald-500/40 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800">
                                        {requestActionMessage}
                                    </div>
                                )}
                                {requestsError && (
                                    <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                        <Icon name="AlertTriangle" size={14} />
                                        <span>{requestsError}</span>
                                    </div>
                                )}
                                {requestsLoading ? (
                                    <div className={`${CRMS_CARD} flex h-96 w-full flex-col items-center justify-center space-y-3`}>
                                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/60">Syncing access requests...</p>
                                    </div>
                                ) : requests.length === 0 ? (
                                    <div className={`${CRMS_CARD} flex h-64 w-full flex-col items-center justify-center space-y-2 border-dashed`}>
                                        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-black">No access requests</p>
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/55">Citizen requests for your cases will appear here.</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {requests.map((req) => (
                                            <div key={req.request_id} className={CRMS_CARD}>
                                                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                                    <div className="flex-1 space-y-2">
                                                        <div className="flex flex-wrap items-center gap-3">
                                                            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                                                                {req.case_id_display || `BLR-${String(req.case_id).padStart(3, "0")}`}
                                                            </span>
                                                            {requestStatusBadge(req.status)}
                                                        </div>
                                                        <h3 className="text-base font-semibold text-black">
                                                            {req.case_title || "Case dossier access request"}
                                                        </h3>
                                                        <p className="text-xs font-medium text-black/70">
                                                            <span className="font-semibold uppercase tracking-[0.08em] text-black/50">Requester:</span>{" "}
                                                            {req.requester_name} · {req.requester_email} · {req.requester_number}
                                                        </p>
                                                        <p className="rounded-xl border-2 border-black/10 bg-white/70 p-3 text-xs leading-relaxed text-black/80">
                                                            {req.reason}
                                                        </p>
                                                        <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-black/50">
                                                            Filed: {req.requested_at ? new Date(req.requested_at).toLocaleString() : "N/A"}
                                                            {req.decided_by_name ? ` · Decided by ${req.decided_by_name}` : ""}
                                                        </p>
                                                    </div>
                                                    {req.status === "Pending" && (
                                                        <div className="flex shrink-0 gap-2">
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDecide(req.request_id, "approve")}
                                                                disabled={decidingRequestId === req.request_id}
                                                                className="rounded-full border-2 border-emerald-600 bg-emerald-50 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-900 transition-all hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                                                            >
                                                                {decidingRequestId === req.request_id ? "Processing..." : "Approve"}
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDecide(req.request_id, "reject")}
                                                                disabled={decidingRequestId === req.request_id}
                                                                className="rounded-full border-2 border-rose-500 bg-rose-50 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-900 transition-all hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                                                            >
                                                                Decline
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                    {/* RENDER DETAILED VIEW MODAL */}
                    {selectedCase && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
                            <motion.div
                                className={`max-h-[90vh] w-full max-w-2xl overflow-y-auto ${CRMS_CARD}`}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.35 }}
                            >
                                <div className="mb-4 flex items-center justify-between border-b-2 border-black/10 pb-4">
                                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">
                                        Case: {selectedCase.display_id || `BLR-${String(selectedCase.case_id).padStart(3, '0')}`}
                                    </span>
                                    <button type="button" onClick={() => setSelectedCase(null)} className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black text-black hover:bg-black hover:text-white">
                                        <Icon name="X" size={14} />
                                    </button>
                                </div>
                                <div className="space-y-4 text-xs">
                                    <div>
                                        <div className={CRMS_LABEL}>Incident Heading</div>
                                        <div className="mt-0.5 text-sm font-semibold text-black">{selectedCase.title}</div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 border-y-2 border-black/10 py-3">
                                        <div>
                                            <div className={CRMS_LABEL}>Classification</div>
                                            <div className="mt-0.5 font-medium text-black">{selectedCase.crime_type}</div>
                                        </div>
                                        <div>
                                            <div className={CRMS_LABEL}>Status</div>
                                            <div className="mt-0.5 font-medium text-black">{selectedCase.status}</div>
                                        </div>
                                        <div>
                                            <div className={CRMS_LABEL}>Location</div>
                                            <div className="mt-0.5 font-medium text-black">{selectedCase.location || "Not Registered"}</div>
                                        </div>
                                        <div>
                                            <div className={CRMS_LABEL}>Record Date</div>
                                            <div className="mt-0.5 font-medium text-black">{selectedCase.date_added || "N/A"}</div>
                                        </div>
                                    </div>
                                    <div>
                                        <div className={CRMS_LABEL}>Case Narrative</div>
                                        <div className="mt-1 whitespace-pre-wrap rounded-xl border-2 border-black/10 bg-white/70 p-3 text-sm leading-relaxed text-black/85">
                                            {selectedCase.description || "No documentation detailed."}
                                        </div>
                                    </div>
                                    <div className="rounded-xl border-2 border-black/10 bg-white/70 p-3">
                                        <div className={`${CRMS_LABEL} mb-1`}>Complainant</div>
                                        <div className="text-black/70">Name: <span className="font-semibold text-black">{selectedCase.complainant_name || "Anonymous / Guarded"}</span></div>
                                        <div className="text-black/70">Contact: <span className="font-semibold text-black">{selectedCase.complainant_contact || "N/A"}</span></div>
                                        <div className="text-black/70">Aadhaar (Last 4): <span className="font-semibold text-black">{selectedCase.complainant_aadhaar || "XXXX"}</span></div>
                                    </div>

                                    <div className="rounded-xl border-2 border-accent/30 bg-accent/5 p-4">
                                        <div className={`${CRMS_LABEL} mb-2`}>Update Case Status</div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            {["Active", "Solved", "Closed"].map(statusOption => (
                                                <button
                                                    key={statusOption}
                                                    type="button"
                                                    onClick={() => handleCaseStatusUpdate(selectedCase.case_id, statusOption)}
                                                    disabled={selectedCase.status === statusOption}
                                                    className={`rounded-full border-2 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] transition-all ${
                                                        selectedCase.status === statusOption
                                                            ? "cursor-not-allowed border-black/20 bg-black/5 text-black/40 opacity-50"
                                                            : statusOption === "Active"
                                                            ? "border-amber-500 bg-amber-50 text-amber-900 hover:bg-amber-100"
                                                            : statusOption === "Solved"
                                                            ? "border-emerald-600 bg-emerald-50 text-emerald-900 hover:bg-emerald-100"
                                                            : "border-black/30 bg-white/80 text-black hover:bg-black hover:text-white"
                                                    }`}
                                                >
                                                    {statusOption === "Active" ? "Mark Active" : statusOption === "Solved" ? "Mark Solved" : "Mark Closed"}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        </div>
                    )}
                    </motion.div>
                </CrmsPageShell>
            );
        };

        // ─── LOGIN PAGE ───────────────────────────────────────────────────────
        const LoginPage = ({ onLogin, onBack }) => {
            const [badgeId, setBadgeId]   = useState("");
            const [password, setPassword] = useState("");
            const [error, setError]       = useState("");
            const [loading, setLoading]   = useState(false);

            const handleLogin = async (e) => {
                e.preventDefault();
                setError("");
                setLoading(true);
                try {
                    // Get CAPTCHA token
                    const captchaToken = await executeRecaptcha("login");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required to log in");
                        return;
                    }
                    const res = await apiFetch("/auth/login", {
                        method: "POST",
                        body: JSON.stringify({ badge_id: badgeId, password, captcha_token: captchaToken }),
                    });
                    onLogin(res.officer || res.data);
                } catch (err) {
                    setError(err.message || "Invalid credentials");
                } finally {
                    setLoading(false);
                }
            };

            return (
                <CrmsPageShell
                    title="Staff Login"
                    subtitle="Bengaluru Police Department · CRMS"
                    onBack={onBack}
                    scrim="bg-white/45"
                    className="flex flex-col"
                >
                    <div className="flex flex-1 items-center justify-center px-5 py-12">
                        <motion.div
                            className={`w-full max-w-md ${CRMS_CARD}`}
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                        >
                            <div className="mb-10 text-center">
                                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border-2 border-black bg-white">
                                    <Icon name="Shield" size={24} className="text-black" />
                                </div>
                                <h1 className="mb-1 text-xl font-semibold uppercase tracking-[0.12em] text-black sm:text-2xl">Staff Login</h1>
                                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-black/65 sm:text-xs">Secure officer access</p>
                            </div>

                            <form onSubmit={handleLogin} className="space-y-5">
                                <div>
                                    <label className={CRMS_LABEL}>Officer Badge ID</label>
                                    <input autoFocus type="text" required value={badgeId}
                                        onChange={e => setBadgeId(e.target.value)}
                                        className={`${CRMS_INPUT} font-mono`}
                                        placeholder="e.g., BPD-7821" />
                                </div>
                                <div>
                                    <label className={CRMS_LABEL}>Password</label>
                                    <input type="password" required value={password}
                                        onChange={e => setPassword(e.target.value)}
                                        className={CRMS_INPUT}
                                        placeholder="••••••••" />
                                </div>
                                {error && (
                                    <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                        <Icon name="AlertTriangle" size={14} /> {error}
                                    </div>
                                )}
                                <button type="submit" disabled={loading}
                                    className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 ${loading ? "cursor-not-allowed opacity-60" : ""}`}>
                                    <Icon name={loading ? "Clock" : "Lock"} size={16} />
                                    {loading ? "Authenticating..." : "Sign In"}
                                </button>
                            </form>

                            <div className="mt-8 rounded-xl border-2 border-black/15 bg-white/60 p-4">
                                <p className="mb-2 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-black/50">Development credentials</p>
                                <p className="text-center text-xs font-medium text-black/80">Badge: <span className="font-mono font-semibold">BPD-7821</span> · Password: <span className="font-mono font-semibold">crms1234</span></p>
                                <p className="mt-1 text-center text-[10px] font-semibold uppercase tracking-[0.1em] text-black/50">(Inspector = read+write · Sub-Inspector = read only)</p>
                            </div>
                        </motion.div>
                    </div>
                </CrmsPageShell>
            );
        };

        // ─── APP ──────────────────────────────────────────────────────────────
        const App = () => {
            const [currentView, setCurrentView] = useState("landing");
            const [officer, setOfficer]         = useState(null);

            // Map DB role to legacy P1/P2 gate the dashboard already uses
            const userRole = officer?.role === "inspector" ? "P1" : "P2";

            const handleLogin = (officerData) => {
                setOfficer(officerData);
                setCurrentView("staff");
            };

            const handleLogout = () => {
                setOfficer(null);
                setCurrentView("landing");
            };

            return (
                <div className="min-h-screen">
                    <AnimatePresence mode="wait">
                        {currentView === "landing" && (
                            <motion.div key="landing" className="min-h-[100dvh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.5 }}>
                                <LandingPage onNavigate={setCurrentView} />
                            </motion.div>
                        )}
                        {currentView === "public" && (
                            <motion.div key="public" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
                                <PublicPortal onNavigate={setCurrentView} />
                            </motion.div>
                        )}
                        {currentView === "login" && (
                            <motion.div key="login" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
                                <LoginPage onLogin={handleLogin} onBack={() => setCurrentView("landing")} />
                            </motion.div>
                        )}
                        {currentView === "staff" && officer && (
                            <motion.div key="staff" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.4 }}>
                                <StaffDashboard onNavigate={setCurrentView} userRole={userRole} officer={officer} onLogout={handleLogout} />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            );
        };

        const root = ReactDOM.createRoot(document.getElementById("root"));
        root.render(<App />);
    </script>
</body>
</html>
````

## File: .env.example
````
# ============================================================================
# DATABASE CONFIGURATION (Required)
# ============================================================================
# The hostname where your MySQL database is running
DB_HOST=localhost

# The port where your MySQL server is listening (default: 3306)
DB_PORT=3306

# MySQL username for database access
DB_USER=your_db_username

# MySQL password for database access
# IMPORTANT: Keep this secret! Never commit actual passwords to git.
DB_PASSWORD=your_db_password

# Name of the database to use
DB_NAME=crms

# ============================================================================
# FLASK SERVER CONFIGURATION (Required)
# ============================================================================
# The host to bind Flask to (0.0.0.0 = all interfaces, 127.0.0.1 = localhost only)
FLASK_HOST=0.0.0.0

# The port where Flask development server runs
FLASK_PORT=5000

# Enable/disable Flask debug mode (true for development, false for production)
# Debug mode: auto-reloads code, shows interactive debugger, detailed errors
# Production mode: better performance, no debugger, generic error pages
FLASK_DEBUG=false

# ============================================================================
# CORS CONFIGURATION (Optional)
# ============================================================================
# Allowed origins for CORS (Cross-Origin Resource Sharing)
# Use "*" to allow all origins (not recommended for production)
# For production, specify exact domain: https://yourfrontend.com
CORS_ORIGIN=*

# ============================================================================
# reCAPTCHA v2 (Invisible) CONFIGURATION (Required)
# ============================================================================
# Get these keys from: https://www.google.com/recaptcha/admin
# These are TEST keys for localhost development:
# - Site Key (Public): 6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI
# - Secret Key (Private): 6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe
#
# For production, generate your own keys and keep SECRET_KEY safe!

# reCAPTCHA Secret Key (private - never expose publicly)
RECAPTCHA_SECRET_KEY=your_recaptcha_secret_key_here

# reCAPTCHA Site/Public Key (public - safe to expose in frontend)
RECAPTCHA_PUBLIC_KEY=your_recaptcha_public_key_here

# reCAPTCHA Scoring Threshold (v3 only, not used for v2)
# Minimum score threshold for reCAPTCHA v3 (0.0 to 1.0)
# Only used if implementing reCAPTCHA v3 in the future
# 0.0 = allow everything, 1.0 = very strict
RECAPTCHA_THRESHOLD=0.5

# ============================================================================
# SMTP EMAIL CONFIGURATION (Optional - Fallback is Offline Mock Mode)
# ============================================================================

# SMTP_FROM_NAME=Bengaluru Police CRMS Team
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Bengaluru Police CRMS Team
````

## File: .gitignore
````
pycache/
*.py[cod]
*.pyo
*.pyd
*.so
*.egg
*.egg-info/
dist/
build/
.eggs/
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
venv/
.venv/
env/
ENV/

node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
dist/
build/
.next/
.nuxt/
.svelte-kit/
coverage/

.env
.env.*
!.env.example

.vscode/
.idea/
*.swp
*.swo
*~

.DS_Store
Thumbs.db

*.log
logs/

*.sqlite3
*.db

tmp/
temp/
.cache/

*.pid
docker-compose.override.yml


*CAPTCHA*
````

## File: LICENCE
````
Copyright <2026> <ADARSH VH, ADITHYA BK, ADITI AM, AMOGH JP>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
````

## File: Procfile
````
web: gunicorn Backend.app:app
````

## File: README.md
````markdown
# CRMS — Crime Record Management System

A police investigation dashboard for the Bengaluru Police Department, built with Flask, MySQL, and a React-powered single-page frontend. CRMS supports officer case management, citizen complaint intake, automated case assignment, and a secure case-access request workflow with PDF dossier delivery.

## Features

- **Staff portal** — Role-based login, case CRUD, officer assignments, analytics, and case status updates
- **Public portal** — Citizens can file complaints and request access to case records (reCAPTCHA protected)
- **Automated assignment** — Background scheduler promotes pending complaints to cases and assigns officers by crime severity and workload
- **Access request workflow** — Officers approve or reject citizen dossier requests; approved requests trigger a PDF case dossier via email (or mock mode)
- **Security** — bcrypt password hashing, invisible reCAPTCHA on public forms and login, role-based case visibility, `X-Officer-Id` header on protected routes

## Contents

| Path | Description |
|------|-------------|
| `Backend/` | Flask API, SQL migrations, assignment engine, email/PDF utilities |
| `Frontend/crms_frontend.html` | React UI (CDN-based) served at `/` |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

## Prerequisites

- Python 3.10+
- MySQL 8.x
- Google reCAPTCHA v2 (invisible) keys — [reCAPTCHA admin](https://www.google.com/recaptcha/admin) (test keys work on localhost)

## Quick Start

### 1. Clone and configure environment

```bash
cp .env.example .env
```

Edit `.env` with your MySQL credentials and reCAPTCHA keys. See [Environment Variables](#environment-variables) for the full list.

> Do not commit `.env` to source control.

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize the database

Run the scripts **in order** against your MySQL server:

```bash
mysql -u root -p < Backend/setup_db.sql
mysql -u root -p < Backend/migrate_v2.sql
mysql -u root -p < Backend/migrate_v3.sql
```

Replace `root` with your MySQL user if different. Each script is additive and safe to re-run where noted (`CREATE TABLE IF NOT EXISTS`, etc.).

| Script | Purpose |
|--------|---------|
| `setup_db.sql` | Core schema, seed officers and sample cases |
| `migrate_v2.sql` | Officer auth (`password_hash`, `role`), public complaints staging |
| `migrate_v3.sql` | Case access requests table and seed data |

### 4. Start the server

```bash
python3 Backend/app.py
```

Expected startup banner:

```text
============================================================
  CRMS Flask API — Bengaluru Police Department
============================================================
```

Open **http://localhost:5000** in your browser. The Flask app serves the frontend and API from the same origin.

### 5. Sign in (development)

After running `migrate_v2.sql`, seeded officers use this default password:

| Field | Value |
|-------|-------|
| Password | `crms1234` |
| Badge ID | e.g. `BPD-7821` (Inspector Arjun Nair) |

Inspectors (`Inspector Arjun Nair`, `Inspector Vikram Rao`, `Inspector Meera Iyer`) can create and edit cases. Other seeded officers are **viewer** (read-only for assigned cases). Change passwords before any production deployment.

## Environment Variables

All runtime configuration is loaded from `.env` via `python-dotenv` in `Backend/config.py`.

### Database (required)

| Variable | Description |
|----------|-------------|
| `DB_HOST` | MySQL host |
| `DB_PORT` | MySQL port (default `3306`) |
| `DB_USER` | MySQL username |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | Database name (`crms`) |

### Flask (required)

| Variable | Description |
|----------|-------------|
| `FLASK_HOST` | Bind address (`0.0.0.0` or `127.0.0.1`) |
| `FLASK_PORT` | Port (default `5000`) |
| `FLASK_DEBUG` | `true` or `false` |

### CORS (optional)

| Variable | Description |
|----------|-------------|
| `CORS_ORIGIN` | Allowed origin (`*` for dev; set to your domain in production) |

### reCAPTCHA v2 invisible (required in config)

| Variable | Description |
|----------|-------------|
| `RECAPTCHA_SECRET_KEY` | Server-side secret key |
| `RECAPTCHA_PUBLIC_KEY` | Site key (used by the frontend) |
| `RECAPTCHA_THRESHOLD` | Reserved for v3 scoring (unused for v2) |

For local testing without verification, you can leave `RECAPTCHA_SECRET_KEY` empty — the backend skips CAPTCHA checks when the secret is missing.

### SMTP email (optional)

When SMTP is not configured, approved access requests are written to `Backend/mock_emails/` as JSON logs and PDF files instead of sending live email.

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (e.g. `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `SMTP_FROM_EMAIL` | Sender address |
| `SMTP_FROM_NAME` | Sender display name |

## Project Structure

```text
.
├── .env.example
├── requirements.txt
├── Backend/
│   ├── app.py                  # Flask routes and startup
│   ├── config.py               # Environment configuration
│   ├── db_connection.py        # MySQL connection pool
│   ├── queries.py              # All SQL / data access
│   ├── assignment_algorithm.py # Auto-assign pending complaints
│   ├── email_utils.py          # PDF dossier + SMTP / mock email
│   ├── setup_db.sql
│   ├── migrate_v2.sql
│   ├── migrate_v3.sql
│   └── mock_emails/            # Offline email/PDF output (dev)
└── Frontend/
    └── crms_frontend.html      # Public portal + staff dashboard
```

## API Overview

Responses use `{ "success": true, "data": ... }` or `{ "success": false, "error": "..." }`.

Protected staff routes expect the **`X-Officer-Id`** header (integer officer ID returned from login).

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

### Cases

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cases`, `/api/cases` | List cases (filters, pagination; role-based visibility) |
| `GET` | `/cases/<id>`, `/api/cases/<id>` | Case detail with assigned officers |
| `POST` | `/cases` | Create case (inspector role) |
| `PATCH` | `/cases/<id>` | Update case fields / status |
| `DELETE` | `/cases/<id>` | Delete case and assignments |
| `GET` | `/cases/<id>/officers` | Officers assigned to a case |

Query parameters for list: `status`, `crime_type`, `location`, `search`, `page`, `limit`.

### Officers & assignments

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/officers` | List officers |
| `POST` | `/officers` | Add officer |
| `GET` | `/case-officer` | All case–officer pairings |
| `POST` | `/case-officer` | Assign officer to case |
| `DELETE` | `/case-officer` | Remove assignment |

### Analytics & assignment engine

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics` | Dashboard analytics |
| `GET` | `/assignments/pending` | Queue of complaints awaiting auto-assignment |
| `POST` | `/assignments/process` | Manually run the assignment algorithm |

A background thread also runs the assignment algorithm every **10 seconds** while the server is running.

### Public portal (citizen)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/public/complaint` | Submit a complaint (staged for review / auto-promotion) |
| `POST` | `/public/access-request` | Request access to a case dossier |
| `GET` | `/stats` | Public statistics summary |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Officer login (`badge_id`, `password`, `captcha_token`) |

No JWT in this MVP — the client stores the officer record and sends `X-Officer-Id` on subsequent requests. Write endpoints validate role server-side.

### Public complaints (staff review)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/public-complaints` | List staged complaints (`?status=Pending`) |
| `POST` | `/public-complaints/<id>/promote` | Promote complaint to a full case |
| `POST` | `/public-complaints/<id>/reject` | Reject complaint |

### Case access requests (staff)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/access-requests` | List access requests (visibility by role/assignment) |
| `POST` | `/api/access-requests/<id>/approve` | Approve; sends PDF dossier email async |
| `POST` | `/api/access-requests/<id>/reject` | Reject; sends decline notification async |

## Frontend

The UI is a single HTML file using React, Tailwind CSS, Chart.js, and Framer Motion from CDNs.

| View | Description |
|------|-------------|
| **Public portal** | File complaints, request case access, view public stats |
| **Staff login** | Badge ID + password with reCAPTCHA |
| **Staff dashboard** | Cases (filter, paginate, update status), access request queue, analytics |

reCAPTCHA site key is read from the backend environment at runtime.

## Automated Case Assignment

When a citizen files a complaint, it lands in `public_complaints` with status `Pending`. The assignment engine (`assignment_algorithm.py`):

1. Maps `crime_type` to severity (e.g. Assault → Critical, Cyber Fraud → High)
2. Selects officers by rank, current workload, and seniority
3. Creates a case with `source='public'` and `case_officer` rows
4. Marks the complaint as `Promoted`

Inspectors and admins see all cases; viewers only see cases they are assigned to.

## Email & PDF Dossiers

On access request approval, `email_utils.py` generates a ReportLab PDF dossier and dispatches it asynchronously:

- **SMTP configured** — Email sent to the requester with the PDF attached
- **SMTP not configured** — Mock mode writes `email_*.json` and `*.pdf` under `Backend/mock_emails/`

Rejections send a notification email (or mock log) without an attachment.

## Security & Production

- Never commit `.env` or real credentials.
- Change default officer passwords from `migrate_v2.sql` before deployment.
- Restrict `CORS_ORIGIN` to your trusted frontend host.
- Keep `RECAPTCHA_SECRET_KEY` and `SMTP_PASSWORD` secret.
- Use HTTPS in production.
- Run behind a production WSGI server instead of the Flask dev server:

```bash
cd Backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

The development entrypoint calls `init_pool()` and `start_assignment_scheduler()` before `app.run()`. For Gunicorn, wire equivalent startup (e.g. a small `wsgi.py` or Gunicorn `post_fork` hook) so the DB pool and assignment scheduler are initialized in each worker as needed.

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| MySQL connection errors | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` in `.env` |
| Frontend not loading | Server running; visit `http://localhost:5000` |
| Login fails | Migrations run; badge ID exact (e.g. `BPD-7821`); password `crms1234` for dev seeds |
| CAPTCHA errors | Valid keys in `.env`, or empty `RECAPTCHA_SECRET_KEY` for local bypass |
| No email received | Configure SMTP vars, or inspect `Backend/mock_emails/` in mock mode |
| Missing access requests table | Run `Backend/migrate_v3.sql` |

## Dependencies

| Package | Role |
|---------|------|
| Flask | Web framework |
| flask-cors | CORS |
| mysql-connector-python | MySQL driver |
| python-dotenv | `.env` loading |
| bcrypt | Password hashing |
| requests | reCAPTCHA verification |
| reportlab | PDF dossier generation |
| gunicorn | Production WSGI server |
````

## File: requirements.txt
````
flask==3.0.3
flask-cors==4.0.1
mysql-connector-python==8.4.0
gunicorn==21.2.0
requests==2.31.0
python-dotenv==1.0.0
bcrypt==5.0.0
reportlab==4.1.0
````
