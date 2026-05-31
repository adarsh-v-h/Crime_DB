# ─────────────────────────────────────────────────────────────────────────────
# Themis's Domain Automated Case Assignment Algorithm
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

try:
    from .db_connection import get_db
except ImportError:
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


def create_recommendation(complaint_id: int, officer_ids: list) -> int:
    """
    Creates a recommendation record in assignment_recommendations.
    Stores algorithm-generated officer recommendations for admin review.
    
    Returns: recommendation_id of the newly created recommendation, or None on error
    """
    import json
    conn = get_db()
    cur = conn.cursor()
    try:
        officers_json = json.dumps(officer_ids)
        cur.execute(
            """INSERT INTO assignment_recommendations
               (complaint_id, recommended_officer_ids, status)
               VALUES (%s, %s, 'pending')""",
            (complaint_id, officers_json)
        )
        recommendation_id = cur.lastrowid
        
        # Transition the linked case's status to 'Recommended' if it exists.
        cur.execute(
            "SELECT promoted_case_id FROM public_complaints WHERE complaint_id = %s",
            (complaint_id,)
        )
        row = cur.fetchone()
        if row and row[0]:
            cur.execute(
                "UPDATE cases SET `status` = 'Recommended', last_updated = NOW() WHERE case_id = %s",
                (row[0],)
            )

        conn.commit()
        return recommendation_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating recommendation for complaint {complaint_id}: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()


def approve_recommendation(recommendation_id: int, admin_officer_id: int, 
                          final_officer_ids: list = None) -> int:
    """
    Approves a recommendation and creates the actual case + assignments.
    
    Parameters:
    - recommendation_id: ID of the recommendation to approve
    - admin_officer_id: Officer ID of the approving admin
    - final_officer_ids: Optional list of officers (allows admin to modify)
    
    Returns: case_id of the newly created case, or None on error
    """
    import json
    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch the recommendation and complaint (explicit columns only)
        cur.execute(
            """SELECT ar.recommendation_id, ar.complaint_id, ar.recommended_officer_ids,
                      pc.crime_type, pc.location, pc.incident_desc,
                      pc.complaint_mode, pc.complainant_name, pc.contact, pc.aadhaar, pc.promoted_case_id
               FROM assignment_recommendations ar
               JOIN public_complaints pc ON ar.complaint_id = pc.complaint_id
               WHERE ar.recommendation_id = %s""",
            (recommendation_id,)
        )
        row = cur.fetchone()
        if not row:
            logger.error(f"Recommendation {recommendation_id} not found")
            return None
        
        rec = _row_to_dict(cur, row)
        complaint_id = rec["complaint_id"]
        
        # Use final_officer_ids if provided (admin modification), else use recommended
        if final_officer_ids is None:
            officer_ids = json.loads(rec["recommended_officer_ids"])
        else:
            officer_ids = final_officer_ids
        
        # If a linked case already exists, update its status to 'Assigned'
        linked_case_id = rec.get("promoted_case_id")
        if linked_case_id:
            cur.execute(
                "UPDATE cases SET `status` = 'Assigned', last_updated = NOW() WHERE case_id = %s",
                (linked_case_id,)
            )
            new_case_id = linked_case_id
        else:
            # Create the case in the cases table with status 'Assigned'
            title = f"{rec['crime_type']} - {rec['location']}"
            cur.execute(
                """INSERT INTO cases
                   (title, description, crime_type, `status`, `location`, complaint_mode,
                    complainant_name, complainant_contact, complainant_aadhaar, `source`, last_updated)
                   VALUES (%s, %s, %s, 'Assigned', %s, %s, %s, %s, %s, 'public', NOW())""",
                (title, rec["incident_desc"], rec["crime_type"], rec["location"],
                 rec["complaint_mode"], rec["complainant_name"],
                 rec["contact"], rec["aadhaar"])
            )
            new_case_id = cur.lastrowid
        
        # Assign officers to the case
        for officer_id in officer_ids:
            cur.execute(
                """INSERT IGNORE INTO case_officer (case_id, officer_id)
                   VALUES (%s, %s)""",
                (new_case_id, officer_id)
            )
        
        # Mark complaint as Promoted with case reference
        reviewed_by = officer_ids[0] if officer_ids else None
        cur.execute(
            """UPDATE public_complaints
               SET `status` = 'Promoted', promoted_case_id = %s,
                   reviewed_by = %s, reviewed_at = NOW()
               WHERE complaint_id = %s""",
            (new_case_id, reviewed_by, complaint_id)
        )
        
        # Update recommendation as approved
        final_officers_json = json.dumps(final_officer_ids) if final_officer_ids else None
        cur.execute(
            """UPDATE assignment_recommendations
               SET status = 'approved', admin_approved_officer_ids = %s,
                   approved_by = %s, approved_at = NOW()
               WHERE recommendation_id = %s""",
            (final_officers_json, admin_officer_id, recommendation_id)
        )
        
        conn.commit()

        # Notify each newly-assigned officer by email (fires in background threads,
        # never affects the DB result even if emails fail)
        try:
            from email_utils import send_officer_assignment_notification_async
        except ImportError:
            from .email_utils import send_officer_assignment_notification_async

        for oid in officer_ids:
            try:
                send_officer_assignment_notification_async(new_case_id, oid, "added")
            except Exception as email_err:
                logger.error(f"[ASSIGNMENT EMAIL] Failed to queue email for officer {oid} on case {new_case_id}: {email_err}")

        return new_case_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error approving recommendation {recommendation_id}: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()


def create_case_from_complaint(complaint_id: int, officer_ids: list) -> int:
    """
    DEPRECATED: Use create_recommendation() + approve_recommendation() instead.
    
    Kept for backward compatibility. Creates a recommendation and auto-approves it
    to maintain existing behavior (used by auto-approval scheduler).
    
    Returns: case_id of the newly created case
    """
    rec_id = create_recommendation(complaint_id, officer_ids)
    if rec_id is None:
        return None
    
    # Auto-approve with system (None admin_officer_id indicates auto-approval)
    case_id = approve_recommendation(rec_id, admin_officer_id=None, 
                                      final_officer_ids=officer_ids)
    return case_id


# Scheduler behavior: when True the scheduler will auto-approve recommendations
# (backward-compatible). Set to False to require explicit admin approval for
# all recommendations (recommended for manual admin-review workflow).
AUTO_APPROVE_SCHEDULER = True


def process_pending_complaints() -> dict:
    """
    Main entry point for the automated assignment algorithm.
    
    Workflow (NEW):
    1. Fetch all Pending complaints from public_complaints
    2. For each complaint:
       a. Determine severity and select officers
       b. Create a recommendation record for admin review
       c. Auto-approve the recommendation (backward compat: scheduler behavior unchanged)
    
    Returns: dict with results {processed: int, errors: int, details: list}
    
    NOTE: Auto-approval happens here to preserve existing scheduler behavior.
    For manual admin review workflow, call create_recommendation() only and skip auto-approval.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch all pending complaints (only the columns the loop below reads)
        cur.execute(
            "SELECT complaint_id, crime_type FROM public_complaints "
            "WHERE `status` = 'Pending' ORDER BY submitted_at ASC"
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
                # Select officers based on crime severity (ALGORITHM LOGIC UNCHANGED)
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
                
                # Create recommendation
                rec_id = create_recommendation(complaint_id, officer_ids)
                
                if not rec_id:
                    results["errors"] += 1
                    results["details"].append({
                        "complaint_id": complaint_id,
                        "status": "error",
                        "reason": "Failed to create recommendation"
                    })
                    logger.error(f"Failed to create recommendation for complaint {complaint_id}")
                    continue
                
                # Optionally auto-approve depending on config
                if AUTO_APPROVE_SCHEDULER:
                    case_id = approve_recommendation(rec_id, admin_officer_id=None, 
                                                      final_officer_ids=officer_ids)
                    if case_id:
                        results["processed"] += 1
                        results["details"].append({
                            "complaint_id": complaint_id,
                            "recommendation_id": rec_id,
                            "case_id": case_id,
                            "status": "auto_assigned",
                            "assigned_to": officer_ids
                        })
                        logger.info(
                            f"Complaint {complaint_id} → Recommendation {rec_id} → Case {case_id} auto-assigned to officers {officer_ids}"
                        )
                    else:
                        results["errors"] += 1
                        results["details"].append({
                            "complaint_id": complaint_id,
                            "recommendation_id": rec_id,
                            "status": "error",
                            "reason": "Failed to auto-approve recommendation"
                        })
                        logger.error(f"Failed to auto-approve recommendation {rec_id} for complaint {complaint_id}")
                else:
                    # Left for admin review; count as processed recommendation
                    results["processed"] += 1
                    results["details"].append({
                        "complaint_id": complaint_id,
                        "recommendation_id": rec_id,
                        "status": "recommended",
                        "recommended_officers": officer_ids
                    })
                    logger.info(f"Complaint {complaint_id} → Recommendation {rec_id} created for admin review: {officer_ids}")
            
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
