"""Pure comparison tests for the Fabric post-Gold notebook."""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "fabric/notebooks/src/gold/nb_gold_serving_health.py"
spec = importlib.util.spec_from_file_location("nb_gold_serving_health", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GoldServingHealthTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 29, 16, 30, tzinfo=timezone.utc)
        self.gold = {
            "AuditTime": self.now - timedelta(minutes=15),
            "Sales": Decimal("24310119958.77"),
            "Lines": 15000996,
            "Orders": 5007873,
            "SLA": 4756908,
        }
        self.model = {**self.gold, "AuditTime": self.gold["AuditTime"].isoformat()}

    def test_matching_consumer_and_warehouse_pass(self):
        self.assertEqual(module.compare(self.gold, self.model, self.now, 180), [])

    def test_semantic_version_mismatch_fails_even_with_same_metrics(self):
        self.model["AuditTime"] = (self.now - timedelta(hours=1)).isoformat()
        self.assertIn("semantic_audit_version_mismatch", module.compare(self.gold, self.model, self.now, 180))

    def test_stale_gold_publication_fails(self):
        self.gold["AuditTime"] = self.now - timedelta(hours=4)
        self.model["AuditTime"] = self.gold["AuditTime"].isoformat()
        self.assertIn("gold_publication_stale", module.compare(self.gold, self.model, self.now, 180))

    def test_sales_tolerance_and_exact_denominator(self):
        self.model["Sales"] = Decimal("24310119958.779")
        self.assertEqual(module.compare(self.gold, self.model, self.now, 180), [])
        self.model["Lines"] -= 1
        self.assertIn("lines_mismatch", module.compare(self.gold, self.model, self.now, 180))


if __name__ == "__main__":
    unittest.main()
