from datetime import date, timedelta


def calculate_prorated_salary(
    default_salary, revisions, period_start, period_end, full_period_days,
):
    """Prorate monthly salary by active calendar day and effective revision."""
    start = date.fromisoformat(str(period_start))
    end = date.fromisoformat(str(period_end))
    full_period_days = max(int(full_period_days or 0), 1)
    default_salary = float(default_salary or 0)

    normalized = []
    for revision in revisions or []:
        try:
            effective_date = date.fromisoformat(str(revision.get("effective_from", ""))[:10])
            salary = float(revision.get("basic_salary", 0) or 0)
        except (TypeError, ValueError):
            continue
        normalized.append((
            effective_date,
            str(revision.get("created_at", "")),
            salary,
        ))
    normalized.sort(key=lambda item: (item[0], item[1]))

    total = 0.0
    current = start
    while current <= end:
        daily_salary = default_salary
        for effective_date, _, salary in normalized:
            if effective_date > current:
                break
            daily_salary = salary
        total += daily_salary / full_period_days
        current += timedelta(days=1)
    return round(total, 2)


def calculate_payroll_amounts(
    basic_salary, working_days, shift_hours, days_absent=0.0,
    days_halfday=0.0, total_late_min=0, total_early_min=0,
    total_ot_hrs=0.0, ot_multiplier=1.5,
):
    """Return payroll rates and amounts using one consistent rate basis."""
    effective_days = max(float(working_days or 0), 1.0)
    shift_hours = max(float(shift_hours or 0), 1.0)
    basic_salary = float(basic_salary or 0)

    per_day_rate = basic_salary / effective_days
    hourly_rate = per_day_rate / shift_hours
    per_min_rate = hourly_rate / 60
    ot_rate = hourly_rate * max(float(ot_multiplier or 0), 0)

    absent_deduction = round(float(days_absent or 0) * per_day_rate, 2)
    halfday_deduction = round(float(days_halfday or 0) * per_day_rate * 0.5, 2)
    late_deduction = round(float(total_late_min or 0) * per_min_rate, 2)
    early_exit_deduction = round(float(total_early_min or 0) * per_min_rate, 2)
    ot_pay = round(float(total_ot_hrs or 0) * ot_rate, 2)
    attendance_deductions = round(
        absent_deduction + halfday_deduction
        + late_deduction + early_exit_deduction,
        2,
    )
    gross_salary = round(basic_salary + ot_pay, 2)
    net_salary = round(gross_salary - attendance_deductions, 2)

    return {
        "per_day_rate": per_day_rate,
        "per_min_rate": per_min_rate,
        "hourly_rate": hourly_rate,
        "ot_rate": ot_rate,
        "absent_deduction": absent_deduction,
        "halfday_deduction": halfday_deduction,
        "late_deduction": late_deduction,
        "early_exit_deduction": early_exit_deduction,
        "ot_pay": ot_pay,
        "attendance_deductions": attendance_deductions,
        "gross_salary": gross_salary,
        "net_salary": net_salary,
    }
