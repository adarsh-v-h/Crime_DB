# ─── Themis's Domain SQL Query Layer ──────────────────────────────────────────────────────
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

def submit_public_complaint(name, contact, email, aadhaar,
                             crime_type, location, complaint_mode, incident_desc):
    """
    Inserts a citizen complaint into the public_complaints staging table.
    Officers then review and promote to the main cases table.
    Returns the new complaint_id as the citizen's reference number.

    aadhaar: 12-digit Aadhaar number for identity anchoring.
    Never store this outside trusted systems unless absolutely required.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Create a preliminary case row so public complaints immediately
        # exist in the unified `cases` table while retaining the
        # `public_complaints` staging table for backward compatibility.
        title = f"{crime_type or 'Other'} - {location or ''}"
        new_case_id = None
        try:
            cur.execute(
                """INSERT INTO cases
                   (title, description, crime_type, `status`, `location`, complaint_mode,
                    complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (title, incident_desc or "", crime_type or "Other", 'Pending Review', location or "",
                 complaint_mode or "Online", name, contact or "", aadhaar or "", 'public')
            )
            new_case_id = cur.lastrowid
        except Exception:
            # If case insert fails for any reason, continue and still record the public complaint.
            new_case_id = None

        # Insert into public_complaints and link the generated case (if created).
        cur.execute(
            """INSERT INTO public_complaints
               (complainant_name, contact, email, aadhaar,
                crime_type, `location`, incident_desc, complaint_mode, promoted_case_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (name, contact, email or "", aadhaar,
             crime_type or "Other", location or "",
             incident_desc or "", complaint_mode or "Online", new_case_id)
        )
        complaint_id = cur.lastrowid
        conn.commit()
        return complaint_id
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

        # If a linked case already exists (inserted at submission time), simply
        # transition its status to Active and mark the complaint Promoted.
        linked_case_id = pc.get("promoted_case_id")
        if linked_case_id:
            cur.execute(
                "UPDATE cases SET `status` = 'Active', last_updated = NOW() WHERE case_id = %s",
                (linked_case_id,)
            )
            cur.execute(
                """UPDATE public_complaints
                   SET `status` = 'Promoted', reviewed_by = %s, reviewed_at = NOW()
                   WHERE complaint_id = %s""",
                (officer_id, complaint_id)
            )
            conn.commit()
            return linked_case_id

        # Fallback: no linked case found — create one (classic behaviour)
        title = f"{pc['crime_type']} - {pc['location']}"
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode,
                complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
               VALUES (%s, %s, %s, 'Active', %s, %s, %s, %s, %s, 'public', NOW())""",
            (title, pc["incident_desc"], pc["crime_type"], pc["location"],
             pc["complaint_mode"], pc["complainant_name"], pc["contact"], pc["aadhaar"])
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
        # Update the linked case status to 'Rejected' if it exists.
        cur.execute(
            "SELECT promoted_case_id FROM public_complaints WHERE complaint_id = %s",
            (complaint_id,)
        )
        row = cur.fetchone()
        if row and row[0]:
            cur.execute(
                "UPDATE cases SET `status` = 'Rejected', last_updated = NOW() WHERE case_id = %s",
                (row[0],)
            )

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
        o.setdefault("role",       "viewer")

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
# PUBLIC BROWSING — case discovery for citizens
# ──────────────────────────────────────────────────────────────────────────────

def get_public_cases(status=None, crime_type=None, location=None, search=None):
    """
    Returns public cases safe for citizen browsing.
    Returns only: case_id, title, crime_type, location, date_reported, status
    Filters: status, crime_type, location, search
    No authentication required.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = """
            SELECT case_id, title, crime_type, `status`, date_reported, `location`
            FROM cases
            WHERE 1=1
        """
        params = []

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
            sql += " AND (title LIKE %s)"
            params.append(f"%{search}%")

        sql += " ORDER BY date_reported DESC"

        cur.execute(sql, params)
        cases = _rows_to_list(cur, cur.fetchall())

        # Format dates and add display_id to each case
        for case in cases:
            if case.get("date_reported") and hasattr(case["date_reported"], "isoformat"):
                case["date_reported"] = case["date_reported"].isoformat()
            case["case_id_display"] = f"BLR-{str(case['case_id']).zfill(3)}"

        return cases
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


def get_highest_ranked_officer_on_case(case_id: int):
    """
    Returns the highest-ranked officer assigned to the case.
    Rank hierarchy: Inspector > Sub-Inspector > Head Constable > Constable > others.
    Returns dict with officer details or None if no officers assigned.
    """
    # Define rank hierarchy (higher number = higher rank)
    rank_hierarchy = {
        "Inspector": 4,
        "Sub-Inspector": 3,
        "Head Constable": 2,
        "Constable": 1,
    }
    
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Get all officers assigned to the case with their rank info
        cur.execute(
            """SELECT o.officer_id, o.`name`, o.`rank`, o.`role`, o.badge
               FROM officers o
               JOIN case_officer co ON o.officer_id = co.officer_id
               WHERE co.case_id = %s""",
            (case_id,)
        )
        officers = _rows_to_list(cur, cur.fetchall())
        
        if not officers:
            return None
        
        # Sort by rank hierarchy (descending)
        def rank_value(officer):
            rank = officer.get("rank", "")
            return rank_hierarchy.get(rank, 0)
        
        highest = max(officers, key=rank_value)
        return highest if rank_value(highest) > 0 else officers[0]  # Fallback to first if no recognized rank
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


def insert_case_update(case_id, officer_id, update_text):
    """Inserts a chronological timeline update for a case."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO case_updates (case_id, officer_id, update_text)
               VALUES (%s, %s, %s)""",
            (case_id, officer_id, update_text)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def get_case_updates(case_id):
    """Retrieves all timeline updates for a case, ordered chronologically."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT cu.*, o.name AS officer_name, o.rank AS officer_rank
               FROM case_updates cu
               JOIN officers o ON cu.officer_id = o.officer_id
               WHERE cu.case_id = %s
               ORDER BY cu.created_at ASC""",
            (case_id,)
        )
        rows = _rows_to_list(cur, cur.fetchall())
        for r in rows:
            if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        cur.close()
        conn.close()


def insert_case_evidence(case_id, officer_id, file_name, original_name, file_path, mime_type, file_size, description=None):
    """Inserts metadata for a new case evidence upload."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO case_evidence 
               (case_id, officer_id, file_name, original_name, file_path, mime_type, file_size, description)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (case_id, officer_id, file_name, original_name, file_path, mime_type, file_size, description)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def get_case_evidence(case_id):
    """Retrieves all evidence items for a case, ordered newest first."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT ce.*, o.name AS officer_name, o.rank AS officer_rank
               FROM case_evidence ce
               JOIN officers o ON ce.officer_id = o.officer_id
               WHERE ce.case_id = %s
               ORDER BY ce.created_at DESC""",
            (case_id,)
        )
        rows = _rows_to_list(cur, cur.fetchall())
        for r in rows:
            if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        cur.close()
        conn.close()


def get_evidence_by_id(evidence_id):
    """Retrieves evidence metadata by ID."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM case_evidence WHERE evidence_id = %s",
            (evidence_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(cur, row)
    finally:
        cur.close()
        conn.close()


def delete_case_evidence(evidence_id):
    """Deletes evidence metadata by ID."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM case_evidence WHERE evidence_id = %s",
            (evidence_id,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def get_admin_officer():
    """
    Looks up the admin officer.
    Identified by role = 'admin' or badge = 'ADM-0001'.
    Returns the officer dict, or None if not found.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM officers WHERE `role` = 'admin' OR badge = 'ADM-0001' LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(cur, row)
    finally:
        cur.close()
        conn.close()


def get_officers_assigned_to_case(case_id: int):
    """
    Returns a list of officer dicts assigned to the given case.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT o.* FROM officers o
               JOIN case_officer co ON o.officer_id = co.officer_id
               WHERE co.case_id = %s""",
            (case_id,)
        )
        return _rows_to_list(cur, cur.fetchall())
    finally:
        cur.close()
        conn.close()

