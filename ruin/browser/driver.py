"""Select one API consistently for browser tasks and the persistent vault service."""

import importlib
import json
import os
from pathlib import Path

SETTINGS = Path.home() / '.ruin-everything' / 'browser-engine.json'


def engine_name():
    value = os.getenv('RUIN_BROWSER_ENGINE')
    if value is None:
        value = json.loads(SETTINGS.read_text()).get('engine', 'playwright') if SETTINGS.exists() else 'playwright'
    if value not in {'playwright', 'patchright'}:
        raise ValueError('RUIN_BROWSER_ENGINE must be playwright or patchright.')
    return value


ENGINE = engine_name()
try:
    _api = importlib.import_module(f'{ENGINE}.async_api')
except ModuleNotFoundError as exc:
    raise RuntimeError(f'Install the selected {ENGINE} browser dependency before connecting.') from exc


def __getattr__(name):
    return getattr(_api, name)
