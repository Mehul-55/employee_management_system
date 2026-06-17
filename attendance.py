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

from app_time import trusted_now as _app_trusted_now
from db_config import client as _client, db as _db, employees_col
from audit_log import log_action


# ------------------------------------------------------------------------------------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------------------------------------------------------------------------------------
attendance_col = _db["attendance"]
holidays_col   = _db["holidays"]
leave_requests_col = _db["leave_requests"]
departments_col =_db["departments"]
auto_absence_state_col = _db["auto_absence_state"]
# Prevent duplicate attendance per employee per day
try:
    attendance_col.create_index(
        [("emp_id", 1), ("date", 1)],
        unique=True
    )
    auto_absence_state_col.create_index("shift", unique=True)
except Exception as e:
    print(f"[ATTENDANCE WARNING] Could not create attendance indexes: {e}")

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
    return _app_trusted_now(_client)


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


def _employee_inactive_on_date(emp, query_date):
    query_date = _as_date_string(query_date)
    if not query_date:
        return False
    for interval in emp.get("inactive_periods") or []:
        if not isinstance(interval, dict):
            continue
        inactive_from = _as_date_string(
            interval.get("from") or interval.get("start") or interval.get("deleted_at")
        )
        inactive_to = _as_date_string(
            interval.get("to") or interval.get("end") or interval.get("restored_at")
        )
        if inactive_from and inactive_to and inactive_from < query_date < inactive_to:
            return True
    return False


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


def employee_active_on_date(emp, query_date):
    """Return whether an employee belonged to the workforce on query_date."""
    query_date = _as_date_string(query_date)
    if not emp or not query_date:
        return False
    if emp.get("deleted") and not _employee_leaving_date(emp):
        return False
    return (
        _employee_overlaps_period(emp, query_date, query_date)
        and not _employee_inactive_on_date(emp, query_date)
    )


def employee_active_during_period(emp, period_start, period_end):
    """Return whether an employee was active for any date in the period."""
    if not emp:
        return False
    if emp.get("deleted") and not _employee_leaving_date(emp):
        return False
    active_period = _employee_active_period(emp, period_start, period_end)
    if not active_period:
        return False
    current = date.fromisoformat(active_period[0])
    end = date.fromisoformat(active_period[1])
    while current <= end:
        if not _employee_inactive_on_date(emp, current.isoformat()):
            return True
        current += timedelta(days=1)
    return False


def _records_within_employment(records, emp, period_start=None, period_end=None):
    if period_start is None or period_end is None:
        dates = [r.get("date") for r in records if r.get("date")]
        period_start = min(dates) if dates else "0001-01-01"
        period_end = max(dates) if dates else "9999-12-31"
    return [
        record
        for record in records
        if employee_active_on_date(emp, record.get("date"))
        and period_start <= str(record.get("date", "")) <= period_end
    ]


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


def _sunday_off_block_message(emp_id, query_date):
    try:
        from shift_model import is_sunday_off
        sunday_off = is_sunday_off(emp_id, query_date)
    except Exception:
        sunday_off = date.fromisoformat(query_date).weekday() == 6
    if sunday_off:
        return (
            f"Attendance cannot be marked on {query_date}. Sunday is a paid "
            "weekly holiday unless Sunday work is approved by admin."
        )
    return None


def leave_applies_to_date(leave, query_date):
    """
    Modern leave records are authoritative through working_dates.
    Only legacy records without that field may use the calendar date range.
    """
    if not leave:
        return False
    query_date = _as_date_string(query_date)
    if not query_date:
        return False
    if "working_dates" in leave:
        return query_date in {
            str(working_date)
            for working_date in (leave.get("working_dates") or [])
        }
    return (
        str(leave.get("from_date") or "") <= query_date
        <= str(leave.get("to_date") or "")
    )


def get_approved_leave_for_date(emp_id, query_date=None):
    query_date = query_date or _today()
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None
    base_query = {
        "emp_id": emp_id,
        "status": {"$in": ["Approved", "Revert Requested"]},
    }
    leave = leave_requests_col.find_one({
        **base_query,
        "working_dates": query_date,
    })
    if leave:
        return leave
    return leave_requests_col.find_one({
        **base_query,
        "working_dates": {"$exists": False},
        "from_date": {"$lte": query_date},
        "to_date": {"$gte": query_date},
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
    try:
        year, month = map(int, str(year_month).split("-"))
        month_start = f"{year:04d}-{month:02d}-01"
        month_end = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
    except (TypeError, ValueError):
        return set()
    docs = leave_requests_col.find({
        "emp_id": emp_id,
        "status": {"$in": ["Approved", "Revert Requested"]},
        "$or": [
            {"working_dates": {"$elemMatch": {"$gte": month_start, "$lte": month_end}}},
            {
                "working_dates": {"$exists": False},
                "from_date": {"$lte": month_end},
                "to_date": {"$gte": month_start},
            },
        ],
    })
    for doc in docs:
        if "working_dates" in doc:
            working_dates = list(doc.get("working_dates") or [])
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


def _eligible_attendance_dates(emp_id, emp, period_start, period_end, as_of_date=None):
    """
    Return elapsed working dates used as the attendance percentage denominator.

    Sundays, public holidays, approved leave, dates outside employment, and
    future dates are excluded. An approved Sunday-work date is included.
    """
    active_period = _employee_active_period(emp, period_start, period_end)
    if not active_period:
        return []

    active_start, active_end = active_period
    cutoff = _as_date_string(as_of_date) or _today()
    active_end = min(active_end, cutoff)
    if active_start > active_end:
        return []

    leave_dates = get_approved_leave_dates_for_month(
        emp_id,
        active_start[:7],
    )
    if active_start[:7] != active_end[:7]:
        leave_dates.update(
            get_approved_leave_dates_for_month(emp_id, active_end[:7])
        )

    try:
        from shift_model import (
            get_holidays_for_range,
            get_sunday_work_approval_dates_for_range,
        )
        holiday_dates = {
            str(item.get("_holiday_date"))
            for item in get_holidays_for_range(active_start, active_end)
            if item.get("_holiday_date")
        }
        sunday_work_dates = get_sunday_work_approval_dates_for_range(
            emp_id,
            active_start,
            active_end,
        )
    except Exception:
        holiday_dates = set()
        sunday_work_dates = set()
        current = date.fromisoformat(active_start)
        end = date.fromisoformat(active_end)
        while current <= end:
            current_str = current.isoformat()
            if is_holiday(current_str):
                holiday_dates.add(current_str)
            current += timedelta(days=1)

    eligible_dates = []
    current = date.fromisoformat(active_start)
    end = date.fromisoformat(active_end)
    while current <= end:
        current_str = current.isoformat()
        is_sunday_off = current.weekday() == 6 and current_str not in sunday_work_dates
        if (
            not is_sunday_off
            and current_str not in holiday_dates
            and current_str not in leave_dates
            and not _employee_inactive_on_date(emp, current_str)
        ):
            eligible_dates.append(current_str)
        current += timedelta(days=1)
    return eligible_dates


def _attendance_summary_for_period(emp_id, emp, records, period_start, period_end, as_of_date=None):
    """Calculate attendance counts and percentage using one system-wide rule."""
    eligible_dates = _eligible_attendance_dates(
        emp_id,
        emp,
        period_start,
        period_end,
        as_of_date=as_of_date,
    )
    eligible_set = set(eligible_dates)
    eligible_records = [
        record for record in records
        if str(record.get("date", "")) in eligible_set
    ]

    missed_checkout = sum(1 for record in eligible_records if is_missed_checkout(record))
    present = sum(
        1 for record in eligible_records
        if record.get("status") == "Present" and not is_missed_checkout(record)
    )
    late = sum(
        1 for record in eligible_records
        if record.get("status") == "Late" and not is_missed_checkout(record)
    )
    half_day = sum(1 for record in eligible_records if record.get("status") == "Half-Day")
    absent = sum(1 for record in eligible_records if record.get("status") == "Absent")
    recorded_dates = {
        str(record.get("date"))
        for record in eligible_records
        if record.get("date")
    }
    eligible_days = len(eligible_dates)
    not_marked = max(eligible_days - len(recorded_dates), 0)
    working_credit = present + late + (half_day * 0.5)
    attendance_percentage = round(
        (working_credit / eligible_days) * 100,
        2,
    ) if eligible_days else 0

    return {
        "eligible_days": eligible_days,
        "recorded_days": len(recorded_dates),
        "not_marked": not_marked,
        "present": present,
        "late": late,
        "half_day": half_day,
        "absent": absent,
        "missed_checkout": missed_checkout,
        "attendance_percentage": attendance_percentage,
        "records": eligible_records,
    }


def resolve_daily_report_status(attendance_record=None, approved_leave=False, paid_holiday=False):
    """Resolve the displayed daily status without exposing stale holiday records."""
    record = attendance_record or {}
    if paid_holiday:
        return "Paid Holiday", {}
    if approved_leave:
        return "Approved Leave", {}
    return record.get("status", "Not Marked"), record


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

    sunday_block = _sunday_off_block_message(emp_id, today)
    if sunday_block:
        return False, sunday_block

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

    sunday_block = _sunday_off_block_message(emp_id, today)
    if sunday_block:
        return False, sunday_block

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

    try:
        from shift_model import calculate_work_session_hours, MAX_WORK_SESSION_HOURS
        hours_worked = calculate_work_session_hours(arrival_str, checkout_time)
    except ImportError:
        if chk_dt < arr_dt:
            chk_dt += timedelta(days=1)
        hours_worked = round((chk_dt - arr_dt).total_seconds() / 3600, 2)
        MAX_WORK_SESSION_HOURS = 12

    if hours_worked is None or hours_worked > MAX_WORK_SESSION_HOURS:
        return False, (
            f"Checkout rejected: work duration must not exceed "
            f"{MAX_WORK_SESSION_HOURS} hours. Check the arrival and checkout times."
        )

    # ------ Shift-aware overtime ------------------------------------------------------------------------------------------------------------------------------------------------------
    overtime_hours = 0.0
    metrics = None
    try:
        from shift_model import calculate_shift_metrics, SHIFTS, get_employee_shift
        record_shift = record.get("shift")
        if record_shift not in SHIFTS:
            record_shift = get_employee_shift(emp_id, today)
        metrics = calculate_shift_metrics(
            emp_id,
            arrival_str,
            checkout_time,
            shift_name=record_shift,
            work_date=today,
        )
        if metrics:
            overtime_hours = metrics["overtime_hours"]
    except ImportError:
        if hours_worked > OVERTIME_LIMIT:
            overtime_hours = round(hours_worked - OVERTIME_LIMIT, 2)

    # ------ Recalculate status based on actual hours worked ---------------------------------------------------------------------
    try:
        shift_name = record.get("shift")
        if shift_name not in SHIFTS:
            shift_name = get_employee_shift(emp_id, today) or emp.get("shift")
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

    sunday_block = _sunday_off_block_message(emp_id, today)
    if sunday_block:
        return False, sunday_block

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


def _completed_shift_work_dates(shift_name, start_date, now=None):
    """Return every work date from start_date through the latest completed shift."""
    completed = _completed_shift_work_date(shift_name, now)
    if not completed:
        return []
    latest_work_date, _ = completed
    start_date = _as_date_string(start_date)
    if not start_date or start_date > latest_work_date:
        return []

    current = date.fromisoformat(start_date)
    end = date.fromisoformat(latest_work_date)
    work_dates = []
    while current <= end:
        work_dates.append(current.isoformat())
        current += timedelta(days=1)
    return work_dates


def _next_date(date_string):
    parsed = _as_date_string(date_string)
    if not parsed:
        return None
    return (date.fromisoformat(parsed) + timedelta(days=1)).isoformat()


def _initial_auto_absence_start(emp, latest_completed_work_date):
    """
    Establish a safe first checkpoint after upgrading from the old scheduler.
    Resume after the employee's latest active attendance record. Employees with
    no history start at the latest completed date to avoid inventing old data.
    """
    latest_record = attendance_col.find_one(
        {"emp_id": emp.get("emp_id"), "deleted": {"$ne": True}},
        {"date": 1},
        sort=[("date", -1)],
    )
    latest_record_date = _as_date_string((latest_record or {}).get("date"))
    if latest_record_date:
        return _next_date(latest_record_date)

    joining_date = _employee_joining_date(emp)
    if joining_date == latest_completed_work_date:
        return joining_date
    return latest_completed_work_date


def auto_mark_absent_for_today(shift_name=None):
    """
    Marks absent for every unprocessed, completed work date.

    Progress is stored per shift so startup catch-up covers multi-day downtime.
    Existing attendance, holidays, Sunday holidays, approved leave, and dates
    outside an employee's active employment period are always skipped.
    """
    try:
        from shift_model import get_employee_shift, SHIFTS
    except Exception:
        return False, "Shift module not available. Auto absent was not run."

    now = _trusted_now()
    employees = list(employees_col.find({"role": "employee", "deleted": {"$ne": True}}))
    absent_marked = []

    if shift_name and shift_name not in SHIFTS:
        return False, f"Invalid shift: {shift_name}"

    shifts_to_process = [shift_name] if shift_name else list(SHIFTS)
    for current_shift in shifts_to_process:
        completed = _completed_shift_work_date(current_shift, now)
        if not completed:
            continue
        latest_work_date, shift_end_dt = completed
        if now < shift_end_dt:
            continue

        state = auto_absence_state_col.find_one({"shift": current_shift}) or {}
        checkpoint_start = _next_date(state.get("last_processed_work_date"))

        for emp in employees:
            eid = emp["emp_id"]
            start_date = checkpoint_start or _initial_auto_absence_start(
                emp,
                latest_work_date,
            )
            for work_date in _completed_shift_work_dates(
                current_shift,
                start_date,
                now,
            ):
                emp_shift = get_employee_shift(eid, work_date) or emp.get("shift")
                if emp_shift != current_shift:
                    continue
                if not _employee_overlaps_period(emp, work_date, work_date):
                    continue
                if is_holiday(work_date):
                    continue
                if _sunday_off_block_message(eid, work_date):
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

        auto_absence_state_col.update_one(
            {"shift": current_shift},
            {"$set": {
                "shift": current_shift,
                "last_processed_work_date": latest_work_date,
                "updated_at": _now_stamp(),
            }},
            upsert=True,
        )

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
                    {
                        "working_dates": {"$exists": False},
                        "from_date": {"$lte": query_date},
                        "to_date": {"$gte": query_date},
                    },
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
    emp = employees_col.find_one({"emp_id": emp_id}, {"password": 0})
    if emp and not employee_active_during_period(emp, month_start, month_end):
        emp = None
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
    records = list(attendance_col.find({
        "emp_id": emp_id,
        "date": {"$gte": month_start, "$lte": month_end},
        "deleted": {"$ne": True},
    }, {"_id": 0})) if emp else []
    summary = _attendance_summary_for_period(
        emp_id,
        emp,
        records,
        month_start,
        month_end,
    ) if emp else {
        "eligible_days": 0, "recorded_days": 0, "not_marked": 0,
        "present": 0, "late": 0, "half_day": 0, "absent": 0,
        "missed_checkout": 0, "attendance_percentage": 0,
    }

    return {
        "emp_id":                emp_id,
        "month":                 month,
        "year":                  year,
        "total_days":            summary["eligible_days"],
        "eligible_days":         summary["eligible_days"],
        "recorded_days":         summary["recorded_days"],
        "not_marked":            summary["not_marked"],
        "present":               summary["present"],
        "late":                  summary["late"],
        "half_day":              summary["half_day"],
        "absent":                summary["absent"],
        "missed_checkout":       summary["missed_checkout"],
        "attendance_percentage": summary["attendance_percentage"],
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
        emp for emp in employees_col.find(
            {"role": "employee"},
            {"_id": 0, "password": 0},
        ).sort("emp_id", 1)
        if employee_active_during_period(emp, month_start, month_end)
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
        emp_records = [
            r for r in by_emp.get(emp_id, [])
            if active_start <= str(r.get("date", "")) <= active_end
        ]
        summary = _attendance_summary_for_period(
            emp_id,
            emp,
            emp_records,
            month_start,
            month_end,
        )
        eligible_records = summary["records"]

        total_late_minutes = sum(int(r.get("late_minutes") or 0) for r in eligible_records)

        report.append({
            "emp_id": emp_id,
            "name": emp.get("name", "N/A"),
            "department": emp.get("department", "N/A"),
            "month": prefix,
            "month_days": month_days,
            "eligible_days": summary["eligible_days"],
            "recorded_days": summary["recorded_days"],
            "not_marked": summary["not_marked"],
            "present": summary["present"],
            "late": summary["late"],
            "half_day": summary["half_day"],
            "absent": summary["absent"],
            "missed_checkout": summary["missed_checkout"],
            "total_late_minutes": total_late_minutes,
            "total_late_hours": round(total_late_minutes / 60, 2),
            "total_hours_worked": round(sum(float(r.get("hours_worked") or 0) for r in eligible_records), 2),
            "total_overtime_hours": round(sum(float(r.get("overtime_hours") or 0) for r in eligible_records), 2),
            "attendance_percentage": summary["attendance_percentage"],
        })

    return report


def get_employee_monthly_attendance_percentage(emp_id, month=None, year=None):
    """
    Returns attendance percentage for employee list display.
    Uses the same elapsed eligible-working-day rule as the monthly report.
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
    records = list(attendance_col.find(
        {"emp_id": emp_id, "date": {"$gte": active_start, "$lte": active_end}, "deleted": {"$ne": True}},
        {"_id": 0}
    ))
    summary = _attendance_summary_for_period(
        emp_id,
        emp,
        records,
        month_start,
        month_end,
    )
    return summary["attendance_percentage"]


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

        sunday_block = _sunday_off_block_message(eid, work_date)
        if sunday_block:
            wrong_shift.append(f"{emp['name']} (Sunday holiday)")
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

