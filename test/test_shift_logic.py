import importlib
import sys
import types
import unittest
from unittest.mock import patch


class _Collection:
    def create_index(self, *args, **kwargs):
        return None


class _Database:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, _Collection())


fake_db = _Database()
fake_db_config = types.ModuleType("db_config")
fake_db_config.db = fake_db
fake_db_config.employees_col = _Collection()
sys.modules.setdefault("db_config", fake_db_config)

shift_model = importlib.import_module("shift_model")


class SalaryPeriodTests(unittest.TestCase):
    def test_short_month_cycle_does_not_overlap_next_period(self):
        february = shift_model._salary_period_for_month("2026-02", 31)
        march = shift_model._salary_period_for_month("2026-03", 31)

        self.assertEqual(february["start_date"], "2026-01-31")
        self.assertEqual(february["end_date"], "2026-02-27")
        self.assertEqual(march["start_date"], "2026-02-28")
        self.assertEqual(march["end_date"], "2026-03-30")


class OvernightShiftTests(unittest.TestCase):
    def test_after_midnight_checkin_uses_previous_night_shift_start(self):
        with patch.object(shift_model, "get_employee_shift", return_value="Night"):
            metrics = shift_model.calculate_shift_metrics(
                1,
                "00:00",
                "08:00",
                min_ot_minutes=120,
            )

        self.assertEqual(metrics["raw_late_mins"], 120)
        self.assertEqual(metrics["late_minutes"], 105)
        self.assertEqual(metrics["early_exit_minutes"], 0)
        self.assertEqual(metrics["overtime_hours"], 0)


if __name__ == "__main__":
    unittest.main()
