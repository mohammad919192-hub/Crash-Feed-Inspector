import re
import unittest
from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


class MigrationContractTests(unittest.TestCase):
    def test_migration_names_use_fourteen_digit_versions(self):
        names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
        self.assertGreaterEqual(len(names), 2)
        for name in names:
            self.assertRegex(name, r"^\d{14}_[a-z0-9_]+\.sql$")

    def test_round_schema_matches_observed_supabase_column_contract(self):
        sql = (MIGRATIONS / "20261024150000_create_crash_rounds.sql").read_text(encoding="utf-8")
        self.assertIn("create table if not exists public.crash_rounds", sql.lower())
        self.assertIn("occurred_at timestamptz", sql.lower())
        self.assertIn("multiplier numeric(12, 4)", sql.lower())
        self.assertNotIn("timestamp_utc", sql.lower())
        self.assertIn("source_event_sha256", sql.lower())
        self.assertIn("enable row level security", sql.lower())
        self.assertIn("revoke all on table public.crash_rounds from anon, authenticated", sql.lower())

    def test_prediction_migration_does_not_redefine_round_table(self):
        sql = (MIGRATIONS / "20261024150100_crash_research_ledger.sql").read_text(encoding="utf-8")
        self.assertIn("create table if not exists public.crash_predictions", sql.lower())
        self.assertIsNone(re.search(r"create\s+table\s+(if\s+not\s+exists\s+)?public\.crash_rounds", sql, re.I))
        self.assertIn("crash_predictions_evaluated_multiplier_finite_check", sql)
        self.assertIn("enable row level security", sql.lower())
        self.assertIn("revoke all on table public.crash_predictions from anon, authenticated", sql.lower())


if __name__ == "__main__":
    unittest.main()
