import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ruin.auth.identity_setup import normalize_numbers, save_profile


class IdentitySetupTest(unittest.TestCase):
    def test_local_numbers_and_default(self):
        entries, default = normalize_numbers([
            {"region": "US", "number": "(202) 555-0100"},
            {"region": "GB", "number": "020 7946 0018"},
        ], 1)
        self.assertEqual(entries[0]["number"], "+12025550100")
        self.assertEqual(default, "+442079460018")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile" / "identity.json"
            save_profile({"phone": default, "phone_numbers": entries}, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["phone"], default)
