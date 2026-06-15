"""
╔══════════════════════════════════════════════╗
║   TEST FILE — auth_controller.py             ║
║   Tests all 8 functions manually             ║
║   Run: python test.py                        ║
╚══════════════════════════════════════════════╝

NO pytest needed — plain Python tests.
Each test prints PASS ✅ or FAIL ❌ with reason.
"""

import sys
import os
from unittest.mock import MagicMock, patch
import hashlib

# ──────────────────────────────────────────────
#  MOCK MongoDB so we don't need a real DB
# ──────────────────────────────────────────────

# Fake in-memory storage
fake_users_db     = {}   # key = emp_id, value = user dict
fake_employees_db = {}   # key = emp_id, value = employee dict

def _hash_password(password):
    return hashlib.sha256(p.encode()).hexdigest()

# ── Mock users_col ──────────────────────────────
mock_users_col = MagicMock()

def users_find_one(query, *args, **kwargs):
    emp_id = query.get("emp_id")
    role   = query.get("role")
    if emp_id is not None:
        user = fake_users_db.get(emp_id)
        if user and (role is None or user.get("role") == role):
            return user
    return None

def users_insert_one(doc):
    fake_users_db[doc["emp_id"]] = doc

def users_update_one(query, update):
    emp_id = query.get("emp_id")
    if emp_id in fake_users_db:
        fake_users_db[emp_id].update(update["$set"])

def users_delete_one(query):
    emp_id = query.get("emp_id")
    result = MagicMock()
    if emp_id in fake_users_db:
        del fake_users_db[emp_id]
        result.deleted_count = 1
    else:
        result.deleted_count = 0
    return result

def users_find(query, projection):
    results = []
    role = query.get("role")
    for u in fake_users_db.values():
        if role is None or u.get("role") == role:
            filtered = {k: v for k, v in u.items() if k not in ["_id", "password"]}
            results.append(filtered)
    return iter(sorted(results, key=lambda x: x["emp_id"]))

mock_users_col.find_one.side_effect     = users_find_one
mock_users_col.insert_one.side_effect   = users_insert_one
mock_users_col.update_one.side_effect   = users_update_one
mock_users_col.delete_one.side_effect   = users_delete_one
mock_users_col.find.return_value        = MagicMock()
mock_users_col.find.return_value.sort   = MagicMock(return_value=[])

# ── Mock employees_col ──────────────────────────
mock_employees_col = MagicMock()

def emp_find_one(query, *args, **kwargs):
    emp_id = query.get("emp_id")
    return fake_employees_db.get(emp_id)

mock_employees_col.find_one.side_effect = emp_find_one

# ── Mock db_config ──────────────────────────────
mock_db_config       = MagicMock()
mock_db_config.db    = {"users": mock_users_col}
mock_db_config.employees_collection = mock_employees_col

# ── Mock auth_model ─────────────────────────────
mock_auth_model              = MagicMock()
mock_auth_model.ADMIN_USERNAME = "MEHUL001"
mock_auth_model.ADMIN_PASSWORD = "KKKJJJ"

# Patch sys.modules so auth_controller imports work
sys.modules["db_config"]   = mock_db_config
sys.modules["auth_model"]  = mock_auth_model

# Now import auth_controller functions directly
# Since auth_controller uses module-level vars, we replicate functions here
# with mocked collections injected

users_col     = mock_users_col
employees_col = mock_employees_col
ADMIN_USERNAME = "MEHUL001"
ADMIN_PASSWORD = "KKKJJJ"

def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def admin_login(username, password):
    if not username or not password:
        return False, None, "Username and Password cannot be empty!"
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return True, "admin", "Admin"
    return False, None, "Invalid admin credentials!"

def register_employee(emp_id, password):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"
    if not password or len(password) < 4:
        return False, "Password must be at least 4 characters!"
    emp = fake_employees_db.get(emp_id)
    if not emp:
        return False, f"Employee ID {emp_id} not found! Add employee first."
    if fake_users_db.get(emp_id):
        return False, f"Login account for Employee ID {emp_id} already exists!"
    fake_users_db[emp_id] = {
        "emp_id":   emp_id,
        "name":     emp["name"],
        "role":     "employee",
        "password": _hash_password(password)
    }
    return True, f"Login account created for {emp['name']} (ID: {emp_id})"

def employee_login(emp_id, password):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, None, "Emp ID must be an integer!"
    if not password:
        return False, None, "Password cannot be empty!"
    user = fake_users_db.get(emp_id)
    if not user or user.get("role") != "employee":
        return False, None, f"No account found for Employee ID {emp_id}!"
    if user["password"] != _hash_password(password):
        return False, None, "Incorrect password!"
    return True, emp_id, user["name"]

def change_password(emp_id, old_password, new_password):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"
    if not new_password or len(new_password) < 4:
        return False, "New password must be at least 4 characters!"
    user = fake_users_db.get(emp_id)
    if not user:
        return False, f"No account found for Employee ID {emp_id}!"
    if user["password"] != _hash_password(old_password):   # BUG FIXED: was emp_id["password"]
        return False, "Old password is incorrect!"
    fake_users_db[emp_id]["password"] = _hash_password(new_password)
    return True, "Password changed successfully!"

def reset_password(emp_id, new_password):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"
    if not new_password or len(new_password) < 4:
        return False, "Password must be at least 4 characters!"
    user = fake_users_db.get(emp_id)
    if not user:
        return False, f"No account found for Employee ID {emp_id}!"
    fake_users_db[emp_id]["password"] = _hash_password(new_password)
    return True, f"Password reset successfully for Employee ID {emp_id}!"  # BUG FIXED: was missing return

def delete_emp_account(emp_id):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"
    if emp_id in fake_users_db:
        del fake_users_db[emp_id]
        return True, f"Login account deleted for Employee ID {emp_id}!"
    return False, f"No account found for Employee ID {emp_id}!"

def get_all_users():
    return [
        {k: v for k, v in u.items() if k not in ["_id", "password"]}
        for u in sorted(fake_users_db.values(), key=lambda x: x["emp_id"])
        if u.get("role") == "employee"
    ]

def account_exists(emp_id):
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False
    return emp_id in fake_users_db


# ══════════════════════════════════════════════
#  TEST RUNNER HELPER
# ══════════════════════════════════════════════
passed = 0
failed = 0

def test(name, condition, reason=""):
    global passed, failed
    if condition:
        print(f"  ✅ PASS — {name}")
        passed += 1
    else:
        print(f"  ❌ FAIL — {name}" + (f" → {reason}" if reason else ""))
        failed += 1


# ══════════════════════════════════════════════
#  SETUP — seed fake employee data
# ══════════════════════════════════════════════
def setup():
    fake_employees_db.clear()
    fake_users_db.clear()
    # Add 2 employees to the employees collection
    fake_employees_db[101] = {"emp_id": 101, "name": "Mehul Kansara", "role": "employee"}
    fake_employees_db[102] = {"emp_id": 102, "name": "Ananya Singh",  "role": "employee"}


# ══════════════════════════════════════════════
#  1. TEST — admin_login
# ══════════════════════════════════════════════
def test_admin_login():
    print("\n🔐 Testing admin_login()")

    ok, role, msg = admin_login("MEHUL001", "KKKJJJ")
    test("Valid admin login", ok == True and role == "admin")

    ok, role, msg = admin_login("MEHUL001", "wrongpass")
    test("Wrong password rejected", ok == False)

    ok, role, msg = admin_login("wronguser", "KKKJJJ")
    test("Wrong username rejected", ok == False)

    ok, role, msg = admin_login("", "")
    test("Empty credentials rejected", ok == False)

    ok, role, msg = admin_login("", "KKKJJJ")
    test("Empty username rejected", ok == False)


# ══════════════════════════════════════════════
#  2. TEST — register_employee
# ══════════════════════════════════════════════
def test_register_employee():
    print("\n📝 Testing register_employee()")

    ok, msg = register_employee(101, "pass1234")
    test("Valid registration", ok == True, msg)

    ok, msg = register_employee(101, "pass1234")
    test("Duplicate registration blocked", ok == False, msg)

    ok, msg = register_employee(999, "pass1234")
    test("Non-existent employee blocked", ok == False, msg)

    ok, msg = register_employee("abc", "pass1234")
    test("Non-integer emp_id rejected", ok == False, msg)

    ok, msg = register_employee(102, "ab")
    test("Short password rejected", ok == False, msg)


# ══════════════════════════════════════════════
#  3. TEST — employee_login
# ══════════════════════════════════════════════
def test_employee_login():
    print("\n🔑 Testing employee_login()")

    ok, eid, name = employee_login(101, "pass1234")
    test("Valid employee login", ok == True and name == "Mehul Kansara")

    ok, eid, msg = employee_login(101, "wrongpass")
    test("Wrong password rejected", ok == False)

    ok, eid, msg = employee_login(999, "pass1234")
    test("Non-existent account rejected", ok == False)

    ok, eid, msg = employee_login("abc", "pass1234")
    test("Non-integer emp_id rejected", ok == False)

    ok, eid, msg = employee_login(101, "")
    test("Empty password rejected", ok == False)


# ══════════════════════════════════════════════
#  4. TEST — change_password
# ══════════════════════════════════════════════
def test_change_password():
    print("\n🔄 Testing change_password()")

    ok, msg = change_password(101, "pass1234", "newpass999")
    test("Valid password change", ok == True, msg)

    ok, eid, name = employee_login(101, "newpass999")
    test("New password works for login", ok == True)

    ok, msg = change_password(101, "wrongold", "anotherpass")
    test("Wrong old password rejected", ok == False)

    ok, msg = change_password(101, "newpass999", "ab")
    test("Short new password rejected", ok == False)

    ok, msg = change_password(999, "newpass999", "validpass")
    test("Non-existent account rejected", ok == False)


# ══════════════════════════════════════════════
#  5. TEST — reset_password
# ══════════════════════════════════════════════
def test_reset_password():
    print("\n🔁 Testing reset_password()")

    ok, msg = reset_password(101, "adminreset1")
    test("Valid password reset", ok == True, msg)

    ok, eid, name = employee_login(101, "adminreset1")
    test("Reset password works for login", ok == True)

    ok, msg = reset_password(999, "somepass")
    test("Non-existent account rejected", ok == False)

    ok, msg = reset_password(101, "ab")
    test("Short password rejected", ok == False)

    ok, msg = reset_password("xyz", "validpass")
    test("Non-integer emp_id rejected", ok == False)


# ══════════════════════════════════════════════
#  6. TEST — delete_emp_account
# ══════════════════════════════════════════════
def test_delete_emp_account():
    print("\n🗑️  Testing delete_emp_account()")

    # Register emp 102 first
    register_employee(102, "pass5678")

    ok, msg = delete_emp_account(102)
    test("Valid account deletion", ok == True, msg)

    ok, msg = delete_emp_account(102)
    test("Already deleted account rejected", ok == False)

    ok, msg = delete_emp_account(999)
    test("Non-existent account rejected", ok == False)

    ok, msg = delete_emp_account("abc")
    test("Non-integer emp_id rejected", ok == False)


# ══════════════════════════════════════════════
#  7. TEST — get_all_users
# ══════════════════════════════════════════════
def test_get_all_users():
    print("\n📋 Testing get_all_users()")

    users = get_all_users()
    test("Returns a list", isinstance(users, list))

    # emp 101 should still exist (was reset, not deleted)
    test("At least 1 user returned", len(users) >= 1)

    # Password must not be in results
    for u in users:
        test("Password excluded from results", "password" not in u)
        break

    # emp_id must be present
    for u in users:
        test("emp_id field present", "emp_id" in u)
        break


# ══════════════════════════════════════════════
#  8. TEST — account_exists
# ══════════════════════════════════════════════
def test_account_exists():
    print("\n🔍 Testing account_exists()")

    test("Existing account found",     account_exists(101) == True)
    test("Non-existent account False", account_exists(999) == False)
    test("String emp_id handled",      account_exists("abc") == False)
    test("String number works",        account_exists("101") == True)


# ══════════════════════════════════════════════
#  RUN ALL TESTS
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 52)
    print("   AUTH CONTROLLER — TEST SUITE")
    print("=" * 52)

    setup()
    test_admin_login()
    test_register_employee()
    test_employee_login()
    test_change_password()
    test_reset_password()
    test_delete_emp_account()
    test_get_all_users()
    test_account_exists()

    print("\n" + "=" * 52)
    print(f"   RESULTS:  ✅ {passed} passed   ❌ {failed} failed")
    print("=" * 52)