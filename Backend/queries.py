# ─── CRMS SQL Query Layer ──────────────────────────────────────────────────────
# All raw SQL lives here. app.py never constructs SQL directly.
# Every function opens its own connection, executes, commits if needed, and closes.

from db_connection import get_db

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


def insert_case(title, description, crime_type, status, location, complaint_mode):
    """Inserts a new case and returns its new case_id."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode, last_updated)
               VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
            (title, description, crime_type, status, location, complaint_mode)
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
        return _row_to_dict(cur, row)
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

def submit_public_complaint(name, contact, email, crime_type, location, complaint_mode, incident_desc):
    """
    Inserts a citizen complaint directly into the cases table as a new Active case.
    Returns the new case_id so the frontend can show a reference number.
    """
    title = f"{crime_type} — {location}" if location else f"{crime_type} complaint"
    conn  = get_db()
    cur   = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO cases
               (title, description, crime_type, `status`, `location`, complaint_mode, last_updated)
               VALUES (%s, %s, %s, 'Active', %s, %s, NOW())""",
            (title, incident_desc or "", crime_type or "Other", location or "", complaint_mode or "Online")
        )
        conn.commit()
        new_id = cur.lastrowid
        return new_id
    finally:
        cur.close()
        conn.close()
