"""
------------------------------------------------------------------------------------------------------------------------------------------------
---   Attendance Model                           ---
---   attendance.py --- Core attendance logic      ---
------------------------------------------------------------------------------------------------------------------------------------------------
"""

import sys, os
import calendar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta

from pymongo.errors import DuplicateKeyError

from db_config import client as _client, db as _db, employees_col
from audit_log import log_action


# ------------------------------------------------------------------------------------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------------------------------------------------------------------------------------
attendance_col = _db["attendance"]
holidays_col   = _db["holidays"]
leave_requests_col = _db["leave_requests"]
departments_col =_db["departments"]
# Prevent duplicate attendance per employee per day
try:
    attendance_col.create_index(
        [("emp_id", 1), ("date", 1)],
        unique=True
    )
except Exception as e:
    print(f"[ATTENDANCE WARNING] Could not create unique attendance index: {e}")

# ------------------------------------------------------------------------------------------------------------------------------------------
# OFFICE RULES  (fallback when no shift assigned)
# ------------------------------------------------------------------------------------------------------------------------------------------
OFFICE_START   = "09:00"
LATE_LIMIT     = "09:15"
HALFDAY_LIMIT  = "12:00"
FULLDAY_HOURS  = 8
OVERTIME_LIMIT = 9
HALFDAY_LATE_THRESHOLD_RATIO = 0.25
ABSENT_LATE_THRESHOLD_RATIO  = 0.50
MAX_CHECKIN_DELAY_MINUTES = 120

# ------------------------------------------------------------------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------------------------------------------------------------------
def _resolve_emp_id(emp_id):
    """
    Accepts only a numeric emp_id. Names are not unique enough for identity.
    Returns (int_emp_id, None) on success or (None, error_message) on failure.
    """
    try:
        return int(emp_id), None
    except (ValueError, TypeError):
        return None, "Employee ID must be a number!"

def _trusted_now():
    """
    Prefer MongoDB server time so client clock changes do not silently control
    employee check-in/check-out. Falls back to local time if DB time is unavailable,
    and prints a warning so the admin knows times may be unreliable.
    """
    try:
        status = _client.admin.command("serverStatus")
        server_now = status.get("localTime")
        if isinstance(server_now, datetime):
            return server_now.replace(tzinfo=None)
    except Exception as e:
        print(f"[ATTENDANCE WARNING] MongoDB server time unavailable ({e}). "
              f"Falling back to local system clock — check-in times may be unreliable.")
    return datetime.now()


def _today():
    return _trusted_now().date().isoformat()


def _now_time():
    return _trusted_now().strftime("%H:%M")


def _now_stamp():
    return _trusted_now().strftime("%Y-%m-%d %H:%M:%S")


def _as_date_string(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value = str(value).strip()[:10]
    try:
        date.fromisoformat(value)
        return value
    except (TypeError, ValueError):
        return None


def _employee_joining_date(emp):
    for field in ("joining_date", "join_date", "date_of_joining", "created_at"):
        value = _as_date_string(emp.get(field))
        if value:
            return value
    return None


def _employee_leaving_date(emp):
    for field in ("resignation_date", "leaving_date", "date_of_leaving", "termination_date", "deleted_at"):
        value = _as_date_string(emp.get(field))
        if value:
            return value
    return None


def _employee_overlaps_period(emp, period_start, period_end):
    joining_date = _employee_joining_date(emp)
    leaving_date = _employee_leaving_date(emp)
    if joining_date and joining_date > period_end:
        return False
    if leaving_date and leaving_date < period_start:
        return False
    return True


def _employee_active_period(emp, period_start, period_end):
    if not _employee_overlaps_period(emp, period_start, period_end):
        return None
    start = period_start
    end = period_end
    joining_date = _employee_joining_date(emp)
    leaving_date = _employee_leaving_date(emp)
    if joining_date and joining_date > start:
        start = joining_date
    if leaving_date and leaving_date < end:
        end = leaving_date
    return start, end


def _records_within_employment(records, emp, period_start=None, period_end=None):
    if period_start is None or period_end is None:
        dates = [r.get("date") for r in records if r.get("date")]
        period_start = min(dates) if dates else "0001-01-01"
        period_end = max(dates) if dates else "9999-12-31"
    active_period = _employee_active_period(emp, period_start, period_end)
    if not active_period:
        return []
    start, end = active_period
    return [r for r in records if start <= str(r.get("date", "")) <= end]


def _time_to_datetime(time_str):
    return datetime.strptime(time_str, "%H:%M")


def _work_date_for_shift(shift_name=None, punch_time=None, punch_date=None):
    """
    Returns the attendance work date for a punch.
    Overnight shift punches after midnight and before noon belong to
    the previous work date, preventing duplicate check-ins across dates.
    """
    base_date = _as_date_string(punch_date)
    today = date.fromisoformat(base_date) if base_date else _trusted_now().date()
    punch_time = (punch_time or _now_time())[:5]
    try:
        from shift_model import SHIFTS
        shift = SHIFTS.get(shift_name) if shift_name else None
        punch_dt = datetime.strptime(punch_time, "%H:%M")
    except Exception:
        return today.isoformat()

    if shift and shift.get("overnight"):
        noon_dt = datetime.strptime("12:00", "%H:%M")
        if punch_dt < noon_dt:
            return (today - timedelta(days=1)).isoformat()
    return today.isoformat()

def get_holiday(query_date=None):
    """
    Checks the holidays collection for a holiday on query_date.

    Expected MongoDB collection:
        employee_attendance.holidays

    Supported date fields:
        {"date": "YYYY-MM-DD"}
        {"holiday_date": "YYYY-MM-DD"}
        {"day": "YYYY-MM-DD"}
    """
    query_date = query_date or _today()
    return holidays_col.find_one({
        "$and": [
            {"$or": [
                {"date": query_date},
                {"holiday_date": query_date},
                {"day": query_date},
            ]},
            {"active": {"$ne": False}},
            {"deleted": {"$ne": True}},
        ]
    })

def is_holiday(query_date=None):
    """Returns True if query_date is marked as a holiday in MongoDB."""
    return get_holiday(query_date) is not None

def _holiday_block_message(query_date=None):
    query_date = query_date or _today()
    holiday = get_holiday(query_date) or {}
    holiday_name = holiday.get("name") or holiday.get("title") or "Holiday"
    return f"Attendance cannot be marked on {query_date}. It is a holiday: {holiday_name}."

def get_approved_leave_for_date(emp_id, query_date=None):
    query_date = query_date or _today()
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None
    return leave_requests_col.find_one({
        "emp_id": emp_id,
        "status": {"$in": ["Approved", "Revert Requested"]},
        "$or": [
            {"working_dates": query_date},
            {"from_date": {"$lte": query_date}, "to_date": {"$gte": query_date}},
        ],
    })

def _approved_leave_block_message(emp, query_date=None):
    query_date = query_date or _today()
    leave = get_approved_leave_for_date(emp["emp_id"], query_date)
    if not leave:
        return None
    leave_type = leave.get("leave_type", "leave")
    from_date = leave.get("from_date", query_date)
    to_date = leave.get("to_date", query_date)
    return (
        f"Attendance cannot be marked for {emp.get('name', 'this employee')} on {query_date}. "
        f"Approved {leave_type} already exists from {from_date} to {to_date}. "
        "Revert or cancel the leave before marking attendance."
    )

def is_missed_checkout(record, now=None):
    if not record or not record.get("arrival_time") or record.get("checkout_time"):
        return False
    if record.get("status") not in ("Present", "Late"):
        return False
    record_date = record.get("date") or _today()
    if now is None:
        now = _trusted_now()
    try:
        rec_day = date.fromisoformat(str(record_date))
    except (TypeError, ValueError):
        rec_day = now.date()
    if rec_day < now.date():
        return True
    if rec_day > now.date():
        return False
    try:
        from shift_model import get_employee_shift, SHIFTS, GRACE_MINUTES
        shift_name = record.get("shift")
        if not shift_name or shift_name == "---":
            shift_name = get_employee_shift(record.get("emp_id"))
        shift = SHIFTS.get(shift_name) if shift_name else None
    except Exception:
        shift = None
    end_time = shift.get("end") if shift else "23:59"
    try:
        end_dt = datetime.combine(rec_day, datetime.strptime(end_time[:5], "%H:%M").time())
        if shift and shift.get("overnight"):
            start_dt = datetime.combine(rec_day, datetime.strptime(shift["start"][:5], "%H:%M").time())
            if end_dt <= start_dt:
                from datetime import timedelta
                end_dt += timedelta(days=1)
        from datetime import timedelta
        end_dt += timedelta(minutes=GRACE_MINUTES if shift else 0)
    except Exception:
        end_dt = datetime.combine(rec_day, datetime.max.time())
    return now >= end_dt

def get_approved_leave_dates_for_month(emp_id, year_month):
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return set()
    dates = set()
    docs = leave_requests_col.find({
        "emp_id": emp_id,
        "status": {"$in": ["Approved", "Revert Requested"]},
        "$or": [
            {"from_date": {"$regex": f"^{year_month}"}},
            {"to_date": {"$regex": f"^{year_month}"}},
            {"working_dates": {"$elemMatch": {"$regex": f"^{year_month}"}}},
        ],
    })
    for doc in docs:
        working_dates = list(doc.get("working_dates") or [])
        if working_dates:
            dates.update(str(d) for d in working_dates if str(d).startswith(year_month))
            continue
        try:
            current = date.fromisoformat(doc.get("from_date"))
            end = date.fromisoformat(doc.get("to_date"))
        except (TypeError, ValueError):
            continue
        while current <= end:
            current_str = current.isoformat()
            if current_str.startswith(year_month):
                dates.add(current_str)
            current = current.fromordinal(current.toordinal() + 1)
    return dates

# ------------------------------------------------------------------------------------------------------------------------------------------
# STATUS CALCULATION
# ------------------------------------------------------------------------------------------------------------------------------------------
def calculate_status(arrival_time):
    """Auto-decides attendance status based on arrival time."""
    arrival_dt = _time_to_datetime(arrival_time)
    late_dt    = _time_to_datetime(LATE_LIMIT)
    halfday_dt = _time_to_datetime(HALFDAY_LIMIT)
    absent_dt  = _time_to_datetime("14:00")

    if arrival_dt <= late_dt:
        return "Present"
    elif arrival_dt <= halfday_dt:
        return "Late"
    elif arrival_dt <= absent_dt:
        return "Half-Day"
    return "Absent"

# ------------------------------------------------------------------------------------------------------------------------------------------
# LATE MINUTES CALCULATION
# ------------------------------------------------------------------------------------------------------------------------------------------
def calculate_late_minutes(arrival_time):
    """Returns raw late minutes as an integer; display code converts to hours."""
    arrival_dt = _time_to_datetime(arrival_time)
    office_dt  = _time_to_datetime(OFFICE_START)
    delta      = arrival_dt - office_dt
    minutes    = int(delta.total_seconds() // 60)
    return max(minutes, 0)

# ------------------------------------------------------------------------------------------------------------------------------------------
# MARK ARRIVAL (CHECK-IN)  --- shift-aware
# ------------------------------------------------------------------------------------------------------------------------------------------
def mark_arrival(emp_id, arrival_time=None, manual_override=False, query_date=None):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return False, err

    if arrival_time and not manual_override:
        return False, "Manual attendance time requires admin override."
    arrival_time = arrival_time or _now_time()

    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"Employee ID {emp_id} not found!"

    if emp.get("status") == "Inactive":
        return False, "Employee account is inactive!"

    # ------ Use shift-aware status if shift is assigned ---------------------------------------------------------------------------------
    try:
        from shift_model import get_employee_shift, SHIFTS, GRACE_MINUTES
        shift_name = get_employee_shift(emp_id)
        _shift_model_available = True
    except ImportError:
        shift_name = None
        SHIFTS = {}
        GRACE_MINUTES = 0
        _shift_model_available = False

    today = _as_date_string(query_date) if query_date else _work_date_for_shift(shift_name, arrival_time)
    if not today:
        return False, "Invalid attendance date!"

    # ------ Holiday / approved-leave checks must come first so the employee
    #        always gets the correct message regardless of their shift window.
    if is_holiday(today):
        return False, _holiday_block_message(today)

    leave_block = _approved_leave_block_message(emp, today)
    if leave_block:
        return False, leave_block

    # ------ Delegate status + late-minutes to the single source of truth -------
    arrival_metrics = None
    if _shift_model_available and shift_name:
        try:
            from shift_model import calculate_arrival_status
            arrival_metrics = calculate_arrival_status(emp_id, arrival_time)
        except Exception:
            arrival_metrics = None

    if arrival_metrics:
        status       = arrival_metrics["status"]
        late_minutes = arrival_metrics["late_minutes"]
        shift_name   = arrival_metrics["shift_name"]
    else:
        # shift_model unavailable or parse error — fall back to legacy helpers
        status       = calculate_status(arrival_time)
        late_minutes = calculate_late_minutes(arrival_time)
        shift_name   = None

    # ------ Block arrival outside shift check-in window ------------------------------------------------------------------------------------------------
    if shift_name and shift_name in SHIFTS:
        shift_info  = SHIFTS[shift_name]
        is_overnight = shift_info.get("overnight", False)

        try:
            arr_dt   = datetime.strptime(arrival_time[:5], "%H:%M")
            start_dt = datetime.strptime(shift_info["start"], "%H:%M")
            end_dt   = datetime.strptime(shift_info["end"],   "%H:%M")

            # Allow check-in up to GRACE_MINUTES before shift starts
            window_open = start_dt - timedelta(minutes=GRACE_MINUTES)
            latest_checkin = start_dt + timedelta(minutes=MAX_CHECKIN_DELAY_MINUTES)

            if is_overnight:
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                # Only bump arr_dt if it falls before the window_open.
                # Bumping early-but-valid arrivals (within grace before midnight)
                # incorrectly made them appear 24 hours late.
                if arr_dt < window_open:
                    arr_dt += timedelta(days=1)

            # Valid check-in is around shift start, not the whole shift duration.
            in_window = window_open <= arr_dt <= latest_checkin
            if not in_window:
                if arr_dt > latest_checkin:
                    return False, (
                        f"Check-in window is closed. Please contact admin.\n"
                        f"Your {shift_name} shift check-in window closed at "
                        f"{latest_checkin.strftime('%I:%M %p')}."
                    )
                return False, (
                    f"Check-in not allowed for this shift right now.\n"
                    f"You are assigned to the {shift_name} shift, so attendance can only be marked during its check-in window.\n"
                    f"Your shift ({shift_name}) runs "
                    f"{shift_info['start']} --- {shift_info['end']}.\n"
                    f"Check-in window opens at "
                    f"{window_open.strftime('%I:%M %p')} and closes at "
                    f"{latest_checkin.strftime('%I:%M %p')}."
                )
        except ValueError:
            pass   # If time parsing fails, skip the block check silently

    # ------ Do NOT save a record when status is Absent — it is contradictory
    #        to have an arrival_time on an Absent record, and breaks the salary
    #        engine which treats any record with arrival_time as a worked day.
    if status == "Absent":
        return False, (
            f"Arrival rejected for {emp['name']}: arrived too late "
            f"({arrival_time}). Status would be Absent. "
            f"Use 'Mark Absent' to record this day instead."
        )

    existing = attendance_col.find_one({"emp_id": emp_id, "date": today, "deleted": {"$ne": True}})
    if existing:
        existing_arrival = existing.get("arrival_time")
        if existing_arrival:
            return False, (
                f"{emp['name']} already checked in at "
                f"{existing_arrival}"
            )
        if existing.get("status") == "Absent":
            attendance_col.update_one(
                {"emp_id": emp_id, "date": today, "deleted": {"$ne": True}},
                {"$set": {
                    "name":                  emp["name"],
                    "department":            emp.get("department", "N/A"),
                    "status":                status,
                    "arrival_time":          arrival_time,
                    "checkout_time":         None,
                    "late_minutes":          late_minutes,
                    "hours_worked":          None,
                    "overtime_hours":        0,
                    "shift":                 shift_name or "---",
                    "marked_at":             _now_stamp(),
                    "corrected_from_absent": True,
                }}
            )

            shift_label = f" | Shift: {shift_name}" if shift_name else ""
            return True, (
                f"--- Arrival marked for {emp['name']} | "
                f"Status: {status} | "
                f"Late: {late_minutes} min{shift_label}"
            )
        existing_status = existing.get("status") or "attendance"
        return False, (
            f"Attendance already exists for {emp['name']} on {today}: "
            f"{existing_status}."
        )

    attendance_col.insert_one({
        "emp_id":         emp_id,
        "name":           emp["name"],
        "department":     emp.get("department", "N/A"),
        "date":           today,
        "status":         status,
        "arrival_time":   arrival_time,
        "checkout_time":  None,
        "late_minutes":   late_minutes,
        "hours_worked":   None,
        "overtime_hours": 0,
        "shift":          shift_name or "---",
        "marked_at":      _now_stamp(),
    })

    shift_label = f" | Shift: {shift_name}" if shift_name else ""
    return True, (
        f"--- Arrival marked for {emp['name']} | "
        f"Status: {status} | "
        f"Late: {late_minutes} min{shift_label}"
    )

# ------------------------------------------------------------------------------------------------------------------------------------------
# MARK CHECKOUT --- shift-aware OT calculation
# ------------------------------------------------------------------------------------------------------------------------------------------
def mark_checkout(emp_id, checkout_time=None, manual_override=False, query_date=None):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return False, err

    if checkout_time and not manual_override:
        return False, "Manual checkout time requires admin override."
    checkout_time = checkout_time or _now_time()

    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"Employee ID {emp_id} not found!"

    try:
        from shift_model import get_employee_shift
        checkout_shift_name = get_employee_shift(emp_id)
    except Exception:
        checkout_shift_name = None

    today = _as_date_string(query_date) if query_date else _work_date_for_shift(checkout_shift_name, checkout_time)
    if not today:
        return False, "Invalid attendance date!"
    if is_holiday(today):
        return False, _holiday_block_message(today)

    leave_block = _approved_leave_block_message(emp, today)
    if leave_block:
        return False, leave_block

    record = attendance_col.find_one({"emp_id": emp_id, "date": today, "deleted": {"$ne": True}})
    if not record:
        return False, "Arrival not marked yet!"

    if record.get("checkout_time"):
        return False, f"Already checked out at {record['checkout_time']}"

    arrival_str = record.get("arrival_time")
    if not arrival_str:
        return False, "Arrival not marked yet!"

    # ------ Hours worked (handle overnight checkout for Night shift) ---------------------------------------
    fmt = "%H:%M"
    try:
        arr_dt  = datetime.strptime(arrival_str[:5], fmt)
        chk_dt  = datetime.strptime(checkout_time[:5], fmt)
    except ValueError:
        return False, "Invalid time format in records!"

    if chk_dt < arr_dt:
        from datetime import timedelta
        chk_dt += timedelta(days=1)          # Night shift: checkout next morning

    hours_worked = round((chk_dt - arr_dt).total_seconds() / 3600, 2)
    if hours_worked < 0:
        return False, "Checkout cannot be before arrival!"

    # ------ Shift-aware overtime ------------------------------------------------------------------------------------------------------------------------------------------------------
    overtime_hours = 0.0
    metrics = None
    try:
        from shift_model import calculate_shift_metrics, SHIFTS, get_employee_shift
        metrics = calculate_shift_metrics(emp_id, arrival_str, checkout_time)
        if metrics:
            overtime_hours = metrics["overtime_hours"]
    except ImportError:
        if hours_worked > OVERTIME_LIMIT:
            overtime_hours = round(hours_worked - OVERTIME_LIMIT, 2)

    # ------ Recalculate status based on actual hours worked ---------------------------------------------------------------------
    try:
        shift_name  = get_employee_shift(emp_id) or emp.get("shift")
        shift_hours = SHIFTS[shift_name]["hours"] if shift_name in SHIFTS else FULLDAY_HOURS
    except Exception:
        shift_hours = FULLDAY_HOURS

    metrics_status = None
    if metrics:
        metrics_status = metrics.get("status")

    if metrics_status in ("Absent", "Half-Day"):
        final_status = metrics_status
    elif hours_worked < shift_hours * 0.25:
        final_status = "Absent"
    elif hours_worked < shift_hours * 0.5:
        final_status = "Half-Day"
    else:
        # Keep existing status (Present/Late) set at arrival
        final_status = record.get("status", "Present")

    attendance_col.update_one(
        {"emp_id": emp_id, "date": today, "deleted": {"$ne": True}},
        {"$set": {
            "checkout_time":  checkout_time,
            "hours_worked":   hours_worked,
            "overtime_hours": overtime_hours,
            "status":         final_status,
        }}
    )

    return True, (
        f"--- Checkout marked for {emp['name']} | "
        f"Status: {final_status} | "
        f"Hours Worked: {hours_worked}h | "
        f"Overtime: {overtime_hours}h"
    )

# ------------------------------------------------------------------------------------------------------------------------------------------
# MARK ABSENT
# ------------------------------------------------------------------------------------------------------------------------------------------
def mark_absent(emp_id, query_date=None):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return False, err

    emp   = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, "Employee not found!"

    try:
        from shift_model import get_employee_shift
        shift_name = get_employee_shift(emp_id)
    except Exception:
        shift_name = None

    today = _as_date_string(query_date) if query_date else _work_date_for_shift(shift_name)
    if not today:
        return False, "Invalid attendance date!"

    if is_holiday(today):
        return False, _holiday_block_message(today)

    leave_block = _approved_leave_block_message(emp, today)
    if leave_block:
        return False, leave_block

    existing = attendance_col.find_one({"emp_id": emp_id, "date": today, "deleted": {"$ne": True}})
    if existing:
        return False, "Attendance already exists for today!"

    attendance_col.insert_one({
        "emp_id":        emp_id,
        "name":          emp["name"],
        "department":    emp.get("department", "N/A"),
        "date":          today,
        "status":        "Absent",
        "arrival_time":  None,
        "checkout_time": None,
        "late_minutes":  0,
        "hours_worked":  0,
        "overtime_hours": 0,
        "shift":         shift_name or "---",
        "marked_at":     _now_stamp()
    })

    return True, f"Absent marked for {emp['name']} on {today}."

# ------------------------------------------------------------------------------------------------------------------------------------------
# AUTO MARK ABSENT (shift-aware end-of-shift bulk action)
# ------------------------------------------------------------------------------------------------------------------------------------------
def _completed_shift_work_date(shift_name, now=None):
    """
    Returns the work date for the most recently completed occurrence of a shift.
    Night shift ending after midnight is stored against the previous work date.
    """
    now = now or _trusted_now()
    try:
        from shift_model import SHIFTS
        shift = SHIFTS.get(shift_name)
    except Exception:
        shift = None
    if not shift:
        return None

    end_time = datetime.strptime(shift["end"][:5], "%H:%M").time()
    end_date = now.date()
    end_dt = datetime.combine(end_date, end_time)
    if now < end_dt:
        end_date = end_date - timedelta(days=1)
        end_dt = datetime.combine(end_date, end_time)

    if shift.get("overnight"):
        work_date = end_date - timedelta(days=1)
    else:
        work_date = end_date

    return work_date.isoformat(), end_dt


def auto_mark_absent_for_today(shift_name=None):
    """
    Marks absent only for employees whose own shift has already ended.
    If shift_name is supplied, only that shift is processed. Otherwise all
    shifts are checked, but each employee is still evaluated against their
    assigned shift and completed work date.
    """
    try:
        from shift_model import get_employee_shift, SHIFTS
    except Exception:
        return False, "Shift module not available. Auto absent was not run."

    now = _trusted_now()
    employees = employees_col.find({"role": "employee", "deleted": {"$ne": True}})
    absent_marked = []

    if shift_name and shift_name not in SHIFTS:
        return False, f"Invalid shift: {shift_name}"

    for emp in employees:
        eid = emp["emp_id"]
        emp_shift = get_employee_shift(eid) or emp.get("shift")
        if emp_shift not in SHIFTS:
            continue
        if shift_name and emp_shift != shift_name:
            continue

        completed = _completed_shift_work_date(emp_shift, now)
        if not completed:
            continue
        work_date, shift_end_dt = completed
        if now < shift_end_dt:
            continue
        if not _employee_overlaps_period(emp, work_date, work_date):
            continue
        if is_holiday(work_date):
            continue
        if get_approved_leave_for_date(eid, work_date):
            continue

        existing = attendance_col.find_one({
            "emp_id": eid,
            "date": work_date,
        })
        if existing:
            if existing.get("deleted"):
                attendance_col.update_one(
                    {"emp_id": eid, "date": work_date},
                    {"$set": {
                        "emp_id":         eid,
                        "name":           emp["name"],
                        "department":     emp.get("department", "N/A"),
                        "date":           work_date,
                        "status":         "Absent",
                        "arrival_time":   None,
                        "checkout_time":  None,
                        "late_minutes":   0,
                        "hours_worked":   0,
                        "overtime_hours": 0,
                        "shift":          emp_shift,
                        "marked_at":      _now_stamp(),
                        "marked_by":      "system",
                        "auto_marked":    True,
                        "auto_reason":    "No check-in recorded after shift end",
                    },
                    "$unset": {
                        "deleted": "",
                        "deleted_at": "",
                        "deleted_by": "",
                    }}
                )
                absent_marked.append(f"{emp['name']} ({emp_shift}, {work_date})")
            continue

        try:
            attendance_col.insert_one({
                "emp_id":         eid,
                "name":           emp["name"],
                "department":     emp.get("department", "N/A"),
                "date":           work_date,
                "status":         "Absent",
                "arrival_time":   None,
                "checkout_time":  None,
                "late_minutes":   0,
                "hours_worked":   0,
                "overtime_hours": 0,
                "shift":          emp_shift,
                "marked_at":      _now_stamp(),
                "marked_by":      "system",
                "auto_marked":    True,
                "auto_reason":    "No check-in recorded after shift end",
            })
        except DuplicateKeyError:
            continue
        absent_marked.append(f"{emp['name']} ({emp_shift}, {work_date})")

    return True, absent_marked

# ------------------------------------------------------------------------------------------------------------------------------------------
# GET TODAY'S ATTENDANCE FOR ONE EMPLOYEE
# ------------------------------------------------------------------------------------------------------------------------------------------
def get_today_record(emp_id):
    """Returns today's attendance record for a specific employee (or None)."""
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return None

    try:
        from shift_model import get_employee_shift
        shift_name = get_employee_shift(emp_id)
    except Exception:
        shift_name = None
    work_date = _work_date_for_shift(shift_name)

    return attendance_col.find_one(
        {"emp_id": emp_id, "date": work_date, "deleted": {"$ne": True}},
        {"_id": 0}
    )

# ------------------------------------------------------------------------------------------------------------------------------------------
# GET ATTENDANCE BY DATE (admin view)
# ------------------------------------------------------------------------------------------------------------------------------------------
def get_attendance_by_date(query_date=None):
    query_date = query_date or _today()
    active_emp_ids = [
        emp["emp_id"] for emp in employees_col.find(
            {"role": "employee", "deleted": {"$ne": True}},
            {"emp_id": 1}
        )
    ]
    leave_emp_ids = {
        doc["emp_id"] for doc in leave_requests_col.find(
            {
                "emp_id": {"$in": active_emp_ids},
                "status": {"$in": ["Approved", "Revert Requested"]},
                "$or": [
                    {"working_dates": query_date},
                    {"from_date": {"$lte": query_date}, "to_date": {"$gte": query_date}},
                ],
            },
            {"emp_id": 1}
        )
    }
    visible_emp_ids = [emp_id for emp_id in active_emp_ids if emp_id not in leave_emp_ids]
    return list(
        attendance_col.find({"date": query_date, "emp_id": {"$in": visible_emp_ids}, "deleted": {"$ne": True}}, {"_id": 0})
    )

# ------------------------------------------------------------------------------------------------------------------------------------------
# GET EMPLOYEE HISTORY
# ------------------------------------------------------------------------------------------------------------------------------------------
def get_attendance_by_employee(emp_id):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return []
    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}, {"password": 0})
    if not emp:
        return []
    records = list(
        attendance_col.find(
            {"emp_id": emp_id, "deleted": {"$ne": True}},
            {"_id": 0}
        ).sort("date", -1)
    )
    return _records_within_employment(records, emp)

# ------------------------------------------------------------------------------------------------------------------------------------------
# MONTHLY REPORT
# ------------------------------------------------------------------------------------------------------------------------------------------
def get_monthly_report(emp_id, month, year):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return {
            "emp_id": emp_id,
            "month": month,
            "year": year,
            "total_days": 0,
            "present": 0,
            "late": 0,
            "half_day": 0,
            "absent": 0,
            "attendance_percentage": 0,
            "error": err,
        }

    prefix  = f"{year}-{str(month).zfill(2)}"
    month_start = f"{prefix}-01"
    month_end = f"{prefix}-{calendar.monthrange(int(year), int(month))[1]:02d}"
    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}, {"password": 0})
    if not emp:
        records = []
    else:
        active_period = _employee_active_period(emp, month_start, month_end)
        if active_period:
            active_start, active_end = active_period
            records = list(
                attendance_col.find({
                    "emp_id": emp_id,
                    "date":   {"$gte": active_start, "$lte": active_end},
                    "deleted": {"$ne": True}
                }, {"_id": 0})
            )
        else:
            records = []
    leave_dates = get_approved_leave_dates_for_month(emp_id, prefix)
    records = [r for r in records if r.get("date") not in leave_dates]

    total_present = sum(1 for r in records if r.get("status") == "Present")
    total_late    = sum(1 for r in records if r.get("status") == "Late")
    total_halfday = sum(1 for r in records if r.get("status") == "Half-Day")
    total_absent  = sum(1 for r in records if r.get("status") == "Absent")
    total_days    = len(records)

    working_credit = total_present + total_late + (total_halfday * 0.5)
    attendance_percent = round(
        (working_credit / total_days) * 100, 2
    ) if total_days else 0

    return {
        "emp_id":                emp_id,
        "month":                 month,
        "year":                  year,
        "total_days":            total_days,
        "present":               total_present,
        "late":                  total_late,
        "half_day":              total_halfday,
        "absent":                total_absent,
        "attendance_percentage": attendance_percent
    }


def get_monthly_attendance_report(month, year):
    """
    Returns one monthly attendance summary row per active employee.
    Month is 1-12 and year is a 4-digit integer/string.
    """
    try:
        month = int(month)
        year = int(year)
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        return []

    prefix = f"{year}-{month:02d}"
    month_days = calendar.monthrange(year, month)[1]
    month_start = f"{prefix}-01"
    month_end = f"{prefix}-{month_days:02d}"
    employees = [
        emp for emp in employees_col.find({"role": "employee", "deleted": {"$ne": True}}, {"_id": 0, "password": 0}).sort("emp_id", 1)
        if _employee_overlaps_period(emp, month_start, month_end)
    ]

    records = list(attendance_col.find(
        {"date": {"$gte": month_start, "$lte": month_end}, "deleted": {"$ne": True}},
        {"_id": 0}
    ))

    by_emp = {}
    for record in records:
        by_emp.setdefault(record.get("emp_id"), []).append(record)

    report = []
    for emp in employees:
        emp_id = emp.get("emp_id")
        active_period = _employee_active_period(emp, month_start, month_end)
        if not active_period:
            continue
        active_start, active_end = active_period
        leave_dates = get_approved_leave_dates_for_month(emp_id, prefix)
        emp_records = [
            r for r in by_emp.get(emp_id, [])
            if active_start <= str(r.get("date", "")) <= active_end
            and r.get("date") not in leave_dates
        ]

        missed_checkout = sum(1 for r in emp_records if is_missed_checkout(r))
        present = sum(1 for r in emp_records if r.get("status") == "Present") - sum(
            1 for r in emp_records
            if r.get("status") == "Present" and is_missed_checkout(r)
        )
        late = sum(1 for r in emp_records if r.get("status") == "Late") - sum(
            1 for r in emp_records
            if r.get("status") == "Late" and is_missed_checkout(r)
        )
        half_day = sum(1 for r in emp_records if r.get("status") == "Half-Day")
        absent = sum(1 for r in emp_records if r.get("status") == "Absent")
        recorded_days = len(emp_records)
        working_credit = present + late + (half_day * 0.5)
        attendance_percentage = round((working_credit / recorded_days) * 100, 2) if recorded_days else 0

        total_late_minutes = sum(int(r.get("late_minutes") or 0) for r in emp_records)

        report.append({
            "emp_id": emp_id,
            "name": emp.get("name", "N/A"),
            "department": emp.get("department", "N/A"),
            "month": prefix,
            "month_days": month_days,
            "recorded_days": recorded_days,
            "present": present,
            "late": late,
            "half_day": half_day,
            "absent": absent,
            "missed_checkout": missed_checkout,
            "total_late_minutes": total_late_minutes,
            "total_late_hours": round(total_late_minutes / 60, 2),
            "total_hours_worked": round(sum(float(r.get("hours_worked") or 0) for r in emp_records), 2),
            "total_overtime_hours": round(sum(float(r.get("overtime_hours") or 0) for r in emp_records), 2),
            "attendance_percentage": attendance_percentage,
        })

    return report


def get_employee_monthly_attendance_percentage(emp_id, month=None, year=None):
    """
    Returns attendance percentage for employee list display.
    Uses full calendar month days as denominator, separate from Monthly Attendance report.
    """
    try:
        emp_id = int(emp_id)
        today = _trusted_now()
        month = int(month or today.month)
        year = int(year or today.year)
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        return 0

    prefix = f"{year}-{month:02d}"
    month_days = calendar.monthrange(year, month)[1]
    month_start = f"{prefix}-01"
    month_end = f"{prefix}-{month_days:02d}"
    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}, {"password": 0})
    active_period = _employee_active_period(emp, month_start, month_end) if emp else None
    if not active_period:
        return 0
    active_start, active_end = active_period
    active_days = (date.fromisoformat(active_end) - date.fromisoformat(active_start)).days + 1
    records = list(attendance_col.find(
        {"emp_id": emp_id, "date": {"$gte": active_start, "$lte": active_end}, "deleted": {"$ne": True}},
        {"_id": 0}
    ))
    leave_dates = get_approved_leave_dates_for_month(emp_id, prefix)
    records = [r for r in records if r.get("date") not in leave_dates]

    present = sum(
        1 for r in records
        if r.get("status") == "Present" and not is_missed_checkout(r)
    )
    late = sum(
        1 for r in records
        if r.get("status") == "Late" and not is_missed_checkout(r)
    )
    half_day = sum(1 for r in records if r.get("status") == "Half-Day")
    working_credit = present + late + (half_day * 0.5)
    return round((working_credit / active_days) * 100, 2) if active_days else 0


# ------------------------------------------------------------------------------------------------------------------------------------------
# MARK ALL PRESENT (start-of-day bulk action)
# ------------------------------------------------------------------------------------------------------------------------------------------
def mark_all_present_today():
    """
    Marks active employees as Present for today --- but ONLY if their
    assigned shift is currently active (within the shift window).
    Employees on a different shift are skipped and reported separately.
    Returns (True, marked_names, skipped_names, wrong_shift_names).
    """
    from datetime import timedelta as _td
    try:
        from shift_model import get_employee_shift, SHIFTS, GRACE_MINUTES
        shift_aware = True
    except ImportError:
        shift_aware = False

    today     = _today()
    now       = _now_time()
    now_dt    = datetime.strptime(now, "%H:%M")
    employees = list(employees_col.find(
        {"role": "employee", "deleted": {"$ne": True}}
    ))

    marked      = []
    skipped     = []
    wrong_shift = []

    for emp in employees:
        eid = emp["emp_id"]
        if shift_aware:
            shift_name = get_employee_shift(eid) or emp.get("shift")
        else:
            shift_name = emp.get("shift") or None
        work_date = _work_date_for_shift(shift_name, now)

        if is_holiday(work_date):
            wrong_shift.append(f"{emp['name']} ({_holiday_block_message(work_date)})")
            continue

        # Already has a record for this shift work date --- skip
        if attendance_col.find_one({"emp_id": eid, "date": work_date, "deleted": {"$ne": True}}):
            skipped.append(emp["name"])
            continue

        if get_approved_leave_for_date(eid, work_date):
            wrong_shift.append(f"{emp['name']} (approved leave)")
            continue

        # ------ Shift check-in window check ---------------------------------------------------------------------------------------------------------------------------------------
        if shift_aware:
            if shift_name and shift_name in SHIFTS:
                s         = SHIFTS[shift_name]
                start_dt  = datetime.strptime(s["start"], "%H:%M")
                end_dt    = datetime.strptime(s["end"],   "%H:%M")
                window_open = start_dt - _td(minutes=GRACE_MINUTES)
                latest_checkin = start_dt + _td(minutes=MAX_CHECKIN_DELAY_MINUTES)

                if s.get("overnight", False):
                    if end_dt <= start_dt:
                        end_dt += _td(days=1)
                    check_dt = now_dt + _td(days=1) if now_dt < start_dt else now_dt
                else:
                    check_dt = now_dt

                in_window = window_open <= check_dt <= latest_checkin

                if not in_window:
                    wrong_shift.append(f"{emp['name']} ({shift_name})")
                    continue
            else:
                shift_name = None

        # ------ Mark present ------------------------------------------------------------------------------------------------------------------------------------------------------------------
        attendance_col.insert_one({
            "emp_id":         eid,
            "name":           emp["name"],
            "department":     emp.get("department", "N/A"),
            "date":           work_date,
            "status":         "Present",
            "arrival_time":   now,
            "checkout_time":  None,
            "late_minutes":   0,
            "hours_worked":   None,
            "overtime_hours": 0,
            "shift":          shift_name or emp.get("shift", "---"),
            "marked_at":      _now_stamp(),
        })
        marked.append(emp["name"])

    return True, marked, skipped, wrong_shift

# ------------------------------------------------------------------------------------------------------------------------------------------
# DELETE ATTENDANCE (admin only)
# ------------------------------------------------------------------------------------------------------------------------------------------
def delete_attendance(emp_id, query_date=None, deleted_by=None):
    emp_id, err = _resolve_emp_id(emp_id)
    if err:
        return False, err
    query_date = query_date or _today()
    result = attendance_col.update_one(
        {"emp_id": emp_id, "date": query_date, "deleted": {"$ne": True}},
        {"$set": {
            "deleted": True,
            "deleted_at": _now_stamp(),
            "deleted_by": str(deleted_by or "admin"),
        }}
    )

    if result.modified_count:
        log_action(
            action       = "DELETE_ATTENDANCE",
            performed_by = str(deleted_by or "admin"),
            target       = str(emp_id),
            details      = f"Attendance record for {query_date} soft-deleted for Emp ID {emp_id} by {deleted_by or 'admin'}.",
        )
        return True, f"Attendance soft-deleted for Emp ID {emp_id}"
    return False, "No active attendance record found!"
