"""Local-only fixtures exercise capture, tenant isolation and session restoration."""
import asyncio
import json
import tempfile
import unittest
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import ElementHandle, async_playwright

from ruin.auth.local_vault import LocalVault, PrivateJSON
from ruin.auth.vault_runtime import VaultRuntime
from ruin.auth.vault_login import resume_vault_login, wait_for_manual_login
from ruin.browser.background import AgentTabs

FORM = '''<form action=/accepted method=post><input name=username autocomplete=username>
<input type=password name=password><button>Sign In</button></form>'''


class VaultFileTests(unittest.TestCase):
    def test_atomic_private_exact_tenant_and_root_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = LocalVault(root)
            vault.save('https://planview.icims.com/login', 'person', 'fixture-only')
            self.assertEqual(vault.lookup('https://planview.icims.com/')['username'], 'person')
            self.assertIsNone(vault.lookup('https://other.icims.com/'))
            self.assertIsNone(vault.lookup('https://planview.icims.com.evil.test/'))
            self.assertIsNone(vault.lookup('http://planview.icims.com/'))
            self.assertEqual(vault.file.path.stat().st_mode & 0o777, 0o600)
            vault.file.update(lambda data: data.update({'example.co.uk': {
                'username': 'root', 'password': 'fixture-root'}}))
            self.assertEqual(vault.lookup('https://login.example.co.uk/')['username'], 'root')
            self.assertIsNone(vault.lookup('https://other.co.uk/'))

    def test_symlink_and_corrupt_file_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            target.write_text('unchanged')
            path = root / 'auth_vault.json'
            path.symlink_to(target)
            with self.assertRaises(OSError):
                LocalVault(root).save('https://example.com', 'u', 'p')
            path.unlink()
            path.write_text('invalid')
            with self.assertRaisesRegex(RuntimeError, 'not overwritten'):
                LocalVault(root).save('https://example.com', 'u', 'p')
            self.assertEqual(path.read_text(), 'invalid')


class VaultBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('ruin.browser.actions.PROFILE', self.root / 'chrome'))
        driver = await self.enterAsyncContext(async_playwright())
        self.browser = await driver.chromium.launch()
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context()
        self.context.ruin_agent_tabs = AgentTabs(self.root / 'tabs.json')
        await self.context.route('**/*', lambda r: r.fulfill(content_type='text/html', body=FORM))
        await self.context.route('**/accepted', lambda r: r.fulfill(content_type='text/html', body='<main>Signed in</main>'))
        self.page = await self.context.new_page()
        await self.page.goto('https://outer.test/')
        self.runtime = VaultRuntime(self.context, self.root)
        await self.runtime.install()

    async def captured(self, host):
        async with asyncio.timeout(5):
            while not self.runtime.vault.lookup('https://' + host):
                await asyncio.sleep(.02)
        return self.runtime.vault.lookup('https://' + host)

    async def test_capture_submit_enter_click_existing_and_future_documents(self):
        for index, event in enumerate(['submit', 'Enter', 'click']):
            await self.page.goto(f'https://tenant{index}.icims.com/')
            await self.page.locator('[name=username]').fill('fixture-user')
            await self.page.locator('[type=password]').fill('fixture-secret')
            if event == 'submit':
                await self.page.locator('form').evaluate('e => e.requestSubmit()')
            elif event == 'Enter':
                await self.page.locator('[type=password]').press('Enter')
            else:
                await self.page.get_by_role('button').click()
            self.assertEqual((await self.captured(f'tenant{index}.icims.com'))['password'], 'fixture-secret')
            await self.page.wait_for_url('**/accepted')

    async def test_nested_cross_origin_and_new_page_capture(self):
        await self.context.route('https://middle.test/', lambda r: r.fulfill(content_type='text/html',
            body='<iframe id=icims_content_iframe src="https://planview.icims.com/"></iframe>'))
        page = await self.context.new_page()
        await page.goto('https://outer.test/')
        await page.set_content('<iframe src="https://middle.test/"></iframe>')
        frame = page.frame_locator('iframe').frame_locator('iframe')
        await frame.locator('[name=username]').fill('fixture-user')
        await frame.locator('[type=password]').fill('nested-secret')
        await frame.get_by_role('button').click()
        saved = await self.captured('planview.icims.com')
        self.assertEqual(saved['password'], 'nested-secret')
        self.assertIsNone(self.runtime.vault.lookup('https://outer.test'))
        self.assertIsNone(self.runtime.vault.lookup('https://middle.test'))

    async def test_empty_password_and_forged_hostname_do_not_capture(self):
        await self.page.get_by_role('button').click()
        await self.page.evaluate("__ruinCapture({host:'other.test', username:'u', password:'p'})")
        self.assertEqual(self.runtime.vault.file.read(), {})

    async def test_auto_login_executor_and_repeat_limit(self):
        self.runtime.vault.save(self.page.url, 'fixture-user', 'saved-secret')
        await self.page.locator('form').evaluate('e => e.onsubmit = event => event.preventDefault()')
        async def execute(page, button):
            await button.click()
        with patch('ruin.browser.actions.click', side_effect=execute) as clicked:
            result = await resume_vault_login(self.page, self.root)
            clicked.assert_awaited_once()
            self.assertNotIn('saved-secret', str(result))
            self.assertEqual(await self.page.locator('[type=password]').input_value(), 'saved-secret')
            await self.page.locator('[type=password]').fill('')
            self.assertEqual((await resume_vault_login(self.page, self.root))['state'], 'vault_retry_limited')
            clicked.assert_awaited_once()

    async def test_autofill_excludes_signup_and_cross_origin_actions(self):
        self.runtime.vault.save(self.page.url, 'fixture-user', 'saved-secret')
        for form in [FORM.replace('type=password', 'type=password autocomplete=new-password'),
                     FORM.replace('action=/accepted', 'action=https://other.test/accepted')]:
            await self.page.set_content(form)
            with patch('ruin.browser.actions.click') as clicked:
                self.assertIsNone(await resume_vault_login(self.page, self.root))
                clicked.assert_not_called()

    async def test_navigation_during_username_fill_cannot_receive_password(self):
        self.runtime.vault.save(self.page.url, 'fixture-user', 'saved-secret')
        original_fill = ElementHandle.fill
        async def navigate_after_username(handle, value, **kwargs):
            await original_fill(handle, value, **kwargs)
            if value == 'fixture-user':
                await self.page.goto('https://different.test/')
        with patch.object(ElementHandle, 'fill', navigate_after_username), patch('ruin.browser.actions.click') as clicked:
            result = await resume_vault_login(self.page, self.root)
            self.assertEqual(result['state'], 'vault_login_pending')
            self.assertEqual(await self.page.locator('[type=password]').input_value(), '')
            self.assertNotIn('saved-secret', str(result))
            clicked.assert_not_called()

    async def test_snapshot_restores_session_cookies_and_web_storage(self):
        await self.context.add_cookies([{'name': 'session', 'value': 'fixture-cookie',
            'domain': 'outer.test', 'path': '/', 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}])
        await self.page.evaluate("localStorage.setItem('login','fixture-local'); sessionStorage.setItem('login','fixture-tab')")
        await self.runtime.backup()
        self.assertEqual(self.runtime.snapshot.path.stat().st_mode & 0o777, 0o600)
        await self.context.clear_cookies()
        await self.page.evaluate('localStorage.clear(); sessionStorage.clear()')
        await self.runtime.restore()
        cookies = await self.context.cookies()
        self.assertEqual(cookies[0]['value'], 'fixture-cookie')
        self.assertEqual(cookies[0]['expires'], -1)
        self.assertTrue(cookies[0]['httpOnly'])
        self.assertEqual(await self.page.evaluate("[localStorage.getItem('login'),sessionStorage.getItem('login')]"),
                         ['fixture-local', 'fixture-tab'])
        await self.context.clear_cookies()
        await self.page.evaluate('localStorage.clear(); sessionStorage.clear()')
        await self.runtime.backup()
        await self.runtime.restore()
        self.assertEqual(await self.context.cookies(), [])
        self.assertEqual(await self.page.evaluate('localStorage.length + sessionStorage.length'), 0)

    async def test_session_storage_does_not_cross_tabs(self):
        other = await self.context.new_page()
        await other.goto('https://outer.test/second')
        await self.page.evaluate("sessionStorage.setItem('account','first')")
        await other.evaluate("sessionStorage.setItem('account','second')")
        await self.runtime.backup()
        for page in [self.page, other]:
            await page.evaluate('sessionStorage.clear()')
        await self.runtime.restore()
        self.assertEqual(await self.page.evaluate("sessionStorage.getItem('account')"), 'first')
        self.assertEqual(await other.evaluate("sessionStorage.getItem('account')"), 'second')

    async def test_manual_login_resumes_active_waiter(self):
        task = asyncio.create_task(wait_for_manual_login(self.page, 3))
        await self.page.locator('[name=username]').fill('fixture-user')
        await self.page.locator('[type=password]').fill('manual-secret')
        await self.page.get_by_role('button').click()
        self.assertTrue(await task)
        self.assertEqual((await self.captured('outer.test'))['password'], 'manual-secret')


class VaultServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_survives_client_exit_and_browser_restart(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        endpoint = f'http://127.0.0.1:{port}'
        driver = await self.enterAsyncContext(async_playwright())
        async def launch():
            context = await driver.chromium.launch_persistent_context(root / 'profile',
                args=[f'--remote-debugging-port={port}'])
            self.addAsyncCleanup(context.close)
            await context.route('https://fixture.test/**', lambda r: r.fulfill(content_type='text/html', body=FORM))
            await context.pages[0].goto('https://fixture.test/')
            return context
        context = await launch()
        worker = subprocess.Popen([sys.executable, '-m', 'ruin.auth.vault_runtime', endpoint, str(root / 'vault')],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup():
            worker.terminate()
            worker.wait(timeout=10)
        self.addCleanup(cleanup)
        status = PrivateJSON(root / 'vault' / 'vault_status.json')
        async def until(predicate):
            async with asyncio.timeout(20):
                while not predicate():
                    await asyncio.sleep(.05)
        await until(lambda: status.read().get('ready'))
        generation = status.read()['browser']
        # An independent short-lived CLI-like client disconnects; the daemon remains.
        async with async_playwright() as transient:
            client = await transient.chromium.connect_over_cdp(endpoint)
            await client.contexts[0].pages[0].reload()
        page = context.pages[0]
        await page.locator('[name=username]').fill('fixture-user')
        await page.locator('[type=password]').fill('daemon-secret')
        await page.locator('form').evaluate('e => e.onsubmit = event => event.preventDefault()')
        await page.get_by_role('button').click()
        vault = LocalVault(root / 'vault')
        await until(lambda: vault.lookup('https://fixture.test/'))
        self.assertEqual(vault.lookup('https://fixture.test/')['password'], 'daemon-secret')
        worker.terminate()
        worker.wait(timeout=10)
        old_pid = status.read()['pid']
        worker = subprocess.Popen([sys.executable, '-m', 'ruin.auth.vault_runtime', endpoint, str(root / 'vault')],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await until(lambda: status.read().get('ready') and status.read().get('pid') != old_pid)
        await page.locator('[type=password]').fill('reconnected-secret')
        await page.get_by_role('button').click()
        await until(lambda: vault.lookup('https://fixture.test/')['password'] == 'reconnected-secret')
        await context.add_cookies([{'name':'session', 'value':'daemon-cookie', 'url':'https://fixture.test/'}])
        snapshot = PrivateJSON(root / 'vault' / 'cookies_snapshot.json')
        await until(lambda: any(c['name'] == 'session' for c in snapshot.read().get('cookies', [])))
        await context.close()
        context = await launch()
        await until(lambda: status.read().get('ready') and status.read().get('browser') != generation)
        self.assertTrue(any(c['value'] == 'daemon-cookie' for c in await context.cookies()))
        # Capture is reinstalled in the new browser, including future documents.
        page = context.pages[0]
        await page.reload()
        await page.locator('[name=username]').fill('fixture-user')
        await page.locator('[type=password]').fill('updated-secret')
        await page.get_by_role('button').click()
        await until(lambda: vault.lookup('https://fixture.test/')['password'] == 'updated-secret')


if __name__ == '__main__':
    unittest.main()
