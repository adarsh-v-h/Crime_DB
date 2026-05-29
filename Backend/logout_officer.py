#!/usr/bin/env python3
"""
CLI tool to force log out an officer from the backend database.
Usage: python3 logout_officer.py <badge_id>
Example: python3 logout_officer.py BPD-7821
"""

import sys
import os

# Adjust path to import backend modules if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from db_connection import init_pool, get_db
    import queries
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 logout_officer.py <badge_id>")
        sys.exit(1)

    badge_id = sys.argv[1].strip()
    
    # Initialize the db connection pool
    try:
        init_pool()
    except Exception as e:
        print(f"Failed to initialize database pool: {e}")
        sys.exit(1)

    # Look up officer by badge
    try:
        officer = queries.get_officer_by_badge(badge_id)
        if not officer:
            print(f"Error: Officer with badge '{badge_id}' not found.")
            sys.exit(1)

        officer_id = officer["officer_id"]
        officer_name = officer["name"]
        
        # Revoke all active sessions for this officer
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
            revoked_count = cur.rowcount
            print(f"Successfully logged out officer: {officer_name} ({badge_id})")
            print(f"Revoked {revoked_count} active session(s).")
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
