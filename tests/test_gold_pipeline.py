"""Regression checks for the Gold build and publication safety contract."""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_gold_pipeline import DEST, main, publication_sql  # noqa: E402


class GoldPipelineTests(unittest.TestCase):
    def test_candidate_audit_precedes_live_publication(self):
        main()
        properties = json.loads(DEST.read_text())["properties"]
        self.assertEqual(properties["concurrency"], 1)
        activities = properties["activities"]
        by_name = {activity["name"]: activity for activity in activities}
        self.assertIn("AuditGoldCandidate", by_name)
        self.assertEqual(
            by_name["PublishGoldAtomically"]["dependsOn"],
            [{"activity": "AuditGoldCandidate", "dependencyConditions": ["Succeeded"]}],
        )
        self.assertEqual(
            by_name["VerifyPublishedGold"]["dependsOn"],
            [{"activity": "PublishGoldAtomically", "dependencyConditions": ["Succeeded"]}],
        )
        serialized = json.dumps(activities).lower()
        self.assertNotIn("drop table if exists gold.", serialized)
        self.assertIn("drop table if exists gold_build.", serialized)

    def test_publication_checks_columns_and_rolls_back_on_error(self):
        sql = publication_sql()
        self.assertIn("sys.columns", sql)
        self.assertIn("BEGIN TRANSACTION", sql)
        self.assertIn("ROLLBACK TRANSACTION", sql)
        self.assertIn("INSERT INTO gold.fact_sales SELECT * FROM gold_build.fact_sales", sql)


if __name__ == "__main__":
    unittest.main()
