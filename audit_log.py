"""
╔══════════════════════════════════════════════╗
║   audit_log.py                               ║
║   Audit Log — stores & retrieves all system  ║
║   actions performed in the EMS               ║
╚══════════════════════════════════════════════╝

Usage:
    from audit_log import log_action, get_recent_logs

    log_action("LOGIN", "admin", details="Admin logged in.")
    logs = get_recent_logs(limit=50, important_only=True)
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
from pymongo import DESCENDING

from db_config import db as _db

audit_col       = _db["audit_logs"]

# IST = UTC + 5:30
_IST = timezone(timedelta(hours=5, minutes=30))


def _utcnow():
    """Returns current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _fmt_timestamp(ts):
    """
    Converts a stored UTC datetime to IST string for display.
    Handles both timezone-aware and naive (legacy) datetimes.
    """
    if ts is None:
        return "—"
    if ts.tzinfo is None:
        # Legacy naive UTC timestamps — treat as UTC
        ts = ts.replace(tzinfo=timezone.utc)
    ist_ts = ts.astimezone(_IST)
    return ist_ts.strftime("%d %b %Y  %H:%M:%S IST")


# ══════════════════════════════════════════════════════════════════════════════
#  ACTION REGISTRY
#  All possible actions that can be logged.
#  Add new ones here as the project grows.
# ══════════════════════════════════════════════════════════════════════════════
ALL_ACTIONS = [
    "LOGIN",
    "LOGOUT",
    "ADD_EMPLOYEE",
    "UPDATE_EMPLOYEE",
    "DELETE_EMPLOYEE",
    "RESTORE_EMPLOYEE",
    "MARK_ATTENDANCE",
    "UPDATE_ATTENDANCE",
    "DELETE_ATTENDANCE",
    "LEAVE_REQUEST",
    "LEAVE_APPROVED",
    "LEAVE_REJECTED",
    "LEAVE_REVERT_REQUESTED",
    "LEAVE_REVERTED",
    "LEAVE_REVERT_REJECTED",
    "SET_LEAVES",
    "ASSIGN_SHIFT",
    "SUNDAY_WORK_APPROVED",
    "EXPORT_CSV",
    "PASSWORD_CHANGE",
    "PASSWORD_RESET",
    "PROFILE_UPDATE",
]

# Only these actions appear when "Important Only" toggle is ON in the dashboard
IMPORTANT_ACTIONS = {
    "LOGIN",
    "LOGOUT",
    "DELETE_EMPLOYEE",
    "MARK_ATTENDANCE",
    "ASSIGN_SHIFT",
    "DELETE_ATTENDANCE",
    "LEAVE_APPROVED",
    "LEAVE_REJECTED",
    "LEAVE_REVERT_REQUESTED",
    "LEAVE_REVERTED",
    "LEAVE_REVERT_REJECTED",
    "PASSWORD_RESET",
}


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE — log_action()
#  Call this whenever a critical/trackable event happens in the system.
# ══════════════════════════════════════════════════════════════════════════════
def log_action(
    action:       str,
    performed_by: str,
    target:       str = None,
    details:      str = None
) -> bool:
    """
    Insert one audit log entry into MongoDB.

    Parameters
    ----------
    action       : Action type string — use constants from ALL_ACTIONS above.
                   e.g. "LOGIN", "DELETE_EMPLOYEE", "LEAVE_APPROVED"
    performed_by : Username of the person who triggered the action.
                   e.g. "admin", "emp_101"
    target       : The employee ID, name, or object affected. Optional.
                   e.g. "E012", "Ravi Sharma", "Request#abc123"
    details      : Human-readable description of exactly what happened.
                   e.g. "Employee E012 deactivated by admin."

    Returns
    -------
    True if saved successfully, False if an error occurred.

    Example
    -------
    log_action(
        action       = "DELETE_EMPLOYEE",
        performed_by = "admin",
        target       = "E012",
        details      = "Employee E012 (Priya Mehta) deactivated by admin."
    )
    """
    try:
        entry = {
            "action":       action,
            "performed_by": performed_by,
            "target":       target  if target  else "—",
            "details":      details if details else "",
            "timestamp":    _utcnow(),
        }
        audit_col.insert_one(entry)
        print(f"[AUDIT] {action} | by: {performed_by} | target: {target or '—'}")
        return True
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to log action '{action}': {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  READ — get_recent_logs()
#  Used by the dashboard widget to fetch and display logs.
# ══════════════════════════════════════════════════════════════════════════════
def get_recent_logs(
    limit:          int  = 100,
    important_only: bool = False
) -> list:
    """
    Fetch audit logs from MongoDB, newest first.

    Parameters
    ----------
    limit          : Max number of records to return. Default 100.
    important_only : If True, returns only IMPORTANT_ACTIONS (dashboard default).
                     If False, returns ALL logged actions (full history).

    Returns
    -------
    List of dicts, each with keys:
        action, performed_by, target, details, timestamp (formatted string)

    Example
    -------
    # Dashboard widget — important only (default view)
    logs = get_recent_logs(limit=100, important_only=True)

    # Full history view
    logs = get_recent_logs(limit=200, important_only=False)
    """
    try:
        query = {"action": {"$in": list(IMPORTANT_ACTIONS)}} if important_only else {}
        cursor = audit_col.find(query).sort("timestamp", DESCENDING).limit(limit)

        result = []
        for log in cursor:
            result.append({
                "action":       log.get("action",       ""),
                "performed_by": log.get("performed_by", ""),
                "target":       log.get("target",       "—"),
                "details":      log.get("details",      ""),
                "timestamp":    _fmt_timestamp(log.get("timestamp"))
            })
        return result

    except Exception as e:
        print(f"[AUDIT ERROR] Failed to fetch logs: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY — clear_all_logs()
#  Use only for testing/dev. Never call in production GUI.
# ══════════════════════════════════════════════════════════════════════════════
def clear_all_logs(confirm: bool = False) -> bool:
    """
    Delete ALL audit logs from the collection.
    Use only during development/testing.

    You MUST pass confirm=True and set ALLOW_AUDIT_LOG_CLEAR=YES in the
    environment. This prevents accidental production/demo wipes.
    """
    if not confirm:
        print("[AUDIT] clear_all_logs() called without confirm=True. Aborted.")
        return False
    if os.getenv("ALLOW_AUDIT_LOG_CLEAR") != "YES":
        print("[AUDIT] clear_all_logs() blocked. Set ALLOW_AUDIT_LOG_CLEAR=YES only in development.")
        return False
    try:
        result = audit_col.delete_many({})
        print(f"[AUDIT] Cleared {result.deleted_count} log(s).")
        return True
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to clear logs: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  QUICK TEST — run directly to verify MongoDB connection + logging works
#  Usage: python audit_log.py
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 52)
    print("   audit_log.py — Quick Test")
    print("=" * 52)

    # 1. Write some test entries
    print("\n📝 Writing test audit entries...")
    log_action("LOGIN",           "admin",       details="Admin logged in successfully.")
    log_action("ADD_EMPLOYEE",    "admin",       target="E099", details="New employee E099 registered.")
    log_action("LEAVE_APPROVED",  "admin",       target="Ravi Sharma", details="Leave approved: 03 Jun – 05 Jun.")
    log_action("DELETE_EMPLOYEE", "admin",       target="E012", details="Employee E012 deactivated.")
    log_action("MARK_ATTENDANCE", "emp_101",     target="101",  details="Check-in at 09:05.")
    log_action("LOGOUT",          "admin",       details="Admin logged out.")

    # 2. Fetch important only
    print("\n🔍 Fetching IMPORTANT logs only...")
    imp_logs = get_recent_logs(limit=10, important_only=True)
    print(f"   Found {len(imp_logs)} important log(s):")
    for l in imp_logs:
        print(f"   [{l['timestamp']}]  {l['action']:<22}  by: {l['performed_by']:<12}  → {l['target']}")

    # 3. Fetch all logs
    print("\n🔍 Fetching ALL logs...")
    all_logs = get_recent_logs(limit=10, important_only=False)
    print(f"   Found {len(all_logs)} total log(s):")
    for l in all_logs:
        print(f"   [{l['timestamp']}]  {l['action']:<22}  by: {l['performed_by']:<12}  → {l['target']}")

    print("\n✅ audit_log.py is working correctly.")
    print("=" * 52)
