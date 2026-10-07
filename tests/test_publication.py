"""Regression checks for safe, credential-free publication."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_publication", ROOT / "scripts/check_publication.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationTests(unittest.TestCase):
    def check_file(self, name, content):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
            with patch.object(guard, "publishable_paths", return_value=[Path(name)]):
                return guard.check(root)

    def test_plain_python_passes(self):
        self.assertEqual(self.check_file("scripts/example.py", "value = 1\n")["status"], "passed")

    def test_dataset_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "forbidden publication path"):
            self.check_file("datasets/customer.csv", "customer_id\n1\n")

    def test_populated_environment_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "forbidden publication path"):
            self.check_file(".env", "EXAMPLE=value\n")

    def test_access_key_is_rejected_without_echoing_it(self):
        token = "AK" + "IA" + "A" * 16
        with self.assertRaises(RuntimeError) as result:
            self.check_file("example.txt", token)
        self.assertIn("aws-access-key", str(result.exception))
        self.assertNotIn(token, str(result.exception))

    def test_password_in_uri_is_rejected(self):
        uri = "postgresql://" + "user:temporary-test-value@localhost/db"
        with self.assertRaisesRegex(RuntimeError, "embedded-postgres-password"):
            self.check_file("example.txt", uri)

    def test_example_environment_is_allowed(self):
        self.assertEqual(self.check_file(".env.example", "POSTGRES_DSN=\n")["status"], "passed")

    def test_new_documentation_links_resolve(self):
        import re
        from urllib.parse import unquote

        names = ["README.md", "CONTRIBUTING.md", "docs/README.md", "docs/architecture.md",
                 "docs/project-walkthrough.md", "docs/metrics.md", "docs/getting-started.md",
                 "docs/delivery.md", "docs/debugging.md", "docs/implementation-status.md"]
        for name in names:
            source = ROOT / name
            for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", source.read_text()):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                path = source.parent / unquote(target.split("#", 1)[0])
                self.assertTrue(path.exists(), f"Broken link in {name}: {target}")
