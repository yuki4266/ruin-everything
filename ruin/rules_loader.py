"""Load one validated rule snapshot at the beginning of each site workflow."""

import asyncio
import json
import os
import re
import tempfile
from http.client import HTTPException
from pathlib import Path
from urllib.request import urlopen

import regex
from filelock import FileLock, Timeout

BUNDLED = Path(__file__).with_name("rules") / "sites.json"
SOURCE = "https://raw.githubusercontent.com/yuki4266/ruin-everything/main/ruin/rules/sites.json"
LIMIT = 32768
# The adapters need simple CSS selectors. Playwright's visibility suffix is local to its locators.
ATTRIBUTE = r'''\[[\w-]+(?:[*^$~|]?=(?:"[^"\\\]\n]+"|'[^'\\\]\n]+'|[\w-]+)(?: i)?)?\]'''
SELECTOR = re.compile(rf"(?:[a-z][\w-]*(?:{ATTRIBUTE})*|(?:{ATTRIBUTE})+)(?::visible)?")
FIELDS = {"ashby": {"status", "heading", "message"}, "outlook": {"rows", "body"},
          "greenhouse": {"code_field", "code_pattern"}}


def validate(raw: bytes):
    if len(raw) > LIMIT:
        raise ValueError("Rules exceed the size limit.")
    data = json.loads(raw)
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != 1:
        raise ValueError("Unsupported site rule schema.")
    for site, keys in FIELDS.items():
        group = data.get(site)
        if not isinstance(group, dict) or group.keys() != keys:
            raise ValueError(f"Incomplete rules for {site}.")
        for name, value in group.items():
            if not isinstance(value, str) or not 0 < len(value) <= 1024:
                raise ValueError(f"Invalid {site} rule.")
            if name == "code_pattern":
                if regex.compile(value, regex.I).groups != 1:
                    raise ValueError("The code pattern requires one capture group.")
            elif (any(not SELECTOR.fullmatch(part.strip()) for part in value.split(",")) or
                  (site == "ashby" and ":visible" in value)):
                raise ValueError(f"Unsupported selector for {site}.")
    return data


def snapshot(cache: Path):
    defaults = validate(BUNDLED.read_bytes())
    if os.environ.get("RUIN_RULE_UPDATES", "1") == "0":
        return defaults
    try:
        cache.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with FileLock(str(cache) + ".lock", timeout=0):
            with urlopen(SOURCE, timeout=2) as response:
                raw = response.read(LIMIT + 1)
            validated = validate(raw)
            with tempfile.NamedTemporaryFile(dir=cache.parent, delete=False) as tmp:
                tmp_path = Path(tmp.name)
                try:
                    tmp.write(raw)
                    tmp.close()
                    tmp_path.replace(cache)
                finally:
                    tmp_path.unlink(missing_ok=True)
            return validated
    except (OSError, HTTPException, ValueError, RecursionError, regex.error, Timeout):
        try:
            with cache.open("rb") as fh:
                return validate(fh.read(LIMIT + 1))
        except (OSError, ValueError, RecursionError, regex.error):
            return defaults


async def load_rules():
    return await asyncio.to_thread(snapshot, Path.home() / ".ruin" / "sites.json")
