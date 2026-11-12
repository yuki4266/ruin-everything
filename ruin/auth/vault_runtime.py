"""Persistent local CDP capture and session backup, independent of CLI lifetimes."""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from filelock import FileLock, Timeout
from ruin.browser.driver import ENGINE, Error, async_playwright

from .local_vault import ROOT, LocalVault, PrivateJSON, hostname

CAPTURE = Path(__file__).with_name('capture_login.js').read_text()
STORAGE = """() => ({origin: location.origin,
    local: Object.fromEntries(Object.entries(localStorage)),
    session: Object.fromEntries(Object.entries(sessionStorage))})"""
RESTORE = """data => {
    const entry = data[location.origin];
    if (!entry) return;
    for (const [name, storage] of [['local', localStorage], ['session', sessionStorage]])
        if (storage.length === 0)
            for (const [key, value] of Object.entries(entry[name] || {})) storage.setItem(key, value);
}"""


class VaultRuntime:
    def __init__(self, context, root=ROOT):
        self.context = context
        self.vault = LocalVault(root)
        self.snapshot = PrivateJSON(Path(root) / 'cookies_snapshot.json')
        self.tasks = set()
        self.errors = 0
        self.dirty = asyncio.Event()

    async def captured(self, source, payload):
        try:
            # Frame URL comes from the CDP binding source, never a page-supplied hostname.
            if payload.get('host') != hostname(source['frame'].url):
                return
            self.vault.save(source['frame'].url, payload['username'], payload['password'])
            self.dirty.set()
        except (KeyError, TypeError, OSError, RuntimeError):
            self.errors += 1

    async def install(self, restore=False):
        if restore:
            await self.restore()
        await self.context.expose_binding('__ruinCapture', self.captured)
        # Chromium implements this with Page.addScriptToEvaluateOnNewDocument;
        # Playwright also installs it on out-of-process child frame targets.
        await self.context.add_init_script(CAPTURE)
        for page in self.context.pages:
            await self.attach(page)
        self.context.on('page', self.schedule_attach)

    def schedule_attach(self, page):
        task = asyncio.create_task(self.attach(page))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def attach(self, page):
        def changed(frame):
            self.dirty.set()
        page.on('framenavigated', changed)
        for frame in page.frames:
            try:
                await asyncio.wait_for(frame.evaluate(CAPTURE), timeout=2)
            except (Error, TimeoutError):
                pass

    async def backup(self):
        from ruin.browser.background import target_info
        params = await self.cookie_context()
        session = await self.context.browser.new_browser_cdp_session()
        try:
            cookies = (await session.send('Storage.getCookies', params))['cookies']
        finally:
            await session.detach()
        # Keep closed origins until next browser restart, but replace live origins
        # with their exact current state so logout/deletion is not undone.
        origins = self.snapshot.read().get('origins', {})
        tabs = {}
        for page in self.context.pages:
            try:
                target = (await target_info(page))['targetId']
            except Error:
                continue
            tabs[target] = {'url': page.url, 'origins': {}}
            for frame in page.frames:
                if not hostname(frame.url):
                    continue
                try:
                    state = await asyncio.wait_for(frame.evaluate(STORAGE), timeout=2)
                    origin = state.pop('origin')
                    origins[origin] = {'local': state['local']}
                    tabs[target]['origins'][origin] = {'session': state['session']}
                except (Error, TimeoutError):
                    continue
        self.snapshot.update(lambda data: data.update(cookies=cookies, origins=origins, tabs=tabs, saved_at=time.time()))

    async def cookie_context(self):
        from ruin.browser.background import target_info
        if self.context.pages:
            info = await target_info(self.context.pages[0])
            if info.get('browserContextId'):
                return {'browserContextId': info['browserContextId']}
        return {}

    async def restore(self):
        data = self.snapshot.read()
        params_context = await self.cookie_context()
        session = await self.context.browser.new_browser_cdp_session()
        allowed = {'name','value','url','domain','path','secure','httpOnly','sameSite','expires',
                   'priority','sameParty','sourceScheme','sourcePort','partitionKey'}
        try:
            current = (await session.send('Storage.getCookies', params_context))['cookies']
            identity = lambda c: (c['name'], c['domain'], c['path'], json.dumps(c.get('partitionKey'), sort_keys=True))
            existing = {identity(c) for c in current}
            for cookie in data.get('cookies', []):
                if identity(cookie) in existing or (cookie.get('expires', -1) > 0 and cookie['expires'] <= time.time()):
                    continue
                params = {k: v for k, v in cookie.items() if k in allowed}
                if cookie.get('session') or params.get('expires', -1) <= 0:
                    params.pop('expires', None)
                try:
                    await session.send('Storage.setCookies', {**params_context, 'cookies': [params]})
                except Error:
                    self.errors += 1
        finally:
            await session.detach()
        origins = data.get('origins', {})
        # Prime localStorage using an isolated background target, before any task
        # navigation. Do not clear existing context storage or visit real servers.
        if origins:
            from ruin.browser.background import new_agent_page
            page = await new_agent_page(self.context, purpose='vault-storage')
            try:
                await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=''))
                for origin, entry in origins.items():
                    if hostname(origin):
                        await page.goto(origin, wait_until='domcontentloaded')
                        await page.evaluate(RESTORE, {origin: {'local': entry.get('local', {})}})
            finally:
                await page.close()
        from ruin.browser.background import target_info
        self.restore_tabs = {}
        for page in self.context.pages:
            target = (await target_info(page))['targetId']
            saved = data.get('tabs', {}).get(target)
            if not saved:
                candidates = [tab for tab in data.get('tabs', {}).values() if tab['url'] == page.url]
                saved = candidates[0] if len(candidates) == 1 else None
            self.restore_tabs[page] = saved.get('origins', {}) if saved else {}
            for frame in page.frames:
                await self.restore_frame(frame)
            page.on('framenavigated', self.restore_frame)

    async def restore_frame(self, frame):
        from urllib.parse import urlsplit
        parsed = urlsplit(frame.url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        records = self.restore_tabs.get(frame.page, {})
        entry = records.pop(origin, None)
        if entry:
            try:
                await frame.evaluate(RESTORE, {origin: entry})
            except Error:
                records[origin] = entry

    async def run(self):
        while self.context.browser.is_connected():
            try:
                await asyncio.wait_for(self.dirty.wait(), timeout=5)
            except TimeoutError:
                pass
            self.dirty.clear()
            await asyncio.sleep(0.3)
            await self.backup()
            PrivateJSON(self.snapshot.path.parent / 'vault_status.json').update(
                lambda data: data.update(heartbeat=time.time(), errors=self.errors))


def browser_id(endpoint):
    with urlopen(endpoint.rstrip('/') + '/json/version', timeout=3) as response:
        return json.load(response)['webSocketDebuggerUrl'].rsplit('/', 1)[-1]


async def serve(endpoint, root=ROOT):
    root = Path(root)
    status = PrivateJSON(root / 'vault_status.json')
    try:
        with FileLock(root / 'vault_service.lock', timeout=0, mode=0o600):
            while True:
                try:
                    generation = await asyncio.to_thread(browser_id, endpoint)
                    async with async_playwright() as driver:
                        async with asyncio.timeout(20):
                            browser = await driver.chromium.connect_over_cdp(endpoint, no_defaults=True, timeout=15000)
                        runtime = VaultRuntime(browser.contexts[0], root)
                        await runtime.install(restore=status.read().get('browser') != generation)
                        status.update(lambda data: data.update(browser=generation, pid=os.getpid(), ready=True, engine=ENGINE))
                        await runtime.run()
                except (Error, OSError, RuntimeError, KeyError, ValueError, TimeoutError):
                    status.update(lambda data: data.update(ready=False))
                await asyncio.sleep(1)
    except Timeout:
        return


async def ensure_service(endpoint):
    """A detached singleton keeps capture alive after the calling CLI disconnects."""
    status = PrivateJSON(ROOT / 'vault_status.json')
    generation = await asyncio.to_thread(browser_id, endpoint)
    def ready():
        state = status.read()
        if state.get('pid', 0) <= 0:
            return False
        try:
            os.kill(state['pid'], 0)
        except (ProcessLookupError, PermissionError):
            return False
        return state.get('ready') and state.get('browser') == generation
    if ready():
        if status.read().get('engine', 'playwright') != ENGINE:
            raise RuntimeError('Local Auth Vault uses a different browser engine; restart that service first.')
        return
    subprocess.Popen([sys.executable, '-m', 'ruin.auth.vault_runtime', endpoint],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env={**os.environ, 'RUIN_AUTO_UPDATE': '0'})
    for _ in range(100):
        if ready():
            return
        await asyncio.sleep(0.1)
    raise RuntimeError('Local Auth Vault listener did not become ready.')


if __name__ == '__main__':
    asyncio.run(serve(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT))
