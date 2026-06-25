"""
╔══════════════════════════════════════════════╗
║   auth_model.py                              ║
║   All authentication logic                   ║
╚══════════════════════════════════════════════╝

BUGS FIXED:
  1. get_all_employees() was missing — existed as get_all_users(), renamed +
     aliased so both names work.
  2. register_employee() inserted the document TWICE into the same collection
     (two insert_one calls with identical data).
  3. change_password() accepted emp_id as the username string from the GUI
     (EmployeeDashboard passes username, not an int ID) — added a str fallback
     so it queries by name when the value isn't a valid integer.
  4. get_all_employees() now returns dicts with keys "id", "name", "role" that
     match what gui.py's _draw_table() expects (was returning raw Mongo docs
     with "emp_id" key, causing KeyError in the table).
"""

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime, timedelta

import hashlib
import hmac
import secrets
from bson import ObjectId

from app_time import now_stamp as _app_now_stamp
from app_time import now_time as _app_now_time
from app_time import today_date as _app_today_date
from app_time import today_iso as _app_today_iso
from app_time import trusted_now as _app_trusted_now
from db_config import db as _db, employees_col
departments_col = _db["departments"]
salary_history_col = _db["salary_history"]
login_attempts_col = _db["login_attempts"]
try:
    employees_col.create_index("emp_id", unique=True)
    login_attempts_col.create_index([("login_type", 1), ("identifier", 1)], unique=True)
except Exception:
    pass

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

_missing_env = [k for k, v in {
    "ADMIN_USERNAME":      ADMIN_USERNAME,
    "ADMIN_PASSWORD_HASH": ADMIN_PASSWORD_HASH,
}.items() if not v]
if _missing_env:
    raise EnvironmentError(
        f"[auth_model] Missing required environment variable(s): {', '.join(_missing_env)}. "
        "Admin login will never succeed. Load your .env file before starting the application."
    )

# ----------------------------------------------------------------------
#  SHARED DATABASE COLLECTIONS
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
#  HELPER - password hashing
# ----------------------------------------------------------------------
PBKDF2_ITERATIONS = 260_000
PASSWORD_ALGORITHM = "pbkdf2_sha256"


def _hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PASSWORD_ALGORITHM}${PBKDF2_ITERATIONS}${salt}${digest}"


def _verify_password(stored_hash, password):
    if not stored_hash or password is None:
        return False

    stored_hash = str(stored_hash)
    if stored_hash.startswith(f"{PASSWORD_ALGORITHM}$"):
        try:
            _, iterations, salt, expected = stored_hash.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("ascii"),
                int(iterations),
            ).hex()
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(digest, expected)

    # Backward compatibility for existing unsalted SHA-256 employee hashes.
    if len(stored_hash) == 64 and all(ch in "0123456789abcdef" for ch in stored_hash.lower()):
        legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_digest, stored_hash)

    return False


def _password_needs_rehash(stored_hash):
    return not str(stored_hash or "").startswith(f"{PASSWORD_ALGORITHM}$")


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15


def _login_identifier(login_type, identifier):
    return str(identifier or "").strip().lower()


def _login_lock_message(locked_until):
    remaining = max(1, int((locked_until - _app_trusted_now()).total_seconds() // 60) + 1)
    return f"Too many failed login attempts. Try again in {remaining} minute(s)."


def _check_login_lock(login_type, identifier):
    identifier = _login_identifier(login_type, identifier)
    if not identifier:
        return False, None, False
    record = login_attempts_col.find_one({"login_type": login_type, "identifier": identifier})
    if not record:
        return False, None, False
    locked_until = record.get("locked_until")
    if isinstance(locked_until, datetime) and locked_until > _app_trusted_now():
        return True, _login_lock_message(locked_until), True
    return False, None, True


def _record_login_failure(login_type, identifier):
    identifier = _login_identifier(login_type, identifier)
    if not identifier:
        return
    now = _app_trusted_now()
    record = login_attempts_col.find_one({"login_type": login_type, "identifier": identifier}) or {}
    failed_count = int(record.get("failed_count", 0) or 0) + 1
    update = {
        "failed_count": failed_count,
        "last_failed_at": now,
    }
    if failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
        update["locked_until"] = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
    login_attempts_col.update_one(
        {"login_type": login_type, "identifier": identifier},
        {"$set": update},
        upsert=True,
    )


def _clear_login_failures(login_type, identifier):
    identifier = _login_identifier(login_type, identifier)
    if identifier:
        login_attempts_col.delete_one({"login_type": login_type, "identifier": identifier})


def _department_name(doc):
    if isinstance(doc, str):
        return doc.strip()
    if not isinstance(doc, dict):
        return ""
    for key in ("name", "department", "dept", "title"):
        value = doc.get(key)
        if value:
            return str(value).strip()
    return ""


def get_departments(include_fallback=True):
    try:
        docs = departments_col.find({}, {"_id": 0}).sort("name", 1)
        names = [_department_name(doc) for doc in docs]
    except Exception:
        names = []

    names = sorted({name for name in names if name})
    if names or not include_fallback:
        return names

    try:
        return sorted({str(d).strip() for d in employees_col.distinct("department") if str(d).strip()})
    except Exception:
        return []


def _normalize_joining_date(value):
    """
    Admin input format is DD/MM/YY. Store as YYYY-MM-DD for universal comparisons.
    Also accepts YYYY-MM-DD for migrated or scripted data.
    """
    raw = str(value or "").strip()
    if not raw:
        return _app_today_iso()

    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Joining date must be in DD/MM/YY format!")


# ══════════════════════════════════════════════
#  1. ADMIN LOGIN
# ══════════════════════════════════════════════
def admin_login(username, password):
    """
    Returns (True, "admin", "Admin") on success.
    Returns (False, None, error_message) on failure.
    """
    if not username or not password:
        return False, None, "Username and Password cannot be empty!"

    locked, lock_msg, had_failed_attempts = _check_login_lock("admin", username)
    if locked:
        return False, None, lock_msg

    if username != ADMIN_USERNAME:
        _record_login_failure("admin", username)
        return False, None, "Invalid admin credentials!"
    if not ADMIN_PASSWORD_HASH:
        # .env was loaded but the variable is empty — surface this immediately
        # instead of silently falling through to "Invalid credentials".
        return False, None, (
            "Admin account is not configured: ADMIN_PASSWORD_HASH is empty. "
            "Check your .env file."
        )
    if _verify_password(ADMIN_PASSWORD_HASH, password):
        if had_failed_attempts:
            _clear_login_failures("admin", username)
        return True, "admin", "Admin"
    _record_login_failure("admin", username)
    return False, None, "Invalid admin credentials!"


# ══════════════════════════════════════════════
#  2. EMPLOYEE LOGIN
# ══════════════════════════════════════════════
def employee_login(emp_id, password):
    """
    Returns (True, emp_id, name) on success.
    Returns (False, None, error_message) on failure.
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, None, "Employee ID must be a number!"

    if not password:
        return False, None, "Password cannot be empty!"

    locked, lock_msg, had_failed_attempts = _check_login_lock("employee", emp_id)
    if locked:
        return False, None, lock_msg

    user = employees_col.find_one(
        {"emp_id": emp_id},
        {"emp_id": 1, "name": 1, "password": 1, "deleted": 1},
    )
    if not user:
        _record_login_failure("employee", emp_id)
        return False, None, f"No account found for Employee ID {emp_id}!"

    if user.get("deleted"):
        _record_login_failure("employee", emp_id)
        return False, None, "This account has been deactivated. Contact admin."

    if "password" not in user:
        _record_login_failure("employee", emp_id)
        return False, None, f"Account for ID {emp_id} is incomplete. Ask admin to reset your password."

    stored_password = user.get("password")
    if not _verify_password(stored_password, password):
        _record_login_failure("employee", emp_id)
        return False, None, "Incorrect password!"

    if _password_needs_rehash(stored_password):
        employees_col.update_one(
            {"_id": user["_id"]},
            {"$set": {"password": _hash_password(password)}}
        )

    if had_failed_attempts:
        _clear_login_failures("employee", emp_id)
    return True, emp_id, user["name"]


# ══════════════════════════════════════════════
#  3. REGISTER EMPLOYEE
# ══════════════════════════════════════════════
def register_employee(
    emp_id, name, password, basic_salary=0, department=None,
    email=None, phone=None, address=None, joining_date=None,
):
    """
    Registers a new employee into the employees collection.
    Returns (True, message) or (False, error)

    Optional contact fields:
        email   – employee email address (string)
        phone   – contact number (string)
        address – residential address (string)
    """
    import re

    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Employee ID must be a number!"

    if not name or not name.strip():
        return False, "Name cannot be empty!"

    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters!"
    if not department:
        return False, "Department is required!"
    valid_departments = get_departments(include_fallback=False)
    if valid_departments and department not in valid_departments:
        return False, "Please select a valid department from the list!"

    try:
        basic_salary = float(basic_salary)
        if basic_salary < 0:
            return False, "Basic salary cannot be negative!"
    except (ValueError, TypeError):
        return False, "Basic salary must be a valid number!"

    try:
        joining_date = _normalize_joining_date(joining_date)
    except ValueError as exc:
        return False, str(exc)

    normalized_email = email.strip().lower() if email and email.strip() else ""
    # Email format validation (when provided)
    if normalized_email:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
            return False, "Email address is invalid."
        if employees_col.find_one({"email": normalized_email, "deleted": {"$ne": True}}):
            return False, f"Email '{normalized_email}' is already registered to another employee!"

    # Phone: digits/spaces/dashes/plus, 7–15 chars (when provided)
    if phone and phone.strip():
        if not re.fullmatch(r"[\d\s\-\+]{7,15}", phone.strip()):
            return False, "Phone number is invalid (7–15 digits; spaces, dashes or + allowed)."

    existing_emp = employees_col.find_one({"emp_id": emp_id}, {"deleted": 1})
    if existing_emp:
        if existing_emp.get("deleted"):
            return False, f"Employee ID {emp_id} already exists as deactivated. Restore it instead of re-adding."
        return False, f"Employee ID {emp_id} already exists!"

    doc = {
        "emp_id":       emp_id,
        "name":         name.strip(),
        "department":   department,
        "role":         "employee",
        "password":     _hash_password(password),
        "basic_salary": basic_salary,
        "joining_date": joining_date,
        "created_at":   _app_today_iso(),
    }

    # Optional fields — only stored when provided
    if normalized_email:            doc["email"]   = normalized_email
    if phone   and phone.strip():   doc["phone"]   = phone.strip()
    if address and address.strip(): doc["address"] = address.strip()

    employees_col.insert_one(doc)

    return True, f"✅ Employee {name} (ID: {emp_id}) registered successfully!"


def update_employee_details(
    emp_id, name, basic_salary=0, department=None,
    email=None, phone=None, address=None, joining_date=None,
):
    """Updates editable employee profile fields without changing password."""
    import re

    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"

    if not name or not name.strip():
        return False, "Name cannot be empty!"
    if not department:
        return False, "Department is required!"
    valid_departments = get_departments(include_fallback=False)
    if valid_departments and department not in valid_departments:
        return False, "Please select a valid department from the list!"

    try:
        basic_salary = float(basic_salary)
        if basic_salary < 0:
            return False, "Basic salary cannot be negative!"
    except (ValueError, TypeError):
        return False, "Basic salary must be a valid number!"

    try:
        joining_date = _normalize_joining_date(joining_date)
    except ValueError as exc:
        return False, str(exc)

    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"No active employee found with ID {emp_id}!"

    normalized_email = email.strip().lower() if email and email.strip() else ""
    if normalized_email:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
            return False, "Email address is invalid."
        duplicate = employees_col.find_one({
            "emp_id": {"$ne": emp_id},
            "email": normalized_email,
            "deleted": {"$ne": True},
        })
        if duplicate:
            return False, f"Email '{normalized_email}' is already registered to another employee!"

    if phone and phone.strip():
        if not re.fullmatch(r"[\d\s\-\+]{7,15}", phone.strip()):
            return False, "Phone number is invalid (7-15 digits; spaces, dashes or + allowed)."

    set_fields = {
        "name": name.strip(),
        "department": department,
        "basic_salary": basic_salary,
        "joining_date": joining_date,
        "updated_at": _app_now_stamp(),
    }
    unset_fields = {"salary": ""}

    if normalized_email:
        set_fields["email"] = normalized_email
    else:
        unset_fields["email"] = ""
    if phone and phone.strip():
        set_fields["phone"] = phone.strip()
    else:
        unset_fields["phone"] = ""
    if address and address.strip():
        set_fields["address"] = address.strip()
    else:
        unset_fields["address"] = ""

    update_doc = {"$set": set_fields}
    if unset_fields:
        update_doc["$unset"] = unset_fields

    employees_col.update_one({"emp_id": emp_id, "deleted": {"$ne": True}}, update_doc)
    return True, f"Employee ID {emp_id} updated successfully!"


# ══════════════════════════════════════════════
#  4. CHANGE PASSWORD
# ══════════════════════════════════════════════
def change_password(emp_id, old_password, new_password):
    """
    Changes an employee password using emp_id only.
    Names are not accepted as identifiers because they are not unique.
    Returns (True, message) or (False, error)
    """
    if not new_password or len(new_password) < 8:
        return False, "New password must be at least 8 characters!"

    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"

    user = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not user:
        return False, f"No active account found for Employee ID {emp_id}!"

    if not _verify_password(user.get("password"), old_password):
        return False, "Old password is incorrect!"

    employees_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": _hash_password(new_password)}}
    )
    return True, "✅ Password changed successfully!"


# ══════════════════════════════════════════════
#  5. RESET PASSWORD (Admin only)
# ══════════════════════════════════════════════
def reset_password(emp_id, new_password):
    """
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Employee ID must be a number!"

    if not new_password or len(new_password) < 8:
        return False, "Password must be at least 8 characters!"

    user = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not user:
        return False, f"No active account found for Employee ID {emp_id}!"

    employees_col.update_one(
        {"emp_id": emp_id},
        {"$set": {"password": _hash_password(new_password)}}
    )
    return True, f"✅ Password reset successfully for Employee ID {emp_id}!"


# ══════════════════════════════════════════════
#  6. DELETE EMPLOYEE ACCOUNT
# ══════════════════════════════════════════════
def delete_emp_account(emp_id):
    """
    SOFT DELETE — sets deleted=True, records timestamp.
    Employee stays in MongoDB and can be restored by admin.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Employee ID must be a number!"

    from datetime import datetime as _dt
    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"No account found for Employee ID {emp_id}!"

    if emp.get("deleted"):
        return False, f"Employee ID {emp_id} is already deactivated!"

    employees_col.update_one(
        {"emp_id": emp_id},
        {"$set": {
            "deleted":    True,
            "deleted_at": _app_now_stamp(),
        }}
    )
    return True, f"✅ Employee ID {emp_id} deactivated (can be restored by admin)!"


def restore_employee(emp_id):
    """
    Restores a soft-deleted employee — removes the deleted flag.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except (TypeError, ValueError):
        return False, "Employee ID must be a number!"

    emp = employees_col.find_one({"emp_id": emp_id})
    if not emp:
        return False, f"No account found for Employee ID {emp_id}!"

    if not emp.get("deleted"):
        return False, f"Employee ID {emp_id} is not deactivated!"

    from datetime import datetime as _dt, timezone as _timezone
    restored_at = _dt.now(_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    deleted_at = emp.get("deleted_at")
    if not deleted_at:
        return False, (
            f"Employee ID {emp_id} has no deactivation timestamp. "
            "Restore cancelled to protect report history."
        )

    result = employees_col.update_one(
        {"emp_id": emp_id, "deleted": True, "deleted_at": deleted_at},
        {
            "$push": {
                "inactive_periods": {
                    "from": deleted_at,
                    "to": restored_at,
                    "reason": "deactivated",
                }
            },
            "$set": {"restored_at": restored_at},
            "$unset": {"deleted": "", "deleted_at": ""},
        },
    )
    if result.modified_count == 0:
        return False, (
            f"Employee ID {emp_id} changed while being restored. "
            "Refresh the employee list and try again."
        )
    return True, f"✅ Employee ID {emp_id} restored successfully!"


# ══════════════════════════════════════════════
#  6b. SET BASIC SALARY  (Admin)
# ══════════════════════════════════════════════
# ══════════════════════════════════════════════
def _normalize_effective_date(value=None):
    if not value:
        return _app_today_iso()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Effective date must be in DD/MM/YY format!")


def _salary_history_object_id(history_id):
    try:
        return ObjectId(str(history_id))
    except Exception:
        return None


def _sync_current_basic_salary(emp_id):
    today = _app_today_iso()
    doc = salary_history_col.find_one(
        {"emp_id": emp_id, "effective_from": {"$lte": today}},
        sort=[("effective_from", -1), ("created_at", -1)]
    )
    if doc:
        employees_col.update_one(
            {"emp_id": emp_id},
            {"$set": {"basic_salary": float(doc.get("basic_salary", 0) or 0)}, "$unset": {"salary": ""}}
        )


def set_basic_salary(emp_id, basic_salary, effective_from=None, note=""):
    """
    Admin records a salary revision for an existing employee.
    Amount supports exact values and +/- changes:
      30000 sets salary to 30000
      +5000 increases current salary by 5000
      -2000 decreases current salary by 2000
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"

    try:
        effective_from = _normalize_effective_date(effective_from)
    except ValueError as e:
        return False, str(e)

    emp = employees_col.find_one({"emp_id": emp_id})
    if not emp:
        return False, f"No employee found with ID {emp_id}!"

    old_salary = float(emp.get("basic_salary", emp.get("salary", 0)) or 0)
    raw_amount = str(basic_salary or "").strip().replace(",", "")
    if not raw_amount:
        return False, "Salary amount is required!"

    try:
        if raw_amount[0] in "+-":
            change_amount = float(raw_amount)
            new_salary = old_salary + change_amount
            revision_mode = "increase" if change_amount >= 0 else "decrease"
        else:
            change_amount = None
            new_salary = float(raw_amount)
            revision_mode = "set"
    except (ValueError, TypeError):
        return False, "Salary amount must be a number, +amount, or -amount!"

    if new_salary < 0:
        return False, "Salary change cannot make basic salary negative!"

    timestamp = _app_now_stamp()
    if not salary_history_col.find_one({"emp_id": emp_id}):
        salary_history_col.insert_one({
            "emp_id": emp_id,
            "basic_salary": old_salary,
            "effective_from": str(emp.get("joining_date") or emp.get("created_at") or "1900-01-01")[:10],
            "created_at": timestamp,
            "note": "Baseline salary before salary history tracking",
        })

    final_note = str(note or "").strip()
    if change_amount is not None:
        change_note = f"Salary {revision_mode}: {change_amount:+,.2f}. Previous: {old_salary:,.2f}. New: {new_salary:,.2f}."
        final_note = f"{change_note} {final_note}".strip()

    salary_history_col.insert_one({
        "emp_id": emp_id,
        "basic_salary": new_salary,
        "effective_from": effective_from,
        "created_at": timestamp,
        "previous_salary": old_salary,
        "change_amount": change_amount,
        "revision_mode": revision_mode,
        "note": final_note,
    })
    _sync_current_basic_salary(emp_id)

    if change_amount is not None:
        return True, f"Basic salary {revision_mode} saved: {change_amount:+,.0f}. New salary Rs. {new_salary:,.0f} from {effective_from} for Employee ID {emp_id}!"
    return True, f"Basic salary revision saved: Rs. {new_salary:,.0f} from {effective_from} for Employee ID {emp_id}!"


def get_salary_history(emp_id):
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return []

    docs = salary_history_col.find({"emp_id": emp_id}).sort([
        ("effective_from", -1),
        ("created_at", -1),
    ])
    return [
        {
            "id": str(doc.get("_id")),
            "emp_id": doc.get("emp_id"),
            "basic_salary": float(doc.get("basic_salary", 0) or 0),
            "effective_from": str(doc.get("effective_from", ""))[:10],
            "previous_salary": doc.get("previous_salary"),
            "note": doc.get("note", ""),
            "created_at": doc.get("created_at", ""),
        }
        for doc in docs
    ]


def update_salary_history_entry(history_id, basic_salary, effective_from, note=""):
    obj_id = _salary_history_object_id(history_id)
    if not obj_id:
        return False, "Invalid salary history entry!"

    try:
        basic_salary = float(basic_salary)
        if basic_salary < 0:
            return False, "Basic salary cannot be negative!"
    except (ValueError, TypeError):
        return False, "Basic salary must be a valid number!"

    try:
        effective_from = _normalize_effective_date(effective_from)
    except ValueError as e:
        return False, str(e)

    existing = salary_history_col.find_one({"_id": obj_id})
    if not existing:
        return False, "Salary history entry not found!"

    salary_history_col.update_one(
        {"_id": obj_id},
        {"$set": {
            "basic_salary": basic_salary,
            "effective_from": effective_from,
            "note": str(note or "").strip(),
            "updated_at": _app_now_stamp(),
        }}
    )
    _sync_current_basic_salary(int(existing["emp_id"]))
    return True, "Salary history entry updated!"


def delete_salary_history_entry(history_id):
    obj_id = _salary_history_object_id(history_id)
    if not obj_id:
        return False, "Invalid salary history entry!"

    existing = salary_history_col.find_one({"_id": obj_id})
    if not existing:
        return False, "Salary history entry not found!"

    total_entries = salary_history_col.count_documents({"emp_id": existing["emp_id"]})
    if total_entries <= 1:
        return False, "Cannot delete the only salary history entry!"

    salary_history_col.delete_one({"_id": obj_id})
    _sync_current_basic_salary(int(existing["emp_id"]))
    return True, "Salary history entry deleted!"


#  7. GET ALL EMPLOYEES
#  FIX 1: Was named get_all_users() — main.py calls get_all_employees().
#  FIX 4: Returns dicts with keys "id", "name", "role" to match what
#          gui.py _draw_table() expects (u["id"], u["name"], u["role"]).
#          Raw Mongo docs use "emp_id" which caused KeyError in the table.
# ══════════════════════════════════════════════
def get_all_employees(include_deleted=False):
    """
    Returns all employee accounts as a list of dicts with keys:
        id, name, role, deleted
    include_deleted=True  → active + soft-deleted (admin view)
    include_deleted=False → active only (default)
    """
    query = {"role": "employee"}
    if not include_deleted:
        query["deleted"] = {"$ne": True}

    docs = employees_col.find(
        query,
        {
            "_id": 0,
            "emp_id": 1,
            "name": 1,
            "role": 1,
            "department": 1,
            "basic_salary": 1,
            "salary": 1,
            "email": 1,
            "phone": 1,
            "address": 1,
            "deleted": 1,
            "deleted_at": 1,
            "joining_date": 1,
            "created_at": 1,
        },
    ).sort("emp_id", 1)

    return [
        {
            "id":          str(doc.get("emp_id", "?")),
            "name":        doc.get("name", "Unknown"),
            "role":        doc.get("role", "employee").capitalize(),
            "department":  doc.get("department", ""),
            "basic_salary": doc.get("basic_salary", doc.get("salary", "")),
            "email":       doc.get("email", ""),
            "phone":       doc.get("phone", ""),
            "address":     doc.get("address", ""),
            "deleted":     doc.get("deleted", False),
            "deleted_at":  doc.get("deleted_at", ""),
            "joining_date": doc.get("joining_date", doc.get("created_at", "")),
            "created_at":  doc.get("created_at", ""),
        }
        for doc in docs
    ]

# Alias so any legacy call to get_all_users() still works
get_all_users = get_all_employees


# ══════════════════════════════════════════════
#  8. ACCOUNT EXISTS
# ══════════════════════════════════════════════
def account_exists(emp_id):
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False
    return employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}) is not None

# ══════════════════════════════════════════════
#  9. GET EMP ID BY USERNAME
#  Employee dashboard stores the logged-in emp_id.
#  Names are not accepted because they are not unique.
# ----------------------------------------------------------------------
def get_emp_id_by_username(username):
    """
    Resolves emp_id from the ID stored at login.
    Returns emp_id (int) or None.
    """
    try:
        emp_id = int(username)
    except (ValueError, TypeError):
        return None

    doc = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}, {"emp_id": 1})
    return doc["emp_id"] if doc else None


# ══════════════════════════════════════════════
#  NEW COLLECTIONS — auto-created by MongoDB
#  on first insert, no manual setup needed
# ══════════════════════════════════════════════
from datetime import datetime, date, timedelta

leaves_col     = _db["leaves"]
attendance_col = _db["attendance"]
notifications_col = _db["notifications"]
holidays_col = _db["holidays"]

def _today():
    return _app_today_iso()   # e.g. "2026-05-26"

def _now():
    return _app_now_time(include_seconds=True) # e.g. "09:32:11"


def _parse_yyyy_mm_dd(value, label="Date"):
    raw = str(value or "").strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except (TypeError, ValueError):
            pass
    raise ValueError(f"{label} must use DD/MM/YY format.")


def _get_holiday_dates(start_date=None, end_date=None):
    """Fallback holiday lookup using the same active-record rules as payroll."""
    holidays = set()
    for field in ("date", "holiday_date", "day"):
        query = {
            "active": {"$ne": False},
            "deleted": {"$ne": True},
        }
        if start_date and end_date:
            query[field] = {"$gte": str(start_date), "$lte": str(end_date)}
        try:
            docs = holidays_col.find(query, {"_id": 0, field: 1})
        except Exception:
            continue
        for doc in docs:
            value = doc.get(field)
            if isinstance(value, datetime):
                holidays.add(value.date().isoformat())
            elif isinstance(value, date):
                holidays.add(value.isoformat())
            elif value:
                holidays.add(str(value)[:10])
    return holidays


def _business_dates(emp_id, start_date, end_date):
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()
    try:
        from shift_model import (
            get_holidays_for_range,
            get_sunday_work_approval_dates_for_range,
        )
        holidays = {
            str(item.get("_holiday_date"))
            for item in get_holidays_for_range(start_iso, end_iso)
            if item.get("_holiday_date")
        }
        sunday_work_dates = get_sunday_work_approval_dates_for_range(
            emp_id,
            start_iso,
            end_iso,
        )
    except Exception:
        holidays = _get_holiday_dates(start_iso, end_iso)
        sunday_work_dates = set()

    days = []
    current = start_date
    while current <= end_date:
        current_str = current.isoformat()
        sunday_work_approved = current_str in sunday_work_dates
        # The attendance/payroll system treats Sunday as the weekly holiday.
        # Saturday is therefore a normal leave-working day.
        if (current.weekday() != 6 or sunday_work_approved) and current_str not in holidays:
            days.append(current_str)
        current += timedelta(days=1)
    return days


def _range_contains_sunday(start_date, end_date):
    current = start_date
    while current <= end_date:
        if current.weekday() == 6:
            return True
        current += timedelta(days=1)
    return False


def _active_pending_leave_days(emp_id, exclude_request_id=None):
    """
    Returns the total working days reserved by Pending leave requests.
    Uses `days` (requested working days), NOT `paid_days` — paid_days is
    a stale projection from submission time and must not be trusted here.
    Reserving the full requested `days` ensures the balance check is
    conservative: the employee cannot over-commit their leave balance
    across multiple simultaneous pending requests.
    """
    total = 0.0
    query = {"emp_id": int(emp_id), "status": "Pending"}
    if exclude_request_id:
        query["_id"] = {"$ne": exclude_request_id}
    docs = leave_requests_col.find(query, {"days": 1})
    for doc in docs:
        try:
            total += float(doc.get("days", 0))
        except (TypeError, ValueError):
            pass
    return total


def _leave_balance_available(emp_id, exclude_request_id=None):
    doc = leaves_col.find_one({"emp_id": int(emp_id)})
    if not doc:
        return 0, None
    total = float(doc.get("total_leaves", 0))
    used = float(doc.get("used_leaves", 0))
    pending = _active_pending_leave_days(emp_id, exclude_request_id)
    return max(total - used - pending, 0), None


def create_employee_notification(emp_id, title, message, request_id=None, notification_type="general"):
    notifications_col.insert_one({
        "emp_id": int(emp_id),
        "title": title,
        "message": message,
        "request_id": str(request_id) if request_id else None,
        "type": notification_type,
        "created_on": _today(),
        "created_at": _now(),
        "read": False,
    })


def _notify_employee(emp_id, title, message, request_id=None):
    create_employee_notification(emp_id, title, message, request_id=request_id, notification_type="leave")


def get_unread_notification_count(emp_id):
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return 0
    return notifications_col.count_documents({"emp_id": emp_id, "read": {"$ne": True}})


def mark_notification_read(notification_id, emp_id=None):
    try:
        oid = ObjectId(str(notification_id))
    except Exception:
        return False, "Invalid notification."
    query = {"_id": oid}
    if emp_id is not None:
        try:
            query["emp_id"] = int(emp_id)
        except (ValueError, TypeError):
            return False, "Invalid employee."
    result = notifications_col.update_one(query, {"$set": {"read": True, "read_at": _now()}})
    if result.matched_count:
        return True, "Notification marked as read."
    return False, "Notification not found."


def get_employee_notifications(emp_id, limit=10):
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return []
    docs = notifications_col.find({"emp_id": emp_id}).sort([("created_on", -1), ("created_at", -1)]).limit(limit)
    return [
        {
            "id": str(doc.get("_id")),
            "title": doc.get("title", "Notification"),
            "message": doc.get("message", ""),
            "created_on": doc.get("created_on", ""),
            "created_at": doc.get("created_at", ""),
            "read": doc.get("read", False),
            "type": doc.get("type", "general"),
        }
        for doc in docs
    ]


# ══════════════════════════════════════════════
#  10. SET EMPLOYEE LEAVES  (Admin)
# ══════════════════════════════════════════════
def set_employee_leaves(emp_id, total_leaves):
    """
    Admin sets total allowed leaves for an employee.
    Creates the record if it doesn't exist, updates if it does.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id       = int(emp_id)
        total_leaves = int(total_leaves)
    except ValueError:
        return False, "Employee ID and total leaves must be numbers!"

    if total_leaves < 0:
        return False, "Total leaves cannot be negative!"

    if not employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}):
        return False, f"No employee found with ID {emp_id}!"

    leaves_col.update_one(
        {"emp_id": emp_id},
        {"$set": {"total_leaves": total_leaves}},
        upsert=True   # creates document if it doesn't exist
    )
    _log_leave_audit(
        "SET_LEAVES",
        "admin",
        emp_id,
        details=f"Set total leaves to {total_leaves} for Employee ID {emp_id}.",
    )
    return True, f"✅ Set {total_leaves} leaves for Employee ID {emp_id}!"


# ══════════════════════════════════════════════
#  11. GET EMPLOYEE LEAVES  (Employee)
# ══════════════════════════════════════════════
def get_employee_leaves(emp_id):
    """
    Returns leave info for an employee.
    Returns (True, { total, used, remaining }) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"

    doc = leaves_col.find_one({"emp_id": emp_id})
    if not doc:
        return False, f"No leave record found for Employee ID {emp_id}!"

    total     = doc.get("total_leaves", 0)
    used      = doc.get("used_leaves",  0)
    remaining = max(total - used, 0)

    return True, {
        "total":     total,
        "used":      used,
        "remaining": remaining,
    }


# ══════════════════════════════════════════════
#  12. DEDUCT LEAVE  (Legacy utility)
# ══════════════════════════════════════════════
def deduct_leave(emp_id):
    """
    Deducts 1 leave from an employee's balance.
    Manual absence must not call this function. Paid leave is consumed only
    through the approved leave-request workflow so payroll can recognize it.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Employee ID must be a number!"

    doc = leaves_col.find_one({"emp_id": emp_id})
    if not doc:
        return False, f"No leave record for Employee ID {emp_id}. Set leaves first!"

    total = doc.get("total_leaves", 0)
    used  = doc.get("used_leaves",  0)

    if used >= total:
        return False, f"Employee ID {emp_id} has no remaining leaves!"

    leaves_col.update_one(
        {"emp_id": emp_id},
        {"$inc": {"used_leaves": 1}}
    )
    return True, f"✅ Leave deducted. Remaining: {total - used - 1}"


# ══════════════════════════════════════════════
#  13. EMPLOYEE SELF CHECK-IN
# ══════════════════════════════════════════════
def employee_checkin(emp_id):
    """
    Employee self check-in — delegates to the shift-aware mark_arrival()
    in attendance.py so the correct schema, shift logic, late calculation,
    and holiday/leave blocks are all applied consistently.
    Returns (True, message) or (False, error).
    """
    try:
        from attendance import mark_arrival
    except ImportError:
        return False, "Attendance module not available. Contact admin."
    return mark_arrival(emp_id)


# ══════════════════════════════════════════════
#  14. ADMIN MARK ATTENDANCE
# ══════════════════════════════════════════════
def mark_attendance(emp_id, status):
    """
    Admin marks an employee present or absent.
    Delegates to attendance.py so the written document always matches
    the canonical schema (arrival_time, shift, late_minutes, etc.).
    Marking absent does not consume leave. Leave balance is consumed only
    when a leave request is approved.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Employee ID must be a number!"

    if status not in ("present", "absent"):
        return False, "Status must be 'present' or 'absent'!"

    try:
        from attendance import mark_arrival, mark_absent
    except ImportError:
        return False, "Attendance module not available. Contact admin."

    if status == "absent":
        return mark_absent(emp_id)

    return mark_arrival(emp_id)


# ══════════════════════════════════════════════
#  15. GET DAILY REPORT  (Admin daily report)
# ══════════════════════════════════════════════
def get_daily_report(query_date=None):
    """
    Returns the attendance-focused summary for one date.
    """
    query_date = str(query_date or _today()).strip()
    try:
        datetime.strptime(query_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        return []
    try:
        from shift_model import get_employee_shift, get_sunday_work_approval_map
    except Exception:
        get_employee_shift = None
        get_sunday_work_approval_map = None
    try:
        from attendance import (
            employee_active_on_date,
            get_approved_leave_for_date,
            get_holiday,
            is_missed_checkout,
            resolve_daily_report_status,
        )
    except Exception:
        employee_active_on_date = None
        get_approved_leave_for_date = None
        get_holiday = None
        is_missed_checkout = None
        resolve_daily_report_status = None

    all_employees = list(employees_col.find(
        {"role": "employee"},
        {"password": 0},
    ))
    if employee_active_on_date:
        employees = [
            emp for emp in all_employees
            if employee_active_on_date(emp, query_date)
        ]
    else:
        employees = [
            emp for emp in all_employees
            if not emp.get("deleted")
        ]

    is_sunday = datetime.strptime(query_date, "%Y-%m-%d").weekday() == 6
    try:
        is_public_holiday = bool(get_holiday(query_date)) if get_holiday else False
    except Exception:
        is_public_holiday = False
    sunday_approvals = {}
    if is_sunday and get_sunday_work_approval_map:
        try:
            sunday_approvals = get_sunday_work_approval_map(
                [emp.get("emp_id") for emp in employees],
                query_date,
                query_date,
            )
        except Exception:
            sunday_approvals = {}

    report = []
    for emp in employees:
        emp_id = emp.get("emp_id")
        att = attendance_col.find_one({
            "emp_id": emp_id,
            "date": query_date,
            "deleted": {"$ne": True},
        }) or {}
        try:
            leave = (
                get_approved_leave_for_date(emp_id, query_date)
                if get_approved_leave_for_date
                else None
            )
        except Exception:
            leave = None
        is_sunday_off = (
            is_sunday
            and query_date not in sunday_approvals.get(emp_id, set())
        )
        if resolve_daily_report_status:
            status, att = resolve_daily_report_status(
                att,
                approved_leave=bool(leave),
                paid_holiday=is_public_holiday or is_sunday_off,
            )
        else:
            status = att.get("status", "Not Marked")
            if leave:
                status = "Approved Leave"
                att = {}
            if is_public_holiday or is_sunday_off:
                status = "Paid Holiday"
                att = {}
        checkin_time = att.get("arrival_time") or att.get("checkin_time") or "-"
        checkout_time = att.get("checkout_time") or "-"
        try:
            missed_checkout = is_missed_checkout(att) if is_missed_checkout else False
        except Exception:
            missed_checkout = False
        late_minutes = int(att.get("late_minutes") or 0)
        shift = emp.get("shift") or "N/A"
        if get_employee_shift:
            try:
                shift = get_employee_shift(emp_id) or shift
            except Exception:
                pass

        report.append({
            "id": str(emp_id),
            "name": emp.get("name", "Unknown"),
            "department": emp.get("department", "N/A"),
            "shift": shift,
            "status": "Missed Checkout" if missed_checkout else status,
            "checkin_time": checkin_time,
            "checkout_time": checkout_time,
            "hours_worked": round(float(att.get("hours_worked") or 0), 2),
            "late_hours": round(late_minutes / 60, 2),
            "overtime_hours": round(float(att.get("overtime_hours") or 0), 2),
            "marked_by": att.get("marked_by", "-"),
            "missed_checkout": missed_checkout,
        })
    return report


def get_today_report():
    """Backward-compatible wrapper for today's report."""
    return get_daily_report(_today())


#  16. GET EMPLOYEE ATTENDANCE HISTORY
# ══════════════════════════════════════════════
def get_employee_attendance_history(emp_id, limit=30):
    """
    Returns last `limit` attendance records for an employee.
    Used in employee dashboard to show their own history.
    Returns list of dicts { date, status, checkin_time }
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return []

    records = attendance_col.find(
        {"emp_id": emp_id, "deleted": {"$ne": True}},
        {"_id": 0, "date": 1, "status": 1, "checkin_time": 1, "arrival_time": 1, "checkout_time": 1}
    ).sort("date", -1).limit(limit)

    return list(records)


# ══════════════════════════════════════════════
#  LEAVE REQUEST COLLECTION
# ══════════════════════════════════════════════
from bson import ObjectId

leave_requests_col = _db["leave_requests"]


# ══════════════════════════════════════════════
#  17. SUBMIT LEAVE REQUEST  (Employee)
# ══════════════════════════════════════════════
def _format_leave_days(days):
    try:
        days = float(days)
    except (TypeError, ValueError):
        return str(days)
    return str(int(days)) if days.is_integer() else str(days)


def _log_leave_audit(action, performed_by, emp_id, request_id=None, details=""):
    try:
        from audit_log import log_action
        target = f"Employee ID {emp_id}"
        if request_id:
            target = f"{target} | Request {request_id}"
        log_action(action, str(performed_by), target=target, details=details)
    except Exception as exc:
        print(f"Audit log failed for {action}: {exc}")


def _leave_can_be_reverted(doc):
    try:
        leave_end = _parse_yyyy_mm_dd(doc.get("to_date"), "To date")
    except ValueError:
        return False
    return leave_end >= _app_today_date()


def submit_leave_request(emp_id, leave_type, from_date, to_date, reason, leave_duration="Full Day"):
    """
    Employee submits a leave request.
    Supports Full Day, Half Day, and Quarter Leave durations.
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"

    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"No employee found with ID {emp_id}!"

    if not from_date or not to_date:
        return False, "From date and To date are required!"

    if not reason or not reason.strip():
        return False, "Reason cannot be empty!"
    reason = reason.strip()
    if len(reason) < 10 or len(reason.split()) < 3:
        return False, "Reason is too short. Please explain the leave in at least 3 words."

    try:
        d1 = _parse_yyyy_mm_dd(from_date, "From date")
        d2 = _parse_yyyy_mm_dd(to_date, "To date")
    except ValueError as exc:
        return False, str(exc)

    if d1 > d2:
        return False, "From date cannot be after To date!"

    today = _app_today_date()
    if d1 <= today:
        return False, "Leave requests must start from tomorrow or later. Today and past dates are not allowed!"

    full_days = (d2 - d1).days + 1

    duration_values = {
        "Full Day": 1,
        "Half Day": 0.5,
        "Quarter Leave": 0.25,
    }
    if leave_duration not in duration_values:
        return False, "Please select a valid leave duration!"

    leave_type_rules = {
        "Sick Leave": {"Full Day", "Half Day", "Quarter Leave"},
        "Casual Leave": {"Full Day", "Half Day"},
        "Annual Leave": {"Full Day"},
        "Other": {"Full Day", "Half Day"},
    }
    if leave_type not in leave_type_rules:
        return False, "Please select a valid leave type!"
    if leave_duration not in leave_type_rules[leave_type]:
        allowed = ", ".join(sorted(leave_type_rules[leave_type]))
        return False, f"{leave_type} allows only: {allowed}."

    if full_days > 1 and leave_duration != "Full Day":
        return False, "Half Day and Quarter Leave can only be requested for a single date!"

    working_dates = _business_dates(emp_id, d1, d2)
    if not working_dates:
        return False, "Selected dates are Sunday holidays or public holidays. No leave is required for these dates."

    days = len(working_dates) if leave_duration == "Full Day" else duration_values[leave_duration]

    # Always store and query dates as YYYY-MM-DD so MongoDB string comparisons
    # are correct regardless of the input format the UI submitted (DD/MM/YY).
    from_date_iso = d1.isoformat()
    to_date_iso   = d2.isoformat()

    active_overlap = leave_requests_col.find_one({
        "emp_id": emp_id,
        "status": {"$in": ["Pending", "Approved", "Revert Requested"]},
        "from_date": {"$lte": to_date_iso},
        "to_date":   {"$gte": from_date_iso},
    })
    if active_overlap:
        return False, "A pending or approved leave request already exists for these dates."

    available, balance_error = _leave_balance_available(emp_id)
    if balance_error:
        return False, balance_error
    paid_days = min(days, available)
    unpaid_days = max(days - paid_days, 0)

    insert_result = leave_requests_col.insert_one({
        "emp_id": emp_id,
        "emp_name": emp.get("name", "Unknown"),
        "leave_type": leave_type,
        "leave_duration": leave_duration,
        "from_date": from_date_iso,
        "to_date":   to_date_iso,
        "days": days,
        "paid_days": paid_days,
        "unpaid_days": unpaid_days,
        "calendar_days": full_days,
        "working_dates": working_dates,
        "reason": reason,
        "status": "Pending",
        "submitted_on": _today(),
        "reviewed_on": None,
        "remarks": None,
    })
    _log_leave_audit(
        "LEAVE_REQUEST",
        f"emp_{emp_id}",
        emp_id,
        insert_result.inserted_id,
        f"{emp.get('name', 'Unknown')} requested {leave_type} from {from_date_iso} to {to_date_iso} "
        f"for {_format_leave_days(days)} working day(s).",
    )
    if unpaid_days:
        return True, (
            f"Leave request submitted for {_format_leave_days(days)} working day(s). "
            f"Paid: {_format_leave_days(paid_days)}, unpaid: {_format_leave_days(unpaid_days)}."
        )
    return True, f"Leave request submitted for {_format_leave_days(days)} working day(s) ({from_date_iso} to {to_date_iso})!"


# ══════════════════════════════════════════════
#  18. GET LEAVE REQUESTS
# ══════════════════════════════════════════════
def get_leave_requests(emp_id=None):
    """
    Admin: pass emp_id=None → returns ALL requests (newest first).
    Employee: pass emp_id → returns only their requests.
    Each record has a string 'request_id' field added.
    """
    query = {} if emp_id is None else {"emp_id": int(emp_id)}
    docs  = leave_requests_col.find(
        query,
        {
            "emp_id": 1,
            "emp_name": 1,
            "leave_type": 1,
            "leave_duration": 1,
            "from_date": 1,
            "to_date": 1,
            "days": 1,
            "paid_days": 1,
            "unpaid_days": 1,
            "reason": 1,
            "status": 1,
            "submitted_on": 1,
            "remarks": 1,
            "revert_reason": 1,
            "revert_requested_on": 1,
            "working_dates": 1,
        },
    ).sort("submitted_on", -1)

    result = []
    for doc in docs:
        result.append({
            "request_id":   str(doc["_id"]),
            "emp_id":       str(doc.get("emp_id",     "—")),
            "emp_name":     doc.get("emp_name",        "—"),
            "leave_type":   doc.get("leave_type",      "—"),
            "leave_duration": doc.get("leave_duration", "Full Day"),
            "from_date":    doc.get("from_date",       "—"),
            "to_date":      doc.get("to_date",         "—"),
            "days":         _format_leave_days(doc.get("days", "N/A")),
            "paid_days":    _format_leave_days(doc.get("paid_days", doc.get("days", 0))),
            "unpaid_days":  _format_leave_days(doc.get("unpaid_days", 0)),
            "reason":       doc.get("reason",          "—"),
            "status":       doc.get("status",          "Pending"),
            "submitted_on": doc.get("submitted_on",    "—"),
            "remarks":      doc.get("remarks",         ""),
            "revert_reason": doc.get("revert_reason",   ""),
            "revert_requested_on": doc.get("revert_requested_on", ""),
            "can_revert":    _leave_can_be_reverted(doc),
        })
    return result


def request_leave_revert(request_id, emp_id, reason):
    """
    Employee requests admin to revert an approved leave request.
    Admin still makes the final decision.
    """
    try:
        oid = ObjectId(request_id)
        emp_id = int(emp_id)
    except Exception:
        return False, "Invalid leave request!"

    reason = (reason or "").strip()
    if not reason:
        return False, "Reason is required for requesting a leave revert."
    if len(reason) < 10 or len(reason.split()) < 3:
        return False, "Reason is too short. Please explain in at least 3 words."

    doc = leave_requests_col.find_one({"_id": oid, "emp_id": emp_id})
    if not doc:
        return False, "Leave request not found!"

    status = doc.get("status", "Pending")
    if status == "Revert Requested":
        return False, "A revert request is already pending for this leave."
    if status != "Approved":
        return False, "Only approved leave requests can be requested for revert."
    if not _leave_can_be_reverted(doc):
        return False, "Leave revert is not allowed after the leave end date has passed."

    leave_requests_col.update_one(
        {"_id": oid},
        {"$set": {
            "status": "Revert Requested",
            "revert_reason": reason,
            "revert_requested_on": _today(),
            "remarks": "Employee requested leave revert.",
        }}
    )
    _log_leave_audit(
        "LEAVE_REVERT_REQUESTED",
        f"emp_{emp_id}",
        emp_id,
        request_id,
        f"Employee requested revert for approved leave from {doc.get('from_date')} to {doc.get('to_date')}.",
    )
    return True, "Revert request sent to admin for approval."


# ══════════════════════════════════════════════
#  19. APPROVE / REJECT LEAVE REQUEST  (Admin)
# ══════════════════════════════════════════════
def update_leave_request(request_id, action, remarks="", reviewed_by="admin"):
    """
    Admin approves, rejects, or reverts a leave request.
    Reverting an approved request restores the deducted leave balance.
    """
    if action not in ("Approved", "Rejected", "Reverted", "Revert Rejected"):
        return False, "Action must be 'Approved', 'Rejected', 'Reverted', or 'Revert Rejected'!"

    remarks = remarks.strip()
    if action in ("Rejected", "Reverted", "Revert Rejected") and not remarks:
        return False, "Reason is required for rejecting or reverting a leave request!"

    try:
        oid = ObjectId(request_id)
    except Exception:
        return False, "Invalid request ID!"

    doc = leave_requests_col.find_one({"_id": oid})
    if not doc:
        return False, "Leave request not found!"

    current_status = doc.get("status", "Pending")
    if action in ("Approved", "Rejected") and current_status != "Pending":
        return False, f"This request is already {current_status}!"
    if action == "Reverted" and current_status not in ("Approved", "Revert Requested"):
        return False, "Only approved leave requests can be reverted!"
    if action == "Revert Rejected" and current_status != "Revert Requested":
        return False, "Only pending revert requests can be rejected!"
    if action == "Approved":
        try:
            leave_start = _parse_yyyy_mm_dd(doc.get("from_date"), "From date")
        except ValueError:
            return False, "Leave request has an invalid start date and cannot be approved."
        if leave_start <= _app_today_date():
            return False, "Past or same-day leave requests cannot be approved."
    if action == "Reverted" and not _leave_can_be_reverted(doc):
        return False, "Leave revert is not allowed after the leave end date has passed."

    emp_id = doc.get("emp_id")
    days = float(doc.get("days", 1))
    paid_days = float(doc.get("paid_days", days))
    unpaid_days = float(doc.get("unpaid_days", max(days - paid_days, 0)))

    if action == "Approved":
        available, balance_error = _leave_balance_available(emp_id, exclude_request_id=oid)
        if balance_error:
            return False, balance_error
        paid_days = min(days, available)
        unpaid_days = max(days - paid_days, 0)

    approval_balance_snapshot = {}
    if action == "Approved":
        leave_balance_doc = leaves_col.find_one({"emp_id": emp_id}) or {}
        total_before = float(leave_balance_doc.get("total_leaves", 0) or 0)
        used_before = float(leave_balance_doc.get("used_leaves", 0) or 0)
        approval_balance_snapshot = {
            "approved_paid_days": paid_days,
            "balance_before_approval": max(total_before - used_before, 0),
            "used_leaves_before_approval": used_before,
        }

    restore_state = None
    if action == "Reverted":
        restore_days = float(doc.get("approved_paid_days", doc.get("paid_days", paid_days)) or 0)
        if restore_days > 0:
            restore_state = {"emp_id": emp_id, "restore_days": restore_days}
            restore_result = leaves_col.update_one(
                {"emp_id": emp_id, "used_leaves": {"$gte": restore_days}},
                {"$inc": {"used_leaves": -restore_days}}
            )
            if restore_result.matched_count == 0:
                return False, "Leave balance could not be restored. Revert cancelled so balance stays correct."

    final_status = "Approved" if action == "Revert Rejected" else action

    update_fields = {
        "status": final_status,
        "reviewed_on": _today(),
        "remarks": remarks,
        "paid_days": paid_days,
        "unpaid_days": unpaid_days,
    }
    update_fields.update(approval_balance_snapshot)
    if action == "Reverted":
        update_fields["balance_restored_days"] = float(doc.get("approved_paid_days", doc.get("paid_days", paid_days)) or 0)

    result = leave_requests_col.update_one(
        {"_id": oid, "status": current_status},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        if action == "Reverted" and restore_state:
            leaves_col.update_one(
                {"emp_id": restore_state["emp_id"]},
                {"$inc": {"used_leaves": restore_state["restore_days"]}}
            )
        return False, "This request was already actioned by another session. Please refresh and try again."

    if action == "Approved":
        if paid_days > 0:
            balance_result = leaves_col.update_one(
                {"emp_id": emp_id},
                {"$inc": {"used_leaves": paid_days}},
                upsert=False
            )
            if balance_result.matched_count == 0:
                leave_requests_col.update_one(
                    {"_id": oid, "status": "Approved"},
                    {"$set": {"status": "Pending"}, "$unset": {"reviewed_on": "", "remarks": ""}}
                )
                return False, "Leave balance record not found. Approval was cancelled so balance stays correct."
        _log_leave_audit(
            "LEAVE_APPROVED",
            reviewed_by,
            emp_id,
            request_id,
            f"Approved leave for {doc.get('emp_name')} from {doc.get('from_date')} to {doc.get('to_date')}. "
            f"Paid: {_format_leave_days(paid_days)}, unpaid: {_format_leave_days(unpaid_days)}.",
        )
        if unpaid_days:
            return True, (
                f"Leave Approved for {doc.get('emp_name')} ({_format_leave_days(days)} day(s)). "
                f"Paid: {_format_leave_days(paid_days)}, unpaid: {_format_leave_days(unpaid_days)}."
            )
        return True, f"Leave Approved for {doc.get('emp_name')} ({_format_leave_days(days)} day(s)). Balance updated."

    if action == "Reverted":
        _notify_employee(
            emp_id,
            "Leave request reverted",
            f"Your approved leave request for {_format_leave_days(days)} day(s) was reverted. Reason: {remarks}",
            request_id,
        )
        _log_leave_audit(
            "LEAVE_REVERTED",
            reviewed_by,
            emp_id,
            request_id,
            f"Reverted leave for {doc.get('emp_name')} from {doc.get('from_date')} to {doc.get('to_date')}. Reason: {remarks}",
        )
        return True, f"Leave Reverted for {doc.get('emp_name')} ({_format_leave_days(days)} day(s)). Balance restored."

    if action == "Revert Rejected":
        _notify_employee(
            emp_id,
            "Leave revert request denied",
            f"Your request to revert approved leave was denied. Reason: {remarks}",
            request_id,
        )
        _log_leave_audit(
            "LEAVE_REVERT_REJECTED",
            reviewed_by,
            emp_id,
            request_id,
            f"Rejected revert request for {doc.get('emp_name')}. Reason: {remarks}",
        )
        return True, f"Revert request denied for {doc.get('emp_name')}. Leave remains approved."

    _notify_employee(
        emp_id,
        "Leave request rejected",
        f"Your leave request for {_format_leave_days(days)} day(s) was rejected. Reason: {remarks}",
        request_id,
    )
    _log_leave_audit(
        "LEAVE_REJECTED",
        reviewed_by,
        emp_id,
        request_id,
        f"Rejected leave for {doc.get('emp_name')} from {doc.get('from_date')} to {doc.get('to_date')}. Reason: {remarks}",
    )
    return True, f"Leave Rejected for {doc.get('emp_name')}."
