import unittest

from payroll_math import calculate_payroll_amounts, calculate_prorated_salary


class PayrollAmountTests(unittest.TestCase):
    def test_mid_month_salary_revision_is_prorated(self):
        salary = calculate_prorated_salary(
            default_salary=20000,
            revisions=[
                {
                    "basic_salary": 20000,
                    "effective_from": "2026-06-01",
                    "created_at": "2026-06-01 09:00:00",
                },
                {
                    "basic_salary": 30000,
                    "effective_from": "2026-06-15",
                    "created_at": "2026-06-10 09:00:00",
                },
            ],
            period_start="2026-06-01",
            period_end="2026-06-30",
            full_period_days=30,
        )

        self.assertAlmostEqual(salary, 25333.33)

    def test_joining_date_proration_uses_active_period_only(self):
        salary = calculate_prorated_salary(
            default_salary=30000,
            revisions=[],
            period_start="2026-06-15",
            period_end="2026-06-30",
            full_period_days=30,
        )

        self.assertEqual(salary, 16000)

    def test_ot_deductions_and_net_salary_use_same_working_day_basis(self):
        amounts = calculate_payroll_amounts(
            basic_salary=24000,
            working_days=24,
            shift_hours=8,
            days_absent=1,
            days_halfday=1,
            total_late_min=60,
            total_early_min=30,
            total_ot_hrs=2,
            ot_multiplier=1.5,
        )

        self.assertAlmostEqual(amounts["per_day_rate"], 1000)
        self.assertAlmostEqual(amounts["hourly_rate"], 125)
        self.assertAlmostEqual(amounts["absent_deduction"], 1000)
        self.assertAlmostEqual(amounts["halfday_deduction"], 500)
        self.assertAlmostEqual(amounts["late_deduction"], 125)
        self.assertAlmostEqual(amounts["early_exit_deduction"], 62.50)
        self.assertAlmostEqual(amounts["ot_pay"], 375)
        self.assertAlmostEqual(amounts["attendance_deductions"], 1687.50)
        self.assertAlmostEqual(amounts["gross_salary"], 24375)
        self.assertAlmostEqual(amounts["net_salary"], 22687.50)

    def test_no_attendance_adjustments_returns_basic_salary(self):
        amounts = calculate_payroll_amounts(
            basic_salary=20000,
            working_days=25,
            shift_hours=8,
        )

        self.assertEqual(amounts["ot_pay"], 0)
        self.assertEqual(amounts["attendance_deductions"], 0)
        self.assertEqual(amounts["gross_salary"], 20000)
        self.assertEqual(amounts["net_salary"], 20000)

    def test_zero_salary_returns_zero_amounts(self):
        amounts = calculate_payroll_amounts(
            basic_salary=0,
            working_days=25,
            shift_hours=8,
            days_absent=2,
            total_ot_hrs=5,
        )

        self.assertEqual(amounts["attendance_deductions"], 0)
        self.assertEqual(amounts["ot_pay"], 0)
        self.assertEqual(amounts["net_salary"], 0)


if __name__ == "__main__":
    unittest.main()
