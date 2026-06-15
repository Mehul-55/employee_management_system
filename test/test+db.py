import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.employee_model import *
from models.attendance import*

# ══════════════════════════════════════════════
#  HELPER — pretty print results
# ══════════════════════════════════════════════
def section(title):
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

def show(label, result):
    print(f"\n🔹 {label}")
    if isinstance(result, list):
        if not result:
            print("   (empty list)")
        for item in result:
            print(f"   {item}")
    else:
        print(f"   {result}")

# ══════════════════════════════════════════════
#  TEST 1 — ADD EMPLOYEES
# ══════════════════════════════════════════════
section("TEST 1 — ADD EMPLOYEE")

ok, msg = add_employee(101, "Aman Sharma",  "IT",      55000)
print(msg)

ok, msg = add_employee(102, "Neha Verma",   "HR",      32000)
print(msg)

ok, msg = add_employee(103, "Rohit Meena",  "Finance", 47000)
print(msg)

# Duplicate test
ok, msg = add_employee(101, "Duplicate",    "IT",      10000)
print(msg)   # should say already exists

# Invalid input test
ok, msg = add_employee("abc", "Test", "IT", "xyz")
print(msg)   # should say type error

# ══════════════════════════════════════════════
#  TEST 2 — GET ALL EMPLOYEES
# ══════════════════════════════════════════════
section("TEST 2 — GET ALL EMPLOYEES")
show("All Employees", get_all_employees())

# ══════════════════════════════════════════════
#  TEST 3 — GET BY ID
# ══════════════════════════════════════════════
section("TEST 3 — GET EMPLOYEE BY ID")
show("Emp ID 102", get_employees_by_id(102))
show("Emp ID 999 (not exists)", get_employees_by_id(999))

# ══════════════════════════════════════════════
#  TEST 4 — SEARCH
# ══════════════════════════════════════════════
section("TEST 4 — SEARCH EMPLOYEE")
show("Search by ID '101'",         search_employee("101"))
show("Search by name 'neha'",      search_employee("neha"))
show("Search by dept 'finance'",   search_employee("finance"))
show("Search unknown 'xyz'",       search_employee("xyz"))

# ══════════════════════════════════════════════
#  TEST 5 — UPDATE EMPLOYEE
# ══════════════════════════════════════════════
section("TEST 5 — UPDATE EMPLOYEE")
ok, msg = update_employee(101, salary=60000)
print(msg)

ok, msg = update_employee(102, name="Neha Verma Singh", department="Admin")
print(msg)

ok, msg = update_employee(999)   # not found
print(msg)

show("After update — Emp 101", get_employees_by_id(101))
show("After update — Emp 102", get_employees_by_id(102))

# ══════════════════════════════════════════════
#  TEST 6 — DEPARTMENT FILTER
# ══════════════════════════════════════════════
section("TEST 6 — GET BY DEPARTMENT")
show("IT Department",      get_employees_by_department("IT"))
show("Finance Department", get_employees_by_department("finance"))

# ══════════════════════════════════════════════
#  TEST 7 — COUNT + SUMMARY
# ══════════════════════════════════════════════
section("TEST 7 — COUNT & DEPARTMENT SUMMARY")
show("Total Employees", get_employee_count())
show("Department Summary", get_department_summary())

# ══════════════════════════════════════════════
#  TEST 8 — MARK ARRIVAL
# ══════════════════════════════════════════════
section("TEST 8 — MARK ARRIVAL")
ok, msg = mark_arrival(101, "Present", "09:00")
print(msg)

ok, msg = mark_arrival(102, "Late",    "09:45")
print(msg)

# ══════════════════════════════════════════════
#  TEST 9 — MARK ABSENT
# ══════════════════════════════════════════════
section("TEST 9 — MARK ABSENT")
ok, msg = mark_absent(103)
print(msg)   # already has record — should block

# ══════════════════════════════════════════════
#  TEST 11 — MARK CHECKOUT
# ══════════════════════════════════════════════
section("TEST 11 — MARK CHECKOUT")
ok, msg = mark_checkout(101, "17:30")
print(msg)   # should show hours worked

ok, msg = mark_checkout(102, "18:00")
print(msg)

# Checkout without checkin
ok, msg = mark_checkout(999, "17:00")
print(msg)   # should say not checked in

# Double checkout test
ok, msg = mark_checkout(101, "19:00")
print(msg)   # should say already checked out

# ══════════════════════════════════════════════
#  TEST 12 — GET ATTENDANCE BY DATE
# ══════════════════════════════════════════════
section("TEST 12 — GET ATTENDANCE BY DATE (TODAY)")
show("Today's Attendance", get_attendance_by_date())

# ══════════════════════════════════════════════
#  TEST 13 — GET ATTENDANCE BY EMPLOYEE
# ══════════════════════════════════════════════
section("TEST 13 — GET ATTENDANCE BY EMPLOYEE")
show("Emp 101 Full History", get_attendance_by_employee)

# ══════════════════════════════════════════════
#  TEST 15 — DELETE ATTENDANCE
# ══════════════════════════════════════════════
section("TEST 15 — DELETE ATTENDANCE RECORD")
ok, msg = delete_attendance(103)
print(msg)   # should delete

ok, msg = delete_attendance(999)
print(msg)   # should say not found

# ══════════════════════════════════════════════
#  TEST 16 — DELETE EMPLOYEE
# ══════════════════════════════════════════════
section("TEST 16 — DELETE EMPLOYEE")
ok, msg = delete_employee(103)
print(msg)

ok, msg = delete_employee(999)
print(msg)   # should say not found

show("Final Employee List", get_all_employees())

# ══════════════════════════════════════════════
print("\n" + "="*50)
print("  ALL TESTS COMPLETE")
print("="*50)