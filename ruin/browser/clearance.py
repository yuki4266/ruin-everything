"""Private, profile-bound backup of unexpired site-issued clearance cookies only."""

import hashlib
import json
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from filelock import FileLock

SNAPSHOT = Path.home() / '.ruin' / 'cookies_snapshot.json'
FIELDS = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite', 'partitionKey'}


def matches(cookie, site):
    url = urlsplit(site)
    domain = cookie.get('domain', '')
    host = url.hostname or ''
    return (url.scheme == 'https' and cookie.get('name') == 'cf_clearance' and
            bool(cookie.get('value')) and cookie.get('secure') is True and
            isinstance(cookie.get('expires'), (float, int)) and cookie['expires'] > time.time() and
            bool(domain.lstrip('.')) and
            (host == domain.lstrip('.') or (domain.startswith('.') and host.endswith(domain))) and
            cookie.get('path', '').startswith('/'))


def read_snapshot(path):
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise RuntimeError('The clearance snapshot must be a private regular file (mode 0600).')
    if path.stat().st_size > 16_000_000:
        raise RuntimeError('The clearance snapshot is too large.')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError('The clearance snapshot must contain a JSON object.')
    return data


async def identity(context):
    profile = getattr(context, 'ruin_profile', None)
    if profile is None:
        return None
    session = await context.browser.new_browser_cdp_session()
    try:
        version = await session.send('Browser.getVersion')
    finally:
        await session.detach()
    return hashlib.sha256((str(Path(profile).resolve()) + '\n' + version['userAgent']).encode()).hexdigest()


async def save_clearance(context, site, path=None):
    key = await identity(context)
    if key is None:
        return 0
    cookies = [{k: v for k, v in c.items() if k in FIELDS}
               for c in await context.cookies([site]) if matches(c, site)]
    if not cookies:
        return 0  # A successful Turnstile usually issues a token, not this cookie.
    path = Path(path) if path else SNAPSHOT
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with FileLock(str(path) + '.lock', timeout=5):
        data = read_snapshot(path)
        clearance = data.get('ruin_clearance', {})
        records = clearance.get('sites', {}) if clearance.get('identity') == key else {}
        origin = 'https://' + urlsplit(site).netloc
        records[origin] = cookies
        with NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                # Preserve pre-existing local snapshot contents without importing
                # any unrelated login cookies from them.
                data['ruin_clearance'] = {'version': 1, 'identity': key, 'sites': records}
                json.dump(data, handle)
                handle.flush()
                os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    return len(cookies)


async def restore_clearance(context, path=None):
    path = Path(path) if path else SNAPSHOT
    if not path.exists():
        return 0
    data = read_snapshot(path).get('ruin_clearance', {})
    if data.get('version') != 1 or data.get('identity') != await identity(context):
        return 0
    current = await context.cookies()
    existing = {(c['name'], c['domain'], c['path'], str(c.get('partitionKey'))) for c in current
                if c['expires'] == -1 or c['expires'] > time.time()}
    restored = []
    for site, cookies in data.get('sites', {}).items():
        for cookie in cookies:
            ident = (cookie.get('name'), cookie.get('domain'), cookie.get('path'), str(cookie.get('partitionKey')))
            if matches(cookie, site) and ident not in existing:
                restored.append({k: v for k, v in cookie.items() if k in FIELDS})
                existing.add(ident)
    if restored:
        await context.add_cookies(restored)
    return len(restored)
