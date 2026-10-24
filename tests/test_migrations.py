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

    def test_remote_migration_versions_are_represented_locally(self):
        expected = {
            "20261015112619", "20261015120014", "20261018094039",
            "20261018100502", "20261021102333", "20261021105220",
            "20261021111154", "20261021112101", "20261024131139",
            "20261024132027", "20261024132036",
        }
        actual = {path.name[:14] for path in MIGRATIONS.glob("*.sql")}
        self.assertTrue(expected.issubset(actual), f"Missing local migration versions: {sorted(expected - actual)}")

    def test_historical_markers_are_explicitly_documented(self):
        marker = (MIGRATIONS / "20261015112619_commitment_radar_initial_schema.sql").read_text(encoding="utf-8")
        self.assertIn("Historical migration marker", marker)
        docs = (MIGRATIONS.parents[1] / "docs" / "SUPABASE_MIGRATION_HISTORY.md").read_text(encoding="utf-8")
        self.assertIn("original migration SQL bodies were not present", docs)
        self.assertIn("deliberate final-state baseline", docs)

    def test_supabase_cli_config_is_present(self):
        config = (MIGRATIONS.parent / "config.toml").read_text(encoding="utf-8")
        self.assertIn('project_id = "crash-feed-inspector"', config)

    def test_round_schema_matches_observed_supabase_column_contract(self):
        sql = (MIGRATIONS / "20261024132027_create_crash_rounds.sql").read_text(encoding="utf-8")
        self.assertIn("create table if not exists public.crash_rounds", sql.lower())
        self.assertIn("occurred_at timestamptz", sql.lower())
        self.assertIn("multiplier numeric(12, 4)", sql.lower())
        self.assertNotIn("timestamp_utc", sql.lower())
        self.assertIn("source_event_sha256", sql.lower())
        self.assertIn("enable row level security", sql.lower())
        self.assertIn("revoke all on table public.crash_rounds from anon, authenticated", sql.lower())

    def test_prediction_migration_does_not_redefine_round_table(self):
        sql = (MIGRATIONS / "20261024132036_crash_research_ledger.sql").read_text(encoding="utf-8")
        self.assertIn("create table if not exists public.crash_predictions", sql.lower())
        self.assertIsNone(re.search(r"create\s+table\s+(if\s+not\s+exists\s+)?public\.crash_rounds", sql, re.I))
        self.assertIn("crash_predictions_evaluated_multiplier_finite_check", sql)
        self.assertIn("enable row level security", sql.lower())
        self.assertIn("revoke all on table public.crash_predictions from anon, authenticated", sql.lower())


if __name__ == "__main__":
    unittest.main()
