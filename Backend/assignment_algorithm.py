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
