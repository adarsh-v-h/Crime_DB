# ─── Themis's Domain SQL Query Layer ──────────────────────────────────────────────────────
# All raw SQL lives here. app.py never constructs SQL directly.
# Every function opens its own connection, executes, commits if needed, and closes.

try:
    from .db_connection import get_db
except ImportError:
    from db_connection import get_db
import bcrypt
import secrets

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _row_to_dict(cursor, row):
    """Converts a DB row tuple into a dict keyed by column names."""
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_list(cursor, rows):
    return [_row_to_dict(cursor, r) for r in rows]


def ensure_auth_schema():
    """Creates the officer session table used for single-device login enforcement."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS officer_sessions (
                session_id INT NOT NULL AUTO_INCREMENT,
                officer_id INT NOT NULL,
                session_token CHAR(64) NOT NULL,
                user_agent VARCHAR(255) DEFAULT NULL,
                ip_address VARCHAR(64) DEFAULT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                revoked_at DATETIME DEFAULT NULL,
                PRIMARY KEY (session_id),
                UNIQUE KEY uk_session_token (session_token),
                INDEX idx_officer_active (officer_id, revoked_at, expires_at),
                CONSTRAINT fk_session_officer
                    FOREIGN KEY (officer_id) REFERENCES officers(officer_id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ensure_geocode_schema():
    """
    Creates the geocode cache table — a permanent, shared store of
    place-name -> lat/lng so the map never re-geocodes the same place.
    `place_key` is the normalized lookup key (e.g. "station:Whitefield PS").
    A resolved=0 row records a confirmed miss so we don't retry forever.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS geocode_cache (
                place_key   VARCHAR(255) NOT NULL,
                lat         DOUBLE DEFAULT NULL,
                lng         DOUBLE DEFAULT NULL,
                resolved    TINYINT(1) NOT NULL DEFAULT 0,
                updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (place_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_geocode_cache():
    """Returns the full geocode cache as {place_key: {lat, lng, resolved}}."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT place_key, lat, lng, resolved FROM geocode_cache")
        out = {}
        for key, lat, lng, resolved in cur.fetchall():
            out[key] = {
                "lat": float(lat) if lat is not None else None,
                "lng": float(lng) if lng is not None else None,
                "resolved": bool(resolved),
            }
        return out
    finally:
        cur.close()
        conn.close()


def upsert_geocode(place_key, lat, lng, resolved):
    """Inserts or updates a single geocode cache entry."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO geocode_cache (place_key, lat, lng, resolved)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE lat = VALUES(lat), lng = VALUES(lng),
                                       resolved = VALUES(resolved)""",
            (place_key, lat, lng, 1 if resolved else 0)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# CASES
# ──────────────────────────────────────────────────────────────────────────────

def count_cases(status=None, crime_type=None, location=None, search=None, officer_id=None, bypass_visibility=False):
    """Counts cases using the same filters and visibility rules as get_all_cases."""
    conn = get_db()
    cur = conn.cursor()
    try:
        sql = "SELECT COUNT(*) FROM cases WHERE 1=1"
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

        cur.execute(sql, params)
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def get_all_cases(status=None, crime_type=None, location=None, search=None, officer_id=None, bypass_visibility=False, limit=None, offset=0):
    """
    Returns all cases, optionally filtered.
    If bypass_visibility is False and officer_id is provided, returns only cases assigned to that officer.
    Also attaches the list of officer_ids for each case (from case_officer).
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Single JOIN query: pull the cases AND their assigned officer_ids in one
        # round trip. GROUP_CONCAT collapses the case_officer rows into a CSV that
        # we split back into a list below — no second query needed.
        # Explicit columns (every field a consumer reads); `source` is omitted as
        # it is unused anywhere in the backend or frontend.
        sql = """SELECT c.case_id, c.title, c.description, c.crime_type, c.`status`,
                        c.date_reported, c.`location`, c.complaint_mode, c.last_updated,
                        c.complainant_name, c.complainant_contact, c.complainant_aadhaar,
                        GROUP_CONCAT(co.officer_id ORDER BY co.officer_id) AS officer_ids_csv
                 FROM cases c
                 LEFT JOIN case_officer co ON c.case_id = co.case_id
                 WHERE 1=1"""
        params = []

        if not bypass_visibility and officer_id is not None:
            sql += " AND c.case_id IN (SELECT case_id FROM case_officer WHERE officer_id = %s)"
            params.append(officer_id)

        if status and status != "All":
            sql += " AND c.`status` = %s"
            params.append(status)

        if crime_type and crime_type != "All":
            sql += " AND c.crime_type = %s"
            params.append(crime_type)

        if location:
            sql += " AND c.`location` LIKE %s"
            params.append(f"%{location}%")

        if search:
            sql += " AND (c.title LIKE %s OR c.`location` LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        sql += " GROUP BY c.case_id ORDER BY c.date_reported DESC"

        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

        cur.execute(sql, params)
        cases = _rows_to_list(cur, cur.fetchall())

        for case in cases:
            csv = case.pop("officer_ids_csv", None)
            case["officer_ids"] = [int(x) for x in csv.split(",")] if csv else []

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
        # Single query: case row + its assigned officer_ids via GROUP_CONCAT.
        # Explicit columns (union of all consumer needs); `source` omitted (unused).
        cur.execute(
            """SELECT c.case_id, c.title, c.description, c.crime_type, c.`status`,
                      c.date_reported, c.`location`, c.complaint_mode, c.last_updated,
                      c.complainant_name, c.complainant_contact, c.complainant_aadhaar,
                      GROUP_CONCAT(co.officer_id ORDER BY co.officer_id) AS officer_ids_csv
               FROM cases c
               LEFT JOIN case_officer co ON c.case_id = co.case_id
               WHERE c.case_id = %s
               GROUP BY c.case_id""",
            (case_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        case = _row_to_dict(cur, row)

        csv = case.pop("officer_ids_csv", None)
        case["officer_ids"] = [int(x) for x in csv.split(",")] if csv else []

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

def get_all_officers(limit=None, offset=0):
    """
    Returns all officers with computed active_cases and solved_cases counts
    so the frontend Analytics workload bar renders correctly.
    Pass limit/offset for server-side pagination; omit for unbounded results.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = (
            """SELECT
                 o.*,
                 COALESCE(w.active_cases, 0) AS active_cases,
                 COALESCE(w.solved_cases, 0) AS solved_cases
               FROM officers o
               LEFT JOIN (
                 SELECT
                   co.officer_id,
                   SUM(c.`status` = 'Active') AS active_cases,
                   SUM(c.`status` = 'Solved') AS solved_cases
                 FROM case_officer co
                 JOIN cases c ON co.case_id = c.case_id
                 GROUP BY co.officer_id
               ) w ON o.officer_id = w.officer_id
               ORDER BY o.officer_id"""
        )
        params = []
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

        cur.execute(sql, params)
        officers = _rows_to_list(cur, cur.fetchall())

        for officer in officers:
            oid = officer["officer_id"]

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


def count_officers():
    """Total officer count for pagination."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM officers")
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def get_officers_not_on_case(case_id: int):
    """
    Returns all officers NOT currently assigned to the given case, with their
    computed active/solved case counts — in a single query using an anti-join.
    Replaces the old approach of loading all officers + the case and filtering
    in Python.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT
                 o.*,
                 COALESCE(w.active_cases, 0) AS active_cases,
                 COALESCE(w.solved_cases, 0) AS solved_cases
               FROM officers o
               LEFT JOIN (
                 SELECT
                   co.officer_id,
                   SUM(c.`status` = 'Active') AS active_cases,
                   SUM(c.`status` = 'Solved') AS solved_cases
                 FROM case_officer co
                 JOIN cases c ON co.case_id = c.case_id
                 GROUP BY co.officer_id
               ) w ON o.officer_id = w.officer_id
               WHERE o.officer_id NOT IN (
                 SELECT officer_id FROM case_officer WHERE case_id = %s
               )
               ORDER BY o.officer_id""",
            (case_id,)
        )
        officers = _rows_to_list(cur, cur.fetchall())

        for officer in officers:
            oid = officer["officer_id"]
            officer.setdefault("badge",      f"BPD-{1000 + oid}")
            officer.setdefault("station",    "Bengaluru City Police")
            officer.setdefault("phone",      "")
            officer.setdefault("email",      "")
            officer.setdefault("join_date",  "")
            officer.pop("password_hash", None)

        return officers
    finally:
        cur.close()
        conn.close()


def get_officer_by_id(officer_id):
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Explicit columns only — never select password_hash here, and skip
        # columns no consumer reads (station/phone/join_date).
        cur.execute(
            """SELECT officer_id, `name`, `rank`, badge, email, `role`
               FROM officers WHERE officer_id = %s""",
            (officer_id,)
        )
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


def get_all_assignments(limit=None, offset=0):
    """
    JOIN query across all three tables.
    Returns one row per case–officer pair — exactly what the Assignments view needs.
    Pass limit/offset for server-side pagination; omit for the full list.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = (
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
        params = []
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

        cur.execute(sql, params)
        return _rows_to_list(cur, cur.fetchall())
    finally:
        cur.close()
        conn.close()


def count_assignments():
    """Total case-officer assignment count for pagination."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM case_officer")
        return cur.fetchone()[0]
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


def get_map_data():
    """
    Aggregated data for the admin map view.
      - stations: distinct officer stations (green markers) with officer counts
      - case_locations: distinct case locations (red markers) with case counts
        plus a status breakdown so the frontend can colour/label them.
    Aggregating server-side keeps the payload small and avoids overlapping markers
    for the same place. Geocoding (name -> lat/lng) happens client-side.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Police stations — distinct, non-empty officer.station values.
        cur.execute(
            """SELECT station, COUNT(*) AS officer_count
               FROM officers
               WHERE station IS NOT NULL AND TRIM(station) <> ''
               GROUP BY station
               ORDER BY officer_count DESC"""
        )
        stations = [
            {"station": r[0], "officer_count": int(r[1])}
            for r in cur.fetchall()
        ]

        # Case locations — distinct, non-empty case.location values with counts
        # and a per-location active count for richer marker tooltips.
        cur.execute(
            """SELECT `location`,
                      COUNT(*) AS case_count,
                      COALESCE(SUM(`status` = 'Active'), 0) AS active_count,
                      COALESCE(SUM(`status` = 'Solved'), 0) AS solved_count
               FROM cases
               WHERE `location` IS NOT NULL AND TRIM(`location`) <> ''
               GROUP BY `location`
               ORDER BY case_count DESC"""
        )
        case_locations = [
            {
                "location": r[0],
                "case_count": int(r[1]),
                "active_count": int(r[2]),
                "solved_count": int(r[3]),
            }
            for r in cur.fetchall()
        ]

        return {"stations": stations, "case_locations": case_locations}
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


def get_public_complaints(status=None, limit=None, offset=0):
    """Returns all public complaints (for officer review dashboard)."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Explicit columns (full set the review API exposes) — no SELECT *.
        sql = """SELECT complaint_id, complainant_name, contact, email, aadhaar,
                        crime_type, `location`, incident_desc, complaint_mode,
                        `status`, promoted_case_id, submitted_at, reviewed_by, reviewed_at
                 FROM public_complaints WHERE 1=1"""
        params = []
        if status:
            sql += " AND `status` = %s"
            params.append(status)
        sql += " ORDER BY submitted_at DESC"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])
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


def count_public_complaints(status=None):
    """Counts public complaints using the same status filter as get_public_complaints."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = "SELECT COUNT(*) FROM public_complaints WHERE 1=1"
        params = []
        if status:
            sql += " AND `status` = %s"
            params.append(status)
        cur.execute(sql, params)
        return cur.fetchone()[0]
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
        cur.execute(
            """SELECT complaint_id, complainant_name, contact, aadhaar, crime_type,
                      `location`, incident_desc, complaint_mode, promoted_case_id
               FROM public_complaints WHERE complaint_id = %s""",
            (complaint_id,)
        )
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
    Returns the officer dictionary (including password_hash for auth flows) or None.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT officer_id, `name`, `rank`, badge, email, `role`, password_hash
               FROM officers WHERE badge = %s LIMIT 1""",
            (badge,)
        )
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
        # Single conditional-aggregate query for both counts (was two COUNT(*) queries).
        cur.execute(
            """SELECT
                 COALESCE(SUM(c.`status` = 'Active'), 0) AS active_cases,
                 COALESCE(SUM(c.`status` = 'Solved'), 0) AS solved_cases
               FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s""",
            (oid,)
        )
        active, solved = cur.fetchone()
        o["active_cases"] = int(active or 0)
        o["solved_cases"] = int(solved or 0)

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


def officer_has_active_session(officer_id: int) -> bool:
    """Returns True when the officer already has a non-expired, non-revoked session."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE officer_sessions
               SET revoked_at = NOW()
               WHERE officer_id = %s
                 AND revoked_at IS NULL
                 AND expires_at <= NOW()""",
            (officer_id,)
        )
        conn.commit()
        cur.execute(
            """SELECT 1 FROM officer_sessions
               WHERE officer_id = %s
                 AND revoked_at IS NULL
                 AND expires_at > NOW()
               LIMIT 1""",
            (officer_id,)
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def create_officer_session(officer_id: int, ttl_hours: int, user_agent=None, ip_address=None):
    """Creates an active login session token for an officer."""
    token = secrets.token_hex(32)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO officer_sessions
               (officer_id, session_token, user_agent, ip_address, expires_at)
               VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s HOUR))""",
            (officer_id, token, (user_agent or "")[:255], (ip_address or "")[:64], ttl_hours)
        )
        conn.commit()
        cur.execute(
            "SELECT expires_at FROM officer_sessions WHERE session_token = %s",
            (token,)
        )
        row = cur.fetchone()
        expires_at = row[0].isoformat() if row and hasattr(row[0], "isoformat") else str(row[0])
        return token, expires_at
    finally:
        cur.close()
        conn.close()


def validate_officer_session(officer_id: int, session_token: str) -> bool:
    """Checks whether the token belongs to the officer and is still active."""
    if not session_token:
        return False
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT 1 FROM officer_sessions
               WHERE officer_id = %s
                 AND session_token = %s
                 AND revoked_at IS NULL
                 AND expires_at > NOW()
               LIMIT 1""",
            (officer_id, session_token)
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def revoke_officer_session(officer_id: int, session_token: str) -> int:
    """Revokes a specific active officer session."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE officer_sessions
               SET revoked_at = NOW()
               WHERE officer_id = %s
                 AND session_token = %s
                 AND revoked_at IS NULL""",
            (officer_id, session_token)
        )
        conn.commit()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()


def revoke_all_officer_sessions(officer_id: int) -> int:
    """Revokes ALL active sessions for an officer (used by force-login flow)."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE officer_sessions
               SET revoked_at = NOW()
               WHERE officer_id = %s
                 AND revoked_at IS NULL""",
            (officer_id,)
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
            """SELECT officer_id, `name`, `rank`, badge, email, `role`, password_hash
               FROM officers WHERE badge = %s OR `name` = %s LIMIT 1""",
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

        # Attach computed case counts — single conditional-aggregate query.
        oid = o["officer_id"]
        cur.execute(
            """SELECT
                 COALESCE(SUM(c.`status` = 'Active'), 0) AS active_cases,
                 COALESCE(SUM(c.`status` = 'Solved'), 0) AS solved_cases
               FROM case_officer co
               JOIN cases c ON co.case_id = c.case_id
               WHERE co.officer_id = %s""",
            (oid,)
        )
        active, solved = cur.fetchone()
        o["active_cases"] = int(active or 0)
        o["solved_cases"] = int(solved or 0)

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

def get_public_cases(status=None, crime_type=None, location=None, search=None, limit=None, offset=0):
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
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

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


def count_public_cases(status=None, crime_type=None, location=None, search=None):
    """Counts public cases using the same filters as get_public_cases."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = "SELECT COUNT(*) FROM cases WHERE 1=1"
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

        cur.execute(sql, params)
        return cur.fetchone()[0]
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


def get_case_access_requests(officer_id: int = None, bypass_visibility: bool = False, limit=None, offset=0):
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
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])
        
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


def count_case_access_requests(officer_id: int = None, bypass_visibility: bool = False):
    """Counts access requests using the same visibility rules as get_case_access_requests."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = "SELECT COUNT(*) FROM case_access_requests ar"
        params = []
        if not bypass_visibility and officer_id is not None:
            sql += " WHERE ar.case_id IN (SELECT case_id FROM case_officer WHERE officer_id = %s)"
            params.append(officer_id)
        cur.execute(sql, params)
        return cur.fetchone()[0]
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


def get_case_updates(case_id, limit=None, offset=0):
    """Retrieves all timeline updates for a case, ordered chronologically."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = (
            """SELECT cu.*, o.name AS officer_name, o.rank AS officer_rank
               FROM case_updates cu
               JOIN officers o ON cu.officer_id = o.officer_id
               WHERE cu.case_id = %s
               ORDER BY cu.created_at ASC"""
        )
        params = [case_id]
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

        cur.execute(sql, params)
        rows = _rows_to_list(cur, cur.fetchall())
        for r in rows:
            if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        cur.close()
        conn.close()


def count_case_updates(case_id):
    """Counts timeline updates for a case."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM case_updates WHERE case_id = %s", (case_id,))
        return cur.fetchone()[0]
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


def get_case_evidence(case_id, limit=None, offset=0):
    """Retrieves all evidence items for a case, ordered newest first."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        sql = (
            """SELECT ce.*, o.name AS officer_name, o.rank AS officer_rank
               FROM case_evidence ce
               JOIN officers o ON ce.officer_id = o.officer_id
               WHERE ce.case_id = %s
               ORDER BY ce.created_at DESC"""
        )
        params = [case_id]
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([int(limit), int(offset or 0)])

        cur.execute(sql, params)
        rows = _rows_to_list(cur, cur.fetchall())
        for r in rows:
            if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows
    finally:
        cur.close()
        conn.close()


def count_case_evidence(case_id):
    """Counts evidence items for a case."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM case_evidence WHERE case_id = %s", (case_id,))
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()


def get_evidence_by_id(evidence_id):
    """Retrieves evidence metadata by ID."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            """SELECT evidence_id, case_id, officer_id, original_name, file_path,
                      file_size, description, created_at
               FROM case_evidence WHERE evidence_id = %s""",
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
            """SELECT officer_id, `name`, email FROM officers
               WHERE `role` = 'admin' OR badge = 'ADM-0001' LIMIT 1"""
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
    Returns a list of officer dicts assigned to the given case (single JOIN query).
    The password_hash is stripped so the result is safe to send to the frontend.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Explicit columns: identity + the fields consumed by the staff UI,
        # the PDF dossier teammates table (name/rank/badge/station) and the
        # assignment-notification email (email). No password_hash, no SELECT *.
        cur.execute(
            """SELECT o.officer_id, o.`name`, o.`rank`, o.badge, o.station, o.email, o.`role`
               FROM officers o
               JOIN case_officer co ON o.officer_id = co.officer_id
               WHERE co.case_id = %s
               ORDER BY o.officer_id""",
            (case_id,)
        )
        officers = _rows_to_list(cur, cur.fetchall())
        for o in officers:
            o.pop("password_hash", None)
        return officers
    finally:
        cur.close()
        conn.close()
