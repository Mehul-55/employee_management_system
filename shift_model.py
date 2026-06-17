"""
------------------------------------------------------------------------------------------------------------------------------------------------
---   shift_model.py                             ---
---   Shift definitions, assignment & salary     ---
------------------------------------------------------------------------------------------------------------------------------------------------

3 Fixed Shifts:
    Morning  ---  09:00 --- 17:00  (8 hrs)
    Evening  ---  14:00 --- 22:00  (8 hrs)
    Night    ---  22:00 --- 06:00  (8 hrs, crosses midnight)

Salary Rules:
    Grace period  : 15 min --- no deduction within grace
    Late deduction: (late_min - grace) -- per_minute_rate
    Overtime      : eligible hours after the configured threshold -- hourly_rate -- 1.5
    Rate basis    : monthly salary / actual working days in the payroll period
"""

from datetime import datetime, timedelta, date
import calendar

from app_time import now_stamp as _app_now_stamp
from app_time import today_date as _app_today_date
from app_time import today_iso as _app_today_iso
from app_time import trusted_now as _app_trusted_now
from db_config import db as _db, employees_col
from payroll_math import calculate_payroll_amounts, calculate_prorated_salary
shift_assign_col = _db["shift_assignments"]
attendance_col   = _db["attendance"]
salary_col       =_db["salary"]
holidays_col     = _db["holidays"]
leave_requests_col = _db["leave_requests"]
salary_history_col = _db["salary_history"]
sunday_work_col = _db["sunday_work_approvals"]
try:
    sunday_work_col.create_index([("emp_id", 1), ("date", 1)], unique=True)
except Exception:
    pass

# ------------------------------------------------------------------------------------------------------------------------------------------
#  SHIFT DEFINITIONS  (fixed --- not in DB)
# ------------------------------------------------------------------------------------------------------------------------------------------
SHIFTS = {
    "Morning": {
        "start":     "09:00",
        "end":       "17:00",
        "hours":     8,
        "overnight": False,
        "label":     "Morning  (09:00 --- 17:00)",
    },
    "Evening": {
        "start":     "14:00",
        "end":       "22:00",
        "hours":     8,
        "overnight": False,
        "label":     "Evening  (14:00 --- 22:00)",
    },
    "Night": {
        "start":     "22:00",
        "end":       "06:00",
        "hours":     8,
        "overnight": True,
        "label":     "Night    (22:00 --- 06:00)",
    },
}

GRACE_MINUTES   = 15
MIN_OVERTIME_AFTER_SHIFT_MINUTES = 120
MAX_WORK_SESSION_HOURS = 12
WORKING_DAYS    = 30
OT_MULTIPLIER   = 1.5
HALFDAY_LATE_THRESHOLD_RATIO = 0.25
ABSENT_LATE_THRESHOLD_RATIO  = 0.50

SHIFT_COLORS = {
    "Morning": "#f59e0b",
    "Evening": "#6366f1",
    "Night":   "#1e3a5f",
}


# ------ Internal helpers ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _parse_time(time_str, base_date=None):
    if base_date is None:
        base_date = _app_today_date()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(time_str, fmt).time()
            return datetime.combine(base_date, t)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: '{time_str}'")


def calculate_work_session_hours(checkin_str, checkout_str, max_hours=MAX_WORK_SESSION_HOURS):
    """Return a valid same-day/overnight duration, or None if implausible."""
    try:
        checkin_dt = _parse_time(str(checkin_str)[:5])
        checkout_dt = _parse_time(str(checkout_str)[:5])
        max_hours = float(max_hours)
    except (TypeError, ValueError):
        return None

    if checkout_dt < checkin_dt:
        checkout_dt += timedelta(days=1)

    hours_worked = (checkout_dt - checkin_dt).total_seconds() / 3600
    if hours_worked < 0 or hours_worked > max_hours:
        return None
    return round(hours_worked, 2)


def _days_in_month(year_month):
    try:
        year, month = map(int, str(year_month).split("-"))
        return calendar.monthrange(year, month)[1]
    except (TypeError, ValueError):
        return WORKING_DAYS


def _salary_period_for_month(year_month=None, payroll_cycle_start_day=1):
    if year_month is None:
        year_month = _app_trusted_now().strftime("%Y-%m")
    try:
        year, month = map(int, str(year_month).split("-"))
        start_day = int(payroll_cycle_start_day if payroll_cycle_start_day is not None else 1)
    except (TypeError, ValueError):
        today = _app_today_date()
        year_month = today.strftime("%Y-%m")
        year, month = today.year, today.month
        start_day = 1
    start_day = min(max(start_day, 1), 31)
    month_first = date(year, month, 1)
    month_last = date(year, month, calendar.monthrange(year, month)[1])
    if start_day <= 1:
        start = month_first
        end = month_last
        mode = "calendar"
    else:
        prev_last = month_first - timedelta(days=1)
        start = date(prev_last.year, prev_last.month, min(start_day, prev_last.day))
        next_start = date(year, month, min(start_day, month_last.day))
        end = next_start - timedelta(days=1)
        mode = "custom"
    return {
        "month": year_month,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "payroll_days": (end - start).days + 1,
        "cycle_start_day": start_day,
        "cycle_mode": mode,
        "cycle_label": f"{start.isoformat()} to {end.isoformat()}",
    }


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


def _salary_period_for_employee(emp, salary_period):
    start = salary_period["start_date"]
    end = salary_period["end_date"]

    joining_date = _employee_joining_date(emp)
    leaving_date = _employee_leaving_date(emp)
    if joining_date and joining_date > start:
        start = joining_date
    if leaving_date and leaving_date < end:
        end = leaving_date
    if start > end:
        return None

    active_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    adjusted = dict(salary_period)
    adjusted["start_date"] = start
    adjusted["end_date"] = end
    adjusted["payroll_days"] = active_days
    adjusted["employment_start"] = joining_date or ""
    adjusted["employment_end"] = leaving_date or ""
    adjusted["full_payroll_days"] = salary_period["payroll_days"]
    adjusted["cycle_label"] = f"{start} to {end}"
    return adjusted


def _employee_overlaps_period(emp, period_start, period_end):
    joining_date = _employee_joining_date(emp)
    leaving_date = _employee_leaving_date(emp)
    if emp.get("deleted") and not leaving_date:
        return False
    if joining_date and joining_date > period_end:
        return False
    if leaving_date and leaving_date < period_start:
        return False
    return True


def _prorate_basic_salary(basic_salary, salary_period):
    full_days = int(salary_period.get("full_payroll_days") or salary_period.get("payroll_days") or 1)
    active_days = int(salary_period.get("payroll_days") or full_days)
    if active_days >= full_days:
        return float(basic_salary)
    return round(float(basic_salary) * active_days / max(full_days, 1), 2)


def _money_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _has_basic_salary_value(value):
    return _money_value(value) > 0


def _employee_basic_salary_value(emp):
    for field in ("basic_salary", "salary"):
        if field in emp and _has_basic_salary_value(emp.get(field)):
            return float(emp.get(field))
    return 0.0


def get_basic_salary_info_for_month(emp, year_month, period_end=None):
    """Returns (has_basic_salary, amount) effective for the selected salary period."""
    emp_id = emp.get("emp_id")
    if period_end:
        month_end = period_end
    else:
        try:
            year, month = map(int, str(year_month).split("-"))
            month_end = f"{year_month}-{calendar.monthrange(year, month)[1]:02d}"
        except (TypeError, ValueError):
            month_end = _app_today_iso()

    doc = salary_history_col.find_one(
        {"emp_id": emp_id, "effective_from": {"$lte": month_end}},
        sort=[("effective_from", -1), ("created_at", -1)]
    )
    if doc:
        amount = _money_value(doc.get("basic_salary"))
        return amount > 0, amount

    amount = _employee_basic_salary_value(emp)
    return amount > 0, amount


def get_basic_salary_for_month(emp, year_month, period_end=None):
    """Returns the salary effective for the selected salary period."""
    return get_basic_salary_info_for_month(emp, year_month, period_end=period_end)[1]



def _shift_window(shift_name, checkin_str):
    """Returns (start_dt, end_dt) aligned to checkin date."""
    s    = SHIFTS[shift_name]
    checkin_dt = _parse_time(checkin_str)
    base = checkin_dt.date()
    if s["overnight"]:
        end_time = _parse_time(s["end"], base).time()
        if checkin_dt.time() < end_time:
            base -= timedelta(days=1)
    s_dt = _parse_time(s["start"], base)
    e_dt = _parse_time(s["end"],   base)
    if s["overnight"] and e_dt <= s_dt:
        e_dt += timedelta(days=1)
    return s_dt, e_dt


def get_holiday(query_date=None):
    """
    Returns a holiday document for query_date, or None.
    Supported holiday date fields: date, holiday_date, day.
    """
    query_date = query_date or _app_today_iso()
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
    return get_holiday(query_date) is not None


def get_holidays_for_range(start_date, end_date):
    """Returns active holiday documents whose date falls inside the period."""
    holidays = []
    seen_dates = set()
    for field in ("date", "holiday_date", "day"):
        docs = holidays_col.find({
            field: {"$gte": start_date, "$lte": end_date},
            "active": {"$ne": False},
            "deleted": {"$ne": True},
        })
        for doc in docs:
            holiday_date = doc.get(field)
            if holiday_date and holiday_date not in seen_dates:
                doc["_holiday_date"] = holiday_date
                holidays.append(doc)
                seen_dates.add(holiday_date)
    return sorted(holidays, key=lambda h: h["_holiday_date"])


def get_holidays_for_month(year_month):
    """Returns active holiday documents whose date falls in YYYY-MM."""
    period = _salary_period_for_month(year_month, 1)
    return get_holidays_for_range(period["start_date"], period["end_date"])


def _is_sunday_date(query_date):
    try:
        return date.fromisoformat(query_date).weekday() == 6
    except ValueError:
        return False


def approve_sunday_work(emp_id, work_date, approved_by="admin", reason=""):
    try:
        emp_id = int(emp_id)
        work_date = str(work_date or "").strip()
        parsed = date.fromisoformat(work_date)
    except (TypeError, ValueError):
        return False, "Enter a valid Sunday date in YYYY-MM-DD format."
    if parsed.weekday() != 6:
        return False, "Selected date is not Sunday."
    emp = employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}})
    if not emp:
        return False, f"No active employee found with ID {emp_id}."
    reason = str(reason or "").strip()
    if not reason:
        return False, "Reason is required for Sunday work approval."
    sunday_work_col.update_one(
        {"emp_id": emp_id, "date": work_date},
        {"$set": {
            "emp_id": emp_id,
            "emp_name": emp.get("name", "Unknown"),
            "date": work_date,
            "approved_by": str(approved_by or "admin"),
            "reason": reason,
            "active": True,
            "updated_at": _app_now_stamp(),
        }},
        upsert=True,
    )
    try:
        from audit_log import log_action
        log_action(
            "SUNDAY_WORK_APPROVED",
            str(approved_by or "admin"),
            target=f"Employee ID {emp_id}",
            details=f"Approved Sunday work on {work_date}. Reason: {reason or '-'}",
        )
    except Exception:
        pass
    try:
        from auth_model import create_employee_notification
        create_employee_notification(
            emp_id,
            "Sunday work approved",
            f"Your Sunday work request for {work_date} has been approved. Reason: {reason or '-'}",
            request_id=f"sunday-work-{emp_id}-{work_date}",
            notification_type="sunday_work",
        )
    except Exception:
        pass
    return True, f"Sunday work approved for Employee ID {emp_id} on {work_date}."


def get_sunday_work_approval_dates_for_range(emp_id, start_date, end_date):
    try:
        emp_id = int(emp_id)
    except (TypeError, ValueError):
        return set()
    docs = sunday_work_col.find({
        "emp_id": emp_id,
        "date": {"$gte": start_date, "$lte": end_date},
        "active": {"$ne": False},
    }, {"_id": 0, "date": 1})
    return {str(doc.get("date")) for doc in docs if doc.get("date")}


def get_sunday_work_approval_map(emp_ids, start_date, end_date):
    try:
        emp_ids = [int(emp_id) for emp_id in emp_ids]
    except Exception:
        emp_ids = []
    if not emp_ids:
        return {}
    docs = sunday_work_col.find({
        "emp_id": {"$in": emp_ids},
        "date": {"$gte": start_date, "$lte": end_date},
        "active": {"$ne": False},
    }, {"_id": 0, "emp_id": 1, "date": 1})
    result = {}
    for doc in docs:
        result.setdefault(doc.get("emp_id"), set()).add(str(doc.get("date")))
    return result


def _is_paid_sunday_for_employee(query_date, sunday_work_dates=None):
    return _is_sunday_date(query_date) and query_date not in (sunday_work_dates or set())


def is_sunday_off(emp_id, query_date):
    """Return True when the date is Sunday without active work approval."""
    if not _is_sunday_date(query_date):
        return False
    approvals = get_sunday_work_approval_dates_for_range(
        emp_id,
        query_date,
        query_date,
    )
    return query_date not in approvals


def get_paid_holidays_for_range(start_date, end_date):
    """Returns paid-holiday dates in the period, including Sundays and holidays."""
    paid = {}
    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    while current <= end:
        current_str = current.isoformat()
        if _is_sunday_date(current_str):
            paid[current_str] = {"_holiday_date": current_str, "name": "Sunday"}
        current += timedelta(days=1)

    for holiday in get_holidays_for_range(start_date, end_date):
        paid[holiday["_holiday_date"]] = holiday

    return [paid[day] for day in sorted(paid)]


def get_paid_holidays_for_month(year_month):
    """
    Returns paid-holiday dates for the month, including Sundays and any
    active holiday records from MongoDB. Holiday records override Sundays.
    """
    period = _salary_period_for_month(year_month, 1)
    return get_paid_holidays_for_range(period["start_date"], period["end_date"])


def get_approved_leave_credits_for_range(emp_id, start_date, end_date):
    """Returns {date: {paid, unpaid}} for approved leave in a date range."""
    credits = {}
    sunday_work_dates = get_sunday_work_approval_dates_for_range(emp_id, start_date, end_date)
    docs = leave_requests_col.find({
        "emp_id": int(emp_id),
        "status": {"$in": ["Approved", "Revert Requested"]},
        "$or": [
            {"working_dates": {"$elemMatch": {"$gte": start_date, "$lte": end_date}}},
            {
                "working_dates": {"$exists": False},
                "from_date": {"$lte": end_date},
                "to_date": {"$gte": start_date},
            },
        ],
    })

    for doc in docs:
        total_days = float(doc.get("days", 0) or 0)
        paid_remaining = float(doc.get("paid_days", total_days) or 0)
        unpaid_remaining = float(doc.get("unpaid_days", max(total_days - paid_remaining, 0)) or 0)
        working_dates = list(doc.get("working_dates") or [])

        if "working_dates" not in doc:
            try:
                current = date.fromisoformat(doc.get("from_date"))
                end = date.fromisoformat(doc.get("to_date"))
            except (TypeError, ValueError):
                continue
            while current <= end:
                current_str = current.isoformat()
                if (not _is_sunday_date(current_str) or current_str in sunday_work_dates) and not is_holiday(current_str):
                    working_dates.append(current_str)
                current += timedelta(days=1)

        for leave_date in working_dates:
            leave_date = str(leave_date)
            if leave_date < start_date or leave_date > end_date:
                continue
            date_credit = credits.setdefault(leave_date, {"paid": 0.0, "unpaid": 0.0})
            paid_credit = min(1.0 - date_credit["paid"] - date_credit["unpaid"], paid_remaining)
            paid_credit = max(paid_credit, 0)
            date_credit["paid"] += paid_credit
            paid_remaining -= paid_credit

            unpaid_credit = min(1.0 - date_credit["paid"] - date_credit["unpaid"], unpaid_remaining)
            unpaid_credit = max(unpaid_credit, 0)
            date_credit["unpaid"] += unpaid_credit
            unpaid_remaining -= unpaid_credit

    return credits


def get_approved_leave_credits(emp_id, year_month):
    """Returns {date: {paid, unpaid}} for approved leave in a calendar month."""
    period = _salary_period_for_month(year_month, 1)
    return get_approved_leave_credits_for_range(emp_id, period["start_date"], period["end_date"])


# ------------------------------------------------------------------------------------------------------------------------------------------
#  1. ASSIGN SHIFT  (Admin)
# ------------------------------------------------------------------------------------------------------------------------------------------
def assign_shift(emp_id, shift_name):
    """Admin assigns or re-assigns a shift. Returns (True, msg) or (False, err)."""
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return False, "Employee ID must be a number!"
    if shift_name not in SHIFTS:
        return False, f"Invalid shift. Choose: {', '.join(SHIFTS)}."
    if not employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}):
        return False, f"No employee found with ID {emp_id}!"
    effective_from = _app_today_iso()
    existing = shift_assign_col.find_one({"emp_id": emp_id}) or {}
    history = _normalized_shift_history(existing)
    history = [
        item for item in history
        if item["effective_from"] != effective_from
    ]
    history.append({
        "shift_name": shift_name,
        "effective_from": effective_from,
    })
    history.sort(key=lambda item: item["effective_from"])
    shift_assign_col.update_one(
        {"emp_id": emp_id},
        {"$set": {
            "shift_name": shift_name,
            "assigned_on": effective_from,
            "history": history,
        }},
        upsert=True
    )
    return True, f"--- {SHIFTS[shift_name]['label']} assigned to Employee ID {emp_id}!"


# ------------------------------------------------------------------------------------------------------------------------------------------
#  2. GET EMPLOYEE SHIFT
# ------------------------------------------------------------------------------------------------------------------------------------------
DEFAULT_SHIFT = "Morning"


def _normalized_shift_history(doc):
    """Return valid, deduplicated effective-dated assignments."""
    if not doc:
        return []
    by_date = {}
    for item in doc.get("history") or []:
        if not isinstance(item, dict):
            continue
        shift_name = item.get("shift_name")
        effective_from = _as_date_string(item.get("effective_from"))
        if shift_name in SHIFTS and effective_from:
            by_date[effective_from] = {
                "shift_name": shift_name,
                "effective_from": effective_from,
            }

    legacy_shift = doc.get("shift_name")
    legacy_date = _as_date_string(doc.get("assigned_on"))
    if legacy_shift in SHIFTS and legacy_date and legacy_date not in by_date:
        by_date[legacy_date] = {
            "shift_name": legacy_shift,
            "effective_from": legacy_date,
        }
    return [by_date[key] for key in sorted(by_date)]


def _shift_from_assignment_doc(doc, query_date=None):
    if not doc:
        return None
    if query_date is None:
        shift_name = doc.get("shift_name")
        return shift_name if shift_name in SHIFTS else None

    query_date = _as_date_string(query_date)
    if not query_date:
        return None
    applicable = [
        item for item in _normalized_shift_history(doc)
        if item["effective_from"] <= query_date
    ]
    if applicable:
        return applicable[-1]["shift_name"]
    return DEFAULT_SHIFT


def _assign_default_shift(emp_id):
    """Assigns the default shift for active employees when none exists."""
    if not employees_col.find_one({"emp_id": emp_id, "deleted": {"$ne": True}}):
        return None
    shift_assign_col.update_one(
        {"emp_id": emp_id},
        {"$set": {
            "shift_name": DEFAULT_SHIFT,
            "assigned_on": _app_today_iso(),
            "history": [{
                "shift_name": DEFAULT_SHIFT,
                "effective_from": _app_today_iso(),
            }],
        }},
        upsert=True
    )
    return DEFAULT_SHIFT


def get_employee_shift(emp_id, query_date=None):
    """Return the shift effective on query_date, or the current shift."""
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None
    doc = shift_assign_col.find_one({"emp_id": emp_id})
    assigned_shift = _shift_from_assignment_doc(doc, query_date)
    if assigned_shift:
        return assigned_shift
    if query_date is not None:
        return DEFAULT_SHIFT
    return _assign_default_shift(emp_id)


# ------------------------------------------------------------------------------------------------------------------------------------------
#  3. ALL SHIFT ASSIGNMENTS  (Admin table)
# ------------------------------------------------------------------------------------------------------------------------------------------
def get_all_shift_assignments():
    """Returns list of all employees with their assigned shift."""
    employees = list(employees_col.find({"role": "employee", "deleted": {"$ne": True}}, {"password": 0}))
    result = []
    for emp in employees:
        eid = emp.get("emp_id")
        shift = get_employee_shift(eid)
        doc = shift_assign_col.find_one({"emp_id": eid})
        result.append({
            "emp_id":      str(eid),
            "name":        emp.get("name", "---"),
            "department":  emp.get("department", "---"),
            "shift":       shift or "Not Assigned",
            "shift_label": SHIFTS[shift]["label"] if shift in SHIFTS else "Not Assigned",
            "assigned_on": doc["assigned_on"] if doc else "---",
        })
    return sorted(result, key=lambda x: int(x["emp_id"]) if x["emp_id"].isdigit() else 0)


# ------------------------------------------------------------------------------------------------------------------------------------------
#  4. SHIFT METRICS  (late min + OT hours)
#     Called by attendance.py after checkout
# ------------------------------------------------------------------------------------------------------------------------------------------
def calculate_shift_metrics(
    emp_id,
    checkin_str,
    checkout_str,
    min_ot_minutes=None,
    shift_name=None,
    work_date=None,
):
    """
    Returns dict:
        shift_name, late_minutes (deductable), raw_late_mins,
        overtime_hours, status ("Present"|"Late")
    Returns None on parse error.
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None
    try:
        min_ot_minutes = int(min_ot_minutes if min_ot_minutes is not None else MIN_OVERTIME_AFTER_SHIFT_MINUTES)
    except (TypeError, ValueError):
        min_ot_minutes = MIN_OVERTIME_AFTER_SHIFT_MINUTES
    min_ot_minutes = max(0, min_ot_minutes)

    if shift_name not in SHIFTS:
        shift_name = get_employee_shift(emp_id, work_date)
    if not shift_name:
        return {
            "shift_name":     None,
            "late_minutes":   0,
            "raw_late_mins":  0,
            "overtime_hours": 0.0,
            "status":         "Present",
        }

    try:
        checkin_dt  = _parse_time(checkin_str)
        checkout_dt = _parse_time(checkout_str)
        start_dt, end_dt = _shift_window(shift_name, checkin_str)
    except ValueError:
        return None

    # Night shift: checkout might be next calendar day
    if checkout_dt < checkin_dt:
        checkout_dt += timedelta(days=1)

    # Late minutes
    raw_late        = max(0, int((checkin_dt - start_dt).total_seconds() / 60))
    deductable_late = max(0, raw_late - GRACE_MINUTES)

    # Early exit minutes
    # If employee arrived late, their effective end = checkin + shift_hours
    # so they aren't double-penalised (late AND early exit) for the same time.
    shift_hours = SHIFTS[shift_name]["hours"]
    hours_worked = calculate_work_session_hours(checkin_str, checkout_str)
    if hours_worked is None:
        return None

    # Only apply early exit if employee worked at least 50% of shift.
    # Below that, Half-Day/Absent status handles the penalty --- no double charge.
    MIN_HOURS_FOR_EARLY_EXIT = shift_hours * 0.5

    if hours_worked < MIN_HOURS_FOR_EARLY_EXIT:
        deductable_early = 0
    else:
        if deductable_late > 0:
            # Late arrival: measure early exit against their personal end time
            effective_end = checkin_dt + timedelta(hours=shift_hours)
        else:
            # On-time arrival: measure against shift end as normal
            effective_end = end_dt

        early_exit_threshold = effective_end - timedelta(minutes=GRACE_MINUTES)
        if checkout_dt < early_exit_threshold:
            deductable_early = int((early_exit_threshold - checkout_dt).total_seconds() / 60)
        else:
            deductable_early = 0

    # Fair OT rule:
    # - On-time employees complete the normal shift ending at end_dt.
    # - Late employees first complete the full shift duration from check-in.
    # - OT is counted only after that required end, and only if it reaches 2h.
    required_end_dt = end_dt if checkin_dt <= start_dt else checkin_dt + timedelta(hours=shift_hours)
    extra_after_required_minutes = max(0, int((checkout_dt - required_end_dt).total_seconds() / 60))
    if extra_after_required_minutes >= min_ot_minutes:
        ot_hours = round(extra_after_required_minutes / 60, 2)
    else:
        ot_hours = 0.0

    halfday_late_limit = int(shift_hours * 60 * HALFDAY_LATE_THRESHOLD_RATIO)
    absent_late_limit  = int(shift_hours * 60 * ABSENT_LATE_THRESHOLD_RATIO)

    if raw_late >= shift_hours * 60 * 0.5:
        status = "Half-Day"
    elif deductable_late > 0:
        status = "Late"
    elif hours_worked < shift_hours * 0.25:
        status = "Absent"
    elif hours_worked < shift_hours * 0.5:
        status = "Half-Day"
    else:
        status = "Present"

    return {
        "shift_name":        shift_name,
        "late_minutes":      deductable_late,
        "raw_late_mins":     raw_late,
        "early_exit_minutes": deductable_early,
        "overtime_hours":    ot_hours,
        "status":            status,
        "halfday_late_limit": halfday_late_limit,
        "absent_late_limit":  absent_late_limit,
    }


# ------------------------------------------------------------------------------------------------------------------------------------------
#  4b. ARRIVAL STATUS  (check-in only — no checkout required)
#      Single source of truth for mark_arrival in attendance.py.
#      Assumes the employee will complete their full shift (best-case
#      projection); checkout recalculates via calculate_shift_metrics().
# ------------------------------------------------------------------------------------------------------------------------------------------
def calculate_arrival_status(emp_id, arrival_time_str):
    """
    Returns dict:
        shift_name, status ("Present"|"Late"|"Half-Day"|"Absent"),
        late_minutes (deductable), raw_late_mins
    or None on parse error.

    Status thresholds mirror calculate_shift_metrics() — both key off
    projected hours_worked vs shift duration fractions so the two calls
    remain consistent even if thresholds are later tuned.
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None

    shift_name = get_employee_shift(emp_id)
    if not shift_name or shift_name not in SHIFTS:
        return None  # Caller falls back to legacy calculate_status()

    try:
        arr_dt   = _parse_time(arrival_time_str[:5])
        start_dt = _parse_time(SHIFTS[shift_name]["start"], arr_dt.date())
    except ValueError:
        return None

    shift_hours = SHIFTS[shift_name]["hours"]

    raw_late        = max(0, int((arr_dt - start_dt).total_seconds() / 60))
    deductable_late = max(0, raw_late - GRACE_MINUTES)

    # Project hours_worked assuming the employee works their full shift.
    # This matches what calculate_shift_metrics() will see at checkout time
    # (assuming on-time checkout), so arrival status == final status when
    # the employee completes their shift.
    projected_hours = max(0.0, shift_hours - raw_late / 60)

    if raw_late >= shift_hours * 60 * 0.5:
        status = "Half-Day"
    elif deductable_late > 0:
        status = "Late"
    else:
        status = "Present"

    return {
        "shift_name":    shift_name,
        "status":        status,
        "late_minutes":  deductable_late,
        "raw_late_mins": raw_late,
    }


# ------------------------------------------------------------------------------------------------------------------------------------------
#  5. MONTHLY SALARY BREAKDOWN  (Admin report)
# ------------------------------------------------------------------------------------------------------------------------------------------
def calculate_monthly_salary(emp_id, year_month=None, ot_multiplier=None, min_ot_minutes=None, payroll_cycle_start_day=1):
    """
    Full breakdown for one employee for a month (default = current month).
    Returns dict or None if employee not found.
    """
    try:
        emp_id = int(emp_id)
    except (ValueError, TypeError):
        return None

    emp = employees_col.find_one({"emp_id": emp_id})
    if not emp:
        return None

    if year_month is None:
        year_month = _app_trusted_now().strftime("%Y-%m")
    try:
        ot_multiplier = float(ot_multiplier if ot_multiplier is not None else OT_MULTIPLIER)
    except (TypeError, ValueError):
        ot_multiplier = OT_MULTIPLIER
    ot_multiplier = max(0, ot_multiplier)
    try:
        min_ot_minutes = int(min_ot_minutes if min_ot_minutes is not None else MIN_OVERTIME_AFTER_SHIFT_MINUTES)
    except (TypeError, ValueError):
        min_ot_minutes = MIN_OVERTIME_AFTER_SHIFT_MINUTES
    min_ot_minutes = max(0, min_ot_minutes)

    salary_period = _salary_period_for_month(year_month, payroll_cycle_start_day)
    if not _employee_overlaps_period(
        emp,
        salary_period["start_date"],
        salary_period["end_date"],
    ):
        return None
    salary_period = _salary_period_for_employee(emp, salary_period)
    if salary_period is None:
        return None
    period_start = salary_period["start_date"]
    period_end = salary_period["end_date"]
    payroll_days = salary_period["payroll_days"]
    salary_history = list(salary_history_col.find(
        {"emp_id": emp_id, "effective_from": {"$lte": period_end}},
        sort=[("effective_from", 1), ("created_at", 1)],
    ))
    basic_salary = calculate_prorated_salary(
        _employee_basic_salary_value(emp),
        salary_history,
        period_start,
        period_end,
        salary_period.get("full_payroll_days", payroll_days),
    )
    has_basic_salary = basic_salary > 0
    shift_name  = get_employee_shift(emp_id, period_end) or DEFAULT_SHIFT
    shift_hours = SHIFTS[shift_name]["hours"]

    att_records = list(attendance_col.find(
        {
            "emp_id": emp_id,
            "date": {"$gte": period_start, "$lte": period_end},
            "deleted": {"$ne": True},
        },
    ).sort("date", 1))
    sunday_work_dates = get_sunday_work_approval_dates_for_range(emp_id, period_start, period_end)
    leave_credits = get_approved_leave_credits_for_range(emp_id, period_start, period_end)

    records           = []
    days_present      = 0
    days_absent       = 0
    days_late         = 0
    paid_holidays     = 0
    total_late_min    = 0
    total_ot_hrs      = 0.0
    total_early_min   = 0
    days_halfday      = 0
    missed_checkouts  = 0
    paid_leave_days   = 0.0
    unpaid_leave_days = 0.0
    leave_dates_used  = set()
    recorded_dates    = set()

    for rec in att_records:
        rec_date    = rec.get("date", "")
        recorded_dates.add(rec_date)
        holiday     = get_holiday(rec_date)
        is_sunday   = _is_paid_sunday_for_employee(rec_date, sunday_work_dates)
        status_raw  = rec.get("status", "Absent")
        arrival     = rec.get("arrival_time") or rec.get("checkin_time")
        checkout    = rec.get("checkout_time")
        leave_credit = leave_credits.get(rec_date, {"paid": 0.0, "unpaid": 0.0})
        paid_leave = float(leave_credit.get("paid", 0.0))
        unpaid_leave = float(leave_credit.get("unpaid", 0.0))
        late_min    = 0
        ot_hours    = 0.0
        early_min   = 0
        final_status = status_raw.capitalize()

        if paid_leave or unpaid_leave:
            paid_leave_days += paid_leave
            unpaid_leave_days += unpaid_leave
            if unpaid_leave:
                days_absent += unpaid_leave
            leave_dates_used.add(rec_date)
            final_status = "Paid Leave" if not unpaid_leave else "Unpaid Leave"
        elif holiday or is_sunday:
            paid_holidays += 1
            final_status = "Paid Holiday"
        elif arrival and checkout:
            if checkout:
                record_shift = rec.get("shift")
                if record_shift not in SHIFTS:
                    record_shift = get_employee_shift(emp_id, rec_date)
                metrics = calculate_shift_metrics(
                    emp_id,
                    arrival,
                    checkout,
                    min_ot_minutes=min_ot_minutes,
                    shift_name=record_shift,
                    work_date=rec_date,
                )
                if metrics:
                    late_min     = metrics["late_minutes"]
                    ot_hours     = metrics["overtime_hours"]
                    early_min    = metrics.get("early_exit_minutes", 0)
                    final_status = metrics["status"]

            if final_status == "Absent":
                payable_absent = max(1.0 - paid_leave, 0)
                days_absent += payable_absent
                paid_leave_days += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
                late_min = 0
                early_min = 0
            elif final_status == "Half-Day":
                payable_halfday = max(0.5 - paid_leave, 0)
                days_halfday += payable_halfday * 2
                paid_leave_days += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
                early_min = 0
            else:
                days_present += 1

            if final_status == "Late" and late_min > 0:
                days_late += 1
        elif status_raw.lower() in ("present", "late") and arrival:
            missed_checkouts += 1
            payable_absent = max(1.0 - paid_leave, 0)
            days_absent += payable_absent
            paid_leave_days += paid_leave
            unpaid_leave_days += unpaid_leave
            leave_dates_used.add(rec_date)
            final_status = "Missed Checkout"
        elif status_raw.lower() == "half-day":
            # Don't deduct for half-day on a paid holiday
            try:
                is_sunday = _is_paid_sunday_for_employee(rec_date, sunday_work_dates)
            except ValueError:
                is_sunday = False
            if not is_sunday:
                payable_halfday = max(0.5 - paid_leave, 0)
                days_halfday += payable_halfday * 2
                paid_leave_days += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
        else:
            # Don't deduct for absence on a paid holiday
            try:
                is_sunday = _is_paid_sunday_for_employee(rec_date, sunday_work_dates)
            except ValueError:
                is_sunday = False
            if not is_sunday:
                payable_absent = max(1.0 - paid_leave, 0)
                days_absent += payable_absent
                paid_leave_days += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)

        total_late_min  += late_min
        total_ot_hrs    += ot_hours
        total_early_min += early_min

        records.append({
            "date":      rec.get("date", "---"),
            "status":    final_status,
            "arrival":   arrival  or "---",
            "checkout":  checkout or "---",
            "late_min":  late_min,
            "early_min": early_min,
            "ot_hours":  ot_hours,
        })

    for leave_date, credit in leave_credits.items():
        if leave_date in recorded_dates or leave_date in leave_dates_used:
            continue
        if is_holiday(leave_date) or _is_paid_sunday_for_employee(leave_date, sunday_work_dates):
            continue
        paid_leave = float(credit.get("paid", 0.0))
        unpaid_leave = float(credit.get("unpaid", 0.0))
        paid_leave_days += paid_leave
        unpaid_leave_days += unpaid_leave
        if unpaid_leave:
            days_absent += unpaid_leave
        records.append({
            "date":      leave_date,
            "status":    "Paid Leave" if not unpaid_leave else "Unpaid Leave",
            "arrival":   "--------",
            "checkout":  "--------",
            "late_min":  0,
            "early_min": 0,
            "ot_hours":  0.0,
        })

    for holiday in get_paid_holidays_for_range(period_start, period_end):
        holiday_date = holiday["_holiday_date"]
        if holiday_date in recorded_dates:
            continue
        if holiday.get("name") == "Sunday" and holiday_date in sunday_work_dates:
            continue
        paid_holidays += 1
        records.append({
            "date":      holiday_date,
            "status":    "Paid Holiday",
            "arrival":   "---",
            "checkout":  "---",
            "late_min":  0,
            "early_min": 0,
            "ot_hours":  0.0,
        })

    records.sort(key=lambda rec: rec.get("date", ""))

    working_days = max(payroll_days - paid_holidays, 0)
    # Use working_days as denominator so deduction rates reflect actual
    # working days — not the full calendar/cycle period which includes
    # paid holidays. Fallback to payroll_days if working_days is 0
    # (e.g. an entire month of holidays) to avoid ZeroDivisionError.
    effective_days = working_days if working_days > 0 else payroll_days
    amounts = calculate_payroll_amounts(
        basic_salary if has_basic_salary else 0.0,
        effective_days,
        shift_hours,
        days_absent,
        days_halfday,
        total_late_min,
        total_early_min,
        total_ot_hrs,
        ot_multiplier,
    )
    absent_deduction = amounts["absent_deduction"]
    halfday_deduction = amounts["halfday_deduction"]
    late_deduction = amounts["late_deduction"]
    early_exit_deduction = amounts["early_exit_deduction"]
    ot_pay = amounts["ot_pay"]
    attendance_deductions = amounts["attendance_deductions"]
    gross_salary = amounts["gross_salary"]
    total_deductions      = attendance_deductions
    net_salary = amounts["net_salary"]

    return {
        "emp_id":                str(emp_id),
        "name":                  emp.get("name", "---"),
        "department":            emp.get("department", "---"),
        "shift":                 shift_name,
        "has_basic_salary":      has_basic_salary,
        "basic_salary":          basic_salary,
        "gross_salary":          gross_salary,
        "attendance_deductions": attendance_deductions,
        "total_deductions":      total_deductions,
        "payroll_days":          payroll_days,
        "working_days":          working_days,
        "days_present":          days_present,
        "days_absent":           days_absent,
        "days_halfday":          days_halfday,
        "paid_holidays":         paid_holidays,
        "paid_leave_days":       round(paid_leave_days, 2),
        "unpaid_leave_days":     round(unpaid_leave_days, 2),
        "missed_checkouts":      missed_checkouts,
        "days_late":             days_late,
        "total_late_minutes":    total_late_min,
        "total_late_hours":      round(total_late_min / 60, 2),
        "total_early_minutes":   total_early_min,
        "absent_deduction":      absent_deduction,
        "halfday_deduction":     halfday_deduction,
        "late_deduction":        late_deduction,
        "early_exit_deduction":  early_exit_deduction,
        "total_ot_hours":        round(total_ot_hrs, 2),
        "ot_pay":                ot_pay,
        "net_salary":            net_salary,
        "ot_multiplier":         ot_multiplier,
        "min_ot_minutes":        min_ot_minutes,
        "month":                 year_month,
        "period_start":          period_start,
        "period_end":            period_end,
        "payroll_cycle_start_day": salary_period["cycle_start_day"],
        "payroll_cycle_mode":    salary_period["cycle_mode"],
        "payroll_cycle_label":   salary_period["cycle_label"],
        "records":               records,
    }


# ------------------------------------------------------------------------------------------------------------------------------------------
#  6. ALL SALARY SUMMARIES  (Admin table)
# ------------------------------------------------------------------------------------------------------------------------------------------
def _leave_credits_from_docs(leave_docs, start_date, end_date, holiday_set, sunday_work_dates=None):
    sunday_work_dates = sunday_work_dates or set()
    """
    Builds {date: {paid, unpaid}} from pre-fetched leave request docs.
    Identical logic to get_approved_leave_credits_for_range() but works
    from already-fetched documents instead of querying MongoDB.
    """
    credits = {}
    for doc in leave_docs:
        total_days       = float(doc.get("days", 0) or 0)
        paid_remaining   = float(doc.get("paid_days", total_days) or 0)
        unpaid_remaining = float(doc.get("unpaid_days", max(total_days - paid_remaining, 0)) or 0)
        working_dates    = list(doc.get("working_dates") or [])

        if "working_dates" not in doc:
            try:
                current = date.fromisoformat(doc.get("from_date"))
                end_d   = date.fromisoformat(doc.get("to_date"))
            except (TypeError, ValueError):
                continue
            while current <= end_d:
                cs = current.isoformat()
                if (not _is_sunday_date(cs) or cs in sunday_work_dates) and cs not in holiday_set:
                    working_dates.append(cs)
                current += timedelta(days=1)

        for leave_date in working_dates:
            leave_date = str(leave_date)
            if leave_date < start_date or leave_date > end_date:
                continue
            dc = credits.setdefault(leave_date, {"paid": 0.0, "unpaid": 0.0})
            paid_credit = min(1.0 - dc["paid"] - dc["unpaid"], paid_remaining)
            paid_credit = max(paid_credit, 0)
            dc["paid"]      += paid_credit
            paid_remaining  -= paid_credit
            unpaid_credit = min(1.0 - dc["paid"] - dc["unpaid"], unpaid_remaining)
            unpaid_credit = max(unpaid_credit, 0)
            dc["unpaid"]     += unpaid_credit
            unpaid_remaining -= unpaid_credit
    return credits


def _calculate_salary_from_bulk(
    emp, shift_name, basic_salary,
    att_records, leave_docs, holiday_set,
    salary_period, ot_multiplier=None, min_ot_minutes=None,
    salary_history=None, shift_assignment=None,
):
    """
    calculate_monthly_salary() with all DB calls removed.
    Receives pre-fetched data from get_all_salary_summaries().
    """
    try:
        emp_id = int(emp["emp_id"])
    except (ValueError, TypeError):
        return None

    try:
        ot_multiplier = float(ot_multiplier if ot_multiplier is not None else OT_MULTIPLIER)
    except (TypeError, ValueError):
        ot_multiplier = OT_MULTIPLIER
    ot_multiplier = max(0, ot_multiplier)
    try:
        min_ot_minutes = int(min_ot_minutes if min_ot_minutes is not None else MIN_OVERTIME_AFTER_SHIFT_MINUTES)
    except (TypeError, ValueError):
        min_ot_minutes = MIN_OVERTIME_AFTER_SHIFT_MINUTES
    min_ot_minutes = max(0, min_ot_minutes)

    salary_period = _salary_period_for_employee(emp, salary_period)
    if salary_period is None:
        return None
    period_start  = salary_period["start_date"]
    period_end    = salary_period["end_date"]
    payroll_days  = salary_period["payroll_days"]
    basic_salary = calculate_prorated_salary(
        basic_salary,
        salary_history or [],
        period_start,
        period_end,
        salary_period.get("full_payroll_days", payroll_days),
    )
    has_basic_salary = basic_salary > 0
    shift_hours   = SHIFTS[shift_name]["hours"]
    sunday_work_dates = get_sunday_work_approval_dates_for_range(emp_id, period_start, period_end)
    leave_credits = _leave_credits_from_docs(leave_docs, period_start, period_end, holiday_set, sunday_work_dates)

    records           = []
    days_present      = 0
    days_absent       = 0.0
    days_late         = 0
    paid_holidays     = 0
    total_late_min    = 0
    total_ot_hrs      = 0.0
    total_early_min   = 0
    days_halfday      = 0.0
    missed_checkouts  = 0
    paid_leave_days   = 0.0
    unpaid_leave_days = 0.0
    leave_dates_used  = set()
    recorded_dates    = set()

    for rec in att_records:
        rec_date    = rec.get("date", "")
        recorded_dates.add(rec_date)
        is_hol      = rec_date in holiday_set
        is_sunday   = _is_paid_sunday_for_employee(rec_date, sunday_work_dates)
        status_raw  = rec.get("status", "Absent")
        arrival     = rec.get("arrival_time") or rec.get("checkin_time")
        checkout    = rec.get("checkout_time")
        leave_credit = leave_credits.get(rec_date, {"paid": 0.0, "unpaid": 0.0})
        paid_leave   = float(leave_credit.get("paid", 0.0))
        unpaid_leave = float(leave_credit.get("unpaid", 0.0))
        late_min     = 0
        ot_hours     = 0.0
        early_min    = 0
        final_status = status_raw.capitalize()

        if paid_leave or unpaid_leave:
            paid_leave_days   += paid_leave
            unpaid_leave_days += unpaid_leave
            if unpaid_leave:
                days_absent += unpaid_leave
            leave_dates_used.add(rec_date)
            final_status = "Paid Leave" if not unpaid_leave else "Unpaid Leave"
        elif is_hol or is_sunday:
            paid_holidays += 1
            final_status   = "Paid Holiday"
        elif arrival and checkout:
            record_shift = rec.get("shift")
            if record_shift not in SHIFTS:
                record_shift = (
                    _shift_from_assignment_doc(shift_assignment, rec_date)
                    or shift_name
                )
            metrics = calculate_shift_metrics(
                emp_id,
                arrival,
                checkout,
                min_ot_minutes=min_ot_minutes,
                shift_name=record_shift,
                work_date=rec_date,
            )
            if metrics:
                late_min     = metrics["late_minutes"]
                ot_hours     = metrics["overtime_hours"]
                early_min    = metrics.get("early_exit_minutes", 0)
                final_status = metrics["status"]

            if final_status == "Absent":
                payable_absent = max(1.0 - paid_leave, 0)
                days_absent       += payable_absent
                paid_leave_days   += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
                late_min = 0; early_min = 0
            elif final_status == "Half-Day":
                payable_halfday = max(0.5 - paid_leave, 0)
                days_halfday      += payable_halfday * 2
                paid_leave_days   += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
                early_min = 0
            else:
                days_present += 1

            if final_status == "Late" and late_min > 0:
                days_late += 1
        elif status_raw.lower() in ("present", "late") and arrival:
            missed_checkouts  += 1
            payable_absent     = max(1.0 - paid_leave, 0)
            days_absent       += payable_absent
            paid_leave_days   += paid_leave
            unpaid_leave_days += unpaid_leave
            leave_dates_used.add(rec_date)
            final_status = "Missed Checkout"
        elif status_raw.lower() == "half-day":
            if not _is_paid_sunday_for_employee(rec_date, sunday_work_dates):
                payable_halfday = max(0.5 - paid_leave, 0)
                days_halfday      += payable_halfday * 2
                paid_leave_days   += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)
        else:
            if not _is_paid_sunday_for_employee(rec_date, sunday_work_dates):
                payable_absent     = max(1.0 - paid_leave, 0)
                days_absent       += payable_absent
                paid_leave_days   += paid_leave
                unpaid_leave_days += unpaid_leave
                leave_dates_used.add(rec_date)

        total_late_min  += late_min
        total_ot_hrs    += ot_hours
        total_early_min += early_min
        records.append({
            "date":      rec_date or "---",
            "status":    final_status,
            "arrival":   arrival  or "---",
            "checkout":  checkout or "---",
            "late_min":  late_min,
            "early_min": early_min,
            "ot_hours":  ot_hours,
        })

    for leave_date, credit in leave_credits.items():
        if leave_date in recorded_dates or leave_date in leave_dates_used:
            continue
        if leave_date in holiday_set or _is_paid_sunday_for_employee(leave_date, sunday_work_dates):
            continue
        paid_leave   = float(credit.get("paid", 0.0))
        unpaid_leave = float(credit.get("unpaid", 0.0))
        paid_leave_days   += paid_leave
        unpaid_leave_days += unpaid_leave
        if unpaid_leave:
            days_absent += unpaid_leave
        records.append({
            "date":      leave_date,
            "status":    "Paid Leave" if not unpaid_leave else "Unpaid Leave",
            "arrival":   "--------", "checkout": "--------",
            "late_min":  0, "early_min": 0, "ot_hours": 0.0,
        })

    # Paid holidays not already in att_records
    for hdate in sorted(holiday_set):
        if hdate < period_start or hdate > period_end:
            continue
        if hdate in recorded_dates:
            continue
        paid_holidays += 1
        records.append({
            "date":      hdate,
            "status":    "Paid Holiday",
            "arrival":   "---", "checkout": "---",
            "late_min":  0, "early_min": 0, "ot_hours": 0.0,
        })
    # Sundays not already recorded
    current = date.fromisoformat(period_start)
    end_d   = date.fromisoformat(period_end)
    while current <= end_d:
        cs = current.isoformat()
        if current.weekday() == 6 and cs not in recorded_dates and cs not in holiday_set and cs not in sunday_work_dates:
            paid_holidays += 1
            records.append({
                "date":      cs,
                "status":    "Paid Holiday",
                "arrival":   "---", "checkout": "---",
                "late_min":  0, "early_min": 0, "ot_hours": 0.0,
            })
        current += timedelta(days=1)

    records.sort(key=lambda r: r.get("date", ""))

    working_days   = max(payroll_days - paid_holidays, 0)
    effective_days = working_days if working_days > 0 else payroll_days
    amounts = calculate_payroll_amounts(
        basic_salary if has_basic_salary else 0.0,
        effective_days,
        shift_hours,
        days_absent,
        days_halfday,
        total_late_min,
        total_early_min,
        total_ot_hrs,
        ot_multiplier,
    )
    absent_deduction = amounts["absent_deduction"]
    halfday_deduction = amounts["halfday_deduction"]
    late_deduction = amounts["late_deduction"]
    early_exit_deduction = amounts["early_exit_deduction"]
    ot_pay = amounts["ot_pay"]
    attendance_deductions = amounts["attendance_deductions"]
    gross_salary = amounts["gross_salary"]
    net_salary = amounts["net_salary"]

    return {
        "emp_id":                str(emp_id),
        "name":                  emp.get("name", "---"),
        "department":            emp.get("department", "---"),
        "shift":                 shift_name,
        "has_basic_salary":      has_basic_salary,
        "basic_salary":          basic_salary,
        "gross_salary":          gross_salary,
        "attendance_deductions": attendance_deductions,
        "total_deductions":      attendance_deductions,
        "payroll_days":          payroll_days,
        "working_days":          working_days,
        "days_present":          days_present,
        "days_absent":           days_absent,
        "days_halfday":          days_halfday,
        "paid_holidays":         paid_holidays,
        "paid_leave_days":       round(paid_leave_days, 2),
        "unpaid_leave_days":     round(unpaid_leave_days, 2),
        "missed_checkouts":      missed_checkouts,
        "days_late":             days_late,
        "total_late_minutes":    total_late_min,
        "total_late_hours":      round(total_late_min / 60, 2),
        "total_early_minutes":   total_early_min,
        "absent_deduction":      absent_deduction,
        "halfday_deduction":     halfday_deduction,
        "late_deduction":        late_deduction,
        "early_exit_deduction":  early_exit_deduction,
        "total_ot_hours":        round(total_ot_hrs, 2),
        "ot_pay":                ot_pay,
        "net_salary":            net_salary,
        "ot_multiplier":         ot_multiplier,
        "min_ot_minutes":        min_ot_minutes,
        "month":                 salary_period["month"],
        "period_start":          period_start,
        "period_end":            period_end,
        "payroll_cycle_start_day": salary_period["cycle_start_day"],
        "payroll_cycle_mode":    salary_period["cycle_mode"],
        "payroll_cycle_label":   salary_period["cycle_label"],
        "records":               records,
    }


def get_all_salary_summaries(year_month=None, ot_multiplier=None, min_ot_minutes=None, payroll_cycle_start_day=1):
    if year_month is None:
        year_month = _app_trusted_now().strftime("%Y-%m")

    salary_period = _salary_period_for_month(year_month, payroll_cycle_start_day)
    period_start  = salary_period["start_date"]
    period_end    = salary_period["end_date"]

    # ── Bulk load 1: employees ───────────────────────────────────────────────
    employees = [
        emp for emp in employees_col.find({"role": "employee"}, {"password": 0})
        if _employee_overlaps_period(emp, period_start, period_end)
    ]
    if not employees:
        return []
    emp_ids = [emp["emp_id"] for emp in employees]

    # ── Bulk load 2: shift assignments (1 query for all employees) ───────────
    shift_docs = list(shift_assign_col.find({"emp_id": {"$in": emp_ids}}))
    shift_doc_map = {doc["emp_id"]: doc for doc in shift_docs}
    shift_map = {
        emp_id: _shift_from_assignment_doc(shift_doc_map.get(emp_id), period_end)
        for emp_id in emp_ids
    }

    # ── Bulk load 3: salary history (1 query for all employees) ─────────────
    salary_history_docs = list(salary_history_col.find(
        {"emp_id": {"$in": emp_ids}, "effective_from": {"$lte": period_end}},
        sort=[("emp_id", 1), ("effective_from", -1), ("created_at", -1)],
    ))
    salary_history_map = {}
    for doc in salary_history_docs:
        eid = doc["emp_id"]
        salary_history_map.setdefault(eid, []).append(doc)

    # ── Bulk load 4: attendance records (1 query for all employees) ──────────
    att_docs = attendance_col.find(
        {
            "emp_id": {"$in": emp_ids},
            "date":   {"$gte": period_start, "$lte": period_end},
            "deleted": {"$ne": True},
        }
    ).sort("date", 1)
    att_map = {}
    for doc in att_docs:
        att_map.setdefault(doc["emp_id"], []).append(doc)

    # ── Bulk load 5: leave requests (1 query for all employees) ─────────────
    leave_docs = leave_requests_col.find({
        "emp_id": {"$in": emp_ids},
        "status": {"$in": ["Approved", "Revert Requested"]},
        "$or": [
            {"working_dates": {"$elemMatch": {"$gte": period_start, "$lte": period_end}}},
            {
                "working_dates": {"$exists": False},
                "from_date": {"$lte": period_end},
                "to_date": {"$gte": period_start},
            },
        ],
    })
    leave_map = {}
    for doc in leave_docs:
        leave_map.setdefault(doc["emp_id"], []).append(doc)

    # ── Bulk load 6: holidays for the period (1 query, shared by all) ────────
    holiday_set = {
        h["_holiday_date"]
        for h in get_holidays_for_range(period_start, period_end)
    }

    results = []
    for emp in employees:
        emp_id   = emp["emp_id"]
        shift_name = shift_map.get(emp_id)
        if not shift_name or shift_name not in SHIFTS:
            shift_name = DEFAULT_SHIFT

        basic_salary = _employee_basic_salary_value(emp)

        s = _calculate_salary_from_bulk(
            emp          = emp,
            shift_name   = shift_name,
            basic_salary = basic_salary,
            att_records  = att_map.get(emp_id, []),
            leave_docs   = leave_map.get(emp_id, []),
            holiday_set  = holiday_set,
            salary_period = salary_period,
            ot_multiplier = ot_multiplier,
            min_ot_minutes = min_ot_minutes,
            salary_history = salary_history_map.get(emp_id, []),
            shift_assignment = shift_doc_map.get(emp_id),
        )
        if s:
            results.append(s)
    return results



def save_salary_summaries(year_month, summaries, generated_by="system"):
    """Stores one salary summary document per employee/month in MongoDB."""
    if not year_month:
        year_month = _app_trusted_now().strftime("%Y-%m")
    saved_at = _app_now_stamp()
    saved = 0
    for summary in summaries or []:
        emp_id = str(summary.get("emp_id", "")).strip()
        if not emp_id:
            continue
        doc = dict(summary)
        doc["emp_id"] = emp_id
        doc["month"] = year_month
        doc["generated_by"] = generated_by
        doc["saved_at"] = saved_at
        doc["record_type"] = "salary_report"
        salary_col.update_one(
            {"emp_id": emp_id, "month": year_month},
            {"$set": doc},
            upsert=True,
        )
        saved += 1
    return saved
