"""Engine selection must be explicit and shared with the vault daemon."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ruin.browser import driver


class DriverSelectionTests(unittest.TestCase):
    def test_persistent_setting_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / 'engine.json'
            settings.write_text(json.dumps({'engine': 'patchright'}))
            with patch.object(driver, 'SETTINGS', settings), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(driver.engine_name(), 'patchright')
                with patch.dict(os.environ, {'RUIN_BROWSER_ENGINE': 'playwright'}):
                    self.assertEqual(driver.engine_name(), 'playwright')
                settings.write_text('{"engine":"typo"}')
                with self.assertRaises(ValueError):
                    driver.engine_name()

    def test_patchright_uses_consistent_error_types(self):
        import importlib.util
        if not importlib.util.find_spec('patchright'):
            self.skipTest('Optional Patchright extra is not installed')
        script = '''
from ruin.browser.driver import ENGINE, Error, TimeoutError
from ruin.browser import actions, turnstile, background
from ruin.auth import vault_runtime
assert ENGINE == 'patchright'
assert issubclass(TimeoutError, Error)
assert all(m.Error is Error for m in (actions, turnstile, background, vault_runtime))
assert vault_runtime.ENGINE == ENGINE
'''
        subprocess.run([sys.executable, '-c', script], check=True, timeout=10,
                       env={**os.environ, 'RUIN_BROWSER_ENGINE': 'patchright'})
