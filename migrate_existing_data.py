"""
One-time data migration helpers for the Employee Management System.

Default mode is dry-run:
    python migrate_existing_data.py

Apply changes:
    python migrate_existing_data.py --apply
"""

import argparse
import hashlib
import re
from datetime import datetime

from db_config import db


employees_col = db["employees"]
attendance_col = db["attendance"]

LEGACY_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
CURRENT_PASSWORD_PREFIX = "pbkdf2_sha256$"


def is_legacy_sha256(value):
    return bool(value and LEGACY_SHA256_RE.match(str(value)))


def is_current_password_hash(value):
    return str(value or "").startswith(CURRENT_PASSWORD_PREFIX)


def migrate_employee_salary_fields(apply=False):
    """
    Moves old employee.salary into employee.basic_salary.
    Existing basic_salary wins if both fields are present.
    """
    scanned = 0
    changed = 0
    for emp in employees_col.find({}, {"emp_id": 1, "salary": 1, "basic_salary": 1}):
        scanned += 1
        updates = {}
        unsets = {}

        has_salary = "salary" in emp
        has_basic = "basic_salary" in emp

        if has_salary and not has_basic:
            try:
                updates["basic_salary"] = float(emp.get("salary") or 0)
            except (TypeError, ValueError):
                updates["basic_salary"] = 0.0

        if has_salary:
            unsets["salary"] = ""

        if updates or unsets:
            changed += 1
            if apply:
                update_doc = {}
                if updates:
                    update_doc["$set"] = updates
                if unsets:
                    update_doc["$unset"] = unsets
                employees_col.update_one({"_id": emp["_id"]}, update_doc)

    return scanned, changed


def normalize_employee_roles(apply=False):
    """
    Adds role='employee' to employee documents where role is missing.
    This preserves existing role values.
    """
    query = {"role": {"$exists": False}}
    count = employees_col.count_documents(query)
    if apply and count:
        employees_col.update_many(query, {"$set": {"role": "employee"}})
    return count


def flag_legacy_password_hashes(apply=False):
    """
    Existing SHA-256 hashes cannot be converted without the plaintext password.
    They are flagged so the app/admin can identify accounts that will be
    upgraded on next successful login or password reset.
    """
    scanned = 0
    legacy = 0
    current = 0
    invalid = 0

    for emp in employees_col.find({}, {"password": 1, "password_needs_upgrade": 1}):
        scanned += 1
        stored = emp.get("password")

        if is_current_password_hash(stored):
            current += 1
            if emp.get("password_needs_upgrade") and apply:
                employees_col.update_one({"_id": emp["_id"]}, {"$unset": {"password_needs_upgrade": ""}})
        elif is_legacy_sha256(stored):
            legacy += 1
            if apply:
                employees_col.update_one(
                    {"_id": emp["_id"]},
                    {"$set": {"password_needs_upgrade": True}},
                )
        else:
            invalid += 1
            if apply:
                employees_col.update_one(
                    {"_id": emp["_id"]},
                    {"$set": {"password_needs_upgrade": True, "password_hash_invalid": True}},
                )

    return scanned, current, legacy, invalid


def normalize_attendance_deleted_flag(apply=False):
    """
    Adds deleted=False to attendance records that do not have the field.
    The app already treats missing as active; this just makes data explicit.
    """
    query = {"deleted": {"$exists": False}}
    count = attendance_col.count_documents(query)
    if apply and count:
        attendance_col.update_many(query, {"$set": {"deleted": False}})
    return count


def main():
    parser = argparse.ArgumentParser(description="Migrate existing EMS MongoDB data.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this, only prints a dry-run report.")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print("=" * 60)
    print(f"Employee Management System data migration - {mode}")
    print("=" * 60)

    scanned, salary_changed = migrate_employee_salary_fields(apply=args.apply)
    missing_roles = normalize_employee_roles(apply=args.apply)
    pw_scanned, pw_current, pw_legacy, pw_invalid = flag_legacy_password_hashes(apply=args.apply)
    attendance_missing_deleted = normalize_attendance_deleted_flag(apply=args.apply)

    print(f"Employees scanned: {scanned}")
    print(f"Employees needing salary -> basic_salary cleanup: {salary_changed}")
    print(f"Employees missing role='employee': {missing_roles}")
    print(f"Password hashes scanned: {pw_scanned}")
    print(f"  Current PBKDF2 hashes: {pw_current}")
    print(f"  Legacy SHA-256 hashes flagged: {pw_legacy}")
    print(f"  Invalid/missing password hashes flagged: {pw_invalid}")
    print(f"Attendance records missing deleted flag: {attendance_missing_deleted}")

    if not args.apply:
        print("\nNo changes were written. Re-run with --apply to update the database.")
    else:
        print(f"\nMigration applied at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.")


if __name__ == "__main__":
    main()
