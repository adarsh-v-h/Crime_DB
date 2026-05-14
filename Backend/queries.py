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

def get_all_cases(status=None, crime_type=None, location=None, search=None):
    """
    Returns all cases, optionally filtered.
    Also attaches the list of officer_ids for each case (from case_officer).
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql    = "SELECT * FROM cases WHERE 1=1"
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
