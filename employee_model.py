import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import db as _db, employees_col
from app_time import now_stamp as _app_now_stamp
try:
    employees_col.create_index("emp_id", unique=True)
except Exception:
    pass

PUBLIC_EMPLOYEE_FIELDS = {"_id": 0, "password": 0}


def _active_employee_query(extra=None, include_deleted=False):
    query = dict(extra or {})
    if not include_deleted:
        query["deleted"] = {"$ne": True}
    return query

# ----------------------------------------------------------------------
#  1. ADD EMPLOYEE
# ----------------------------------------------------------------------
def add_employee(emp_id, name, department, salary):
    """
    Inserts a new employee document into MongoDB.
    - Checks for duplicate emp_id before inserting.
    - Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
        basic_salary = float(salary)
    except ValueError:
        return False, "Emp ID must be an integer and Salary must be a number!"

    if not name.strip() or not department.strip():
        return False, "Name and Department cannot be empty!"

    # Duplicate check includes active and deactivated employees.
    existing_emp = employees_col.find_one({"emp_id": emp_id}, {"deleted": 1})
    if existing_emp:
        if existing_emp.get("deleted"):
            return False, f"Employee ID {emp_id} already exists as deactivated. Restore it instead of re-adding."
        return False, f"Employee ID {emp_id} already exists!"

    employees_col.insert_one({
        "emp_id":     emp_id,
        "name":       name.strip(),
        "department": department.strip(),
        "basic_salary": basic_salary,
        "role":       "employee",
    })

    return True, f"Employee '{name}' added successfully!"


# ----------------------------------------------------------------------
#  2. GET ALL EMPLOYEES
# ----------------------------------------------------------------------
def get_all_employees(include_deleted=False):
    """
    Returns list of all employees sorted by emp_id.
    Sensitive fields are excluded. Soft-deleted employees are hidden by default.
    """
    return list(
        employees_col.find(
            _active_employee_query(include_deleted=include_deleted),
            PUBLIC_EMPLOYEE_FIELDS
        ).sort("emp_id", 1)
    )


# ----------------------------------------------------------------------
#  3. GET EMPLOYEE BY ID
# ----------------------------------------------------------------------
def get_employees_by_id(emp_id):
    """
    Returns a single employee document by emp_id.
    Returns None if not found.
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return None

    return employees_col.find_one(
        _active_employee_query({"emp_id": emp_id}),
        PUBLIC_EMPLOYEE_FIELDS
    )


# ----------------------------------------------------------------------
#  4. SEARCH EMPLOYEE
# ----------------------------------------------------------------------
def search_employee(keyword):
    """
    Searches employees by:
    - emp_id  -> if keyword is a number
    - name    -> case-insensitive partial match
    - department -> case-insensitive partial match
    Returns a list of matching documents.
    """
    try:
        # If keyword is a number -> search by emp_id
        emp_id = int(keyword)
        return list(employees_col.find(
            _active_employee_query({"emp_id": emp_id}),
            PUBLIC_EMPLOYEE_FIELDS
        ))
    except ValueError:
        # Otherwise -> search by name OR department
        return list(employees_col.find(
            _active_employee_query({"$or": [
                {"name":       {"$regex": keyword, "$options": "i"}},
                {"department": {"$regex": keyword, "$options": "i"}}
            ]}),
            PUBLIC_EMPLOYEE_FIELDS
        ))


# ----------------------------------------------------------------------
#  5. UPDATE EMPLOYEE
# ----------------------------------------------------------------------
def update_employee(emp_id, name=None, department=None, salary=None, basic_salary=None):
    """
    Updates one or more fields of an existing employee.
    Only updates fields that are provided (not None).
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"

    if not employees_col.find_one(_active_employee_query({"emp_id": emp_id})):
        return False, f"Employee ID {emp_id} not found!"

    # Build update dict - only include provided fields
    updates = {}
    if name:
        updates["name"]       = name.strip()
    if department:
        updates["department"] = department.strip()
    salary_value = basic_salary if basic_salary is not None else salary
    if salary_value is not None:
        try:
            salary_value = float(salary_value)
            if salary_value < 0:
                return False, "Basic salary cannot be negative!"
            updates["basic_salary"] = salary_value
        except (ValueError, TypeError):
            return False, "Basic salary must be a number!"

    if not updates:
        return False, "No fields provided to update!"

    update_doc = {"$set": updates}
    if "basic_salary" in updates:
        update_doc["$unset"] = {"salary": ""}

    employees_col.update_one(
        _active_employee_query({"emp_id": emp_id}),
        update_doc
    )

    return True, f"Employee ID {emp_id} updated successfully!"


# ----------------------------------------------------------------------
#  6. DELETE EMPLOYEE
# ----------------------------------------------------------------------
def delete_employee(emp_id):
    """
    Deletes an employee by emp_id.
    Returns (True, message) or (False, error)
    """
    try:
        emp_id = int(emp_id)
    except ValueError:
        return False, "Emp ID must be an integer!"

    emp = employees_col.find_one({"emp_id": emp_id})
    if not emp:
        return False, f"Employee ID {emp_id} not found!"
    if emp.get("deleted"):
        return False, f"Employee ID {emp_id} is already deactivated!"

    result = employees_col.update_one(
        {"emp_id": emp_id},
        {"$set": {"deleted": True, "deleted_at": _app_now_stamp()}}
    )

    if result.modified_count:
        return True, f"Employee ID {emp_id} deactivated successfully!"

    return False, f"Employee ID {emp_id} not found!"


# ----------------------------------------------------------------------
#  7. GET EMPLOYEES BY DEPARTMENT
# ----------------------------------------------------------------------
def get_employees_by_department(department):
    """
    Returns all employees from a specific department.
    Case-insensitive match.
    """
    return list(employees_col.find(
        _active_employee_query({"department": {"$regex": department, "$options": "i"}}),
        PUBLIC_EMPLOYEE_FIELDS
    ).sort("name", 1))


# ----------------------------------------------------------------------
#  8. GET TOTAL EMPLOYEE COUNT
# ----------------------------------------------------------------------
def get_employee_count():
    """
    Returns total number of employees in the collection.
    """
    return employees_col.count_documents(_active_employee_query())


# ----------------------------------------------------------------------
#  9. GET DEPARTMENT SUMMARY
# ----------------------------------------------------------------------
def get_department_summary():
    """
    Returns count of employees per department.
    Uses MongoDB aggregation pipeline.
    Example output:
    [
        {"_id": "IT",      "count": 3, "avg_salary": 55000},
        {"_id": "HR",      "count": 2, "avg_salary": 31000},
        {"_id": "Finance", "count": 2, "avg_salary": 46000},
    ]
    """
    pipeline = [
        {
            "$match": _active_employee_query()
        },
        {
            "$group": {
                "_id":        "$department",
                "count":      {"$sum": 1},
                "avg_salary": {"$avg": {"$ifNull": ["$basic_salary", "$salary"]}},
                "max_salary": {"$max": {"$ifNull": ["$basic_salary", "$salary"]}},
                "min_salary": {"$min": {"$ifNull": ["$basic_salary", "$salary"]}}
            }
        },
        {
            "$sort": {"count": -1}   # most employees first
        }
    ]
    return list(employees_col.aggregate(pipeline))
