"""
MongoDB indexes for the Employee Management System.

These indexes keep common Atlas queries fast as data grows.
"""

from pymongo import ASCENDING, DESCENDING

from db_config import db, employees_col


def ensure_indexes():
    indexes = [
        (employees_col, [("emp_id", ASCENDING)], {"unique": True}),
        (employees_col, [("role", ASCENDING), ("deleted", ASCENDING), ("emp_id", ASCENDING)], {}),

        (db["login_attempts"], [("login_type", ASCENDING), ("identifier", ASCENDING)], {"unique": True}),

        (db["audit_logs"], [("timestamp", DESCENDING)], {}),
        (db["audit_logs"], [("action", ASCENDING), ("timestamp", DESCENDING)], {}),

        (db["attendance"], [("emp_id", ASCENDING), ("date", ASCENDING)], {"unique": True}),
        (db["attendance"], [("date", ASCENDING), ("deleted", ASCENDING)], {}),
        (db["attendance"], [("emp_id", ASCENDING), ("deleted", ASCENDING), ("date", DESCENDING)], {}),

        (db["leave_requests"], [("emp_id", ASCENDING), ("status", ASCENDING), ("from_date", ASCENDING), ("to_date", ASCENDING)], {}),
        (db["leave_requests"], [("status", ASCENDING), ("submitted_on", DESCENDING)], {}),
        (db["leave_requests"], [("working_dates", ASCENDING), ("status", ASCENDING)], {}),

        (db["leaves"], [("emp_id", ASCENDING)], {"unique": True}),
        (db["notifications"], [("emp_id", ASCENDING), ("read", ASCENDING)], {}),
        (db["notifications"], [("emp_id", ASCENDING), ("created_on", DESCENDING), ("created_at", DESCENDING)], {}),

        (db["salary_history"], [("emp_id", ASCENDING), ("effective_from", DESCENDING), ("created_at", DESCENDING)], {}),
        (db["salary"], [("emp_id", ASCENDING), ("month", ASCENDING)], {"unique": True}),

        (db["shift_assignments"], [("emp_id", ASCENDING)], {"unique": True}),
        (db["sunday_work_approvals"], [("emp_id", ASCENDING), ("date", ASCENDING)], {"unique": True}),

        (db["holidays"], [("date", ASCENDING), ("active", ASCENDING), ("deleted", ASCENDING)], {}),
        (db["holidays"], [("holiday_date", ASCENDING), ("active", ASCENDING), ("deleted", ASCENDING)], {}),
        (db["holidays"], [("day", ASCENDING), ("active", ASCENDING), ("deleted", ASCENDING)], {}),
    ]

    created = []
    for collection, keys, options in indexes:
        name = collection.create_index(keys, **options)
        created.append(name)

    return created
