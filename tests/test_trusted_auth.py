import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playwright.async_api import async_playwright

from ruin.auth.autofill import click_trusted_login, offer_chrome_login
from ruin.auth.trusted import load_trusted_oauth_clients, matches_action, origin_matches, origin_pattern, trusted_client


ORIGIN = 'https://app.test'
ACTION = {
    'origin': 'https://github.com', 'path': '/login/oauth/authorize',
    'kind': 'oauth', 'name': 'Authorize Example',
    'oauth': {'client_id': 'fixture', 'redirect_uri': ORIGIN + '/callback', 'scopes': ['read:user']},
}
URL = 'https://github.com/login/oauth/authorize?client_id=fixture&redirect_uri=https%3A%2F%2Fapp.test%2Fcallback&scope=read%3Auser'


class PolicyTest(unittest.TestCase):
    def test_wildcard_dns_boundaries_and_ports(self):
        pattern = 'https://*.myworkdayjobs.com'
        for url in ('https://company.myworkdayjobs.com/job', 'https://company.wd5.myworkdayjobs.com/job',
                    'https://company.wd5.myworkdayjobs.com:443/job'):
            self.assertTrue(origin_matches(pattern, url))
        for url in ('https://myworkdayjobs.com', 'https://evilmyworkdayjobs.com',
                    'https://tenant.myworkdayjobs.com.evil.test', 'http://tenant.myworkdayjobs.com',
                    'https://user@tenant.myworkdayjobs.com', 'https://tenant.myworkdayjobs.com:8443', 'https://tenant.myworkdayjobs.com:0',
                    'https://bad..myworkdayjobs.com', 'https://tenant.myworkdayjobs.com.'):
            self.assertFalse(origin_matches(pattern, url))
        for bad in ('https://*', 'https://*.com', 'https://*workdayjobs.com',
                    'https://*.foo.*.com', 'https://*.127.0.0.1', 'https://*.example.org/path'):
            with self.assertRaises(ValueError):
                origin_pattern(bad)

    def test_exact_and_narrower_rules_override_broad_rules(self):
        broad = {'origin': 'https://*.myworkdayjobs.com'}
        narrow = {'origin': 'https://*.wd5.myworkdayjobs.com'}
        exact = {'origin': 'https://company.wd5.myworkdayjobs.com'}
        url = exact['origin'] + '/job'
        self.assertIs(trusted_client([broad, narrow, exact], url), exact)
        self.assertIs(trusted_client([narrow, broad], url), narrow)
        broad['origin'] += ':443'
        self.assertIs(trusted_client([broad, narrow], url), narrow)

    def test_exact_oauth_request(self):
        self.assertTrue(matches_action(ACTION, URL))
        for changed in (
            URL.replace('github.com', 'github.com.evil.test'),
            URL.replace('fixture', 'other'),
            URL.replace('%2Fcallback', '%2Fother'),
            URL.replace('read%3Auser', 'read%3Auser%20repo'),
            URL + '&client_id=other',
            URL.replace('&scope=read%3Auser', ''),
        ):
            self.assertFalse(matches_action(ACTION, changed))

    def test_config_validation_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trusted-auth.json'
            self.assertEqual(load_trusted_oauth_clients(path), [])
            config = {'trusted_oauth_clients': [{'origin': ORIGIN, 'actions': [ACTION]}]}
            path.write_text(json.dumps(config))
            self.assertEqual(load_trusted_oauth_clients(path), config['trusted_oauth_clients'])
            for invalid in ('https://app.test/', 'https://app.test.evil/path', 'http://app.test'):
                bad = copy.deepcopy(config)
                bad['trusted_oauth_clients'][0]['origin'] = invalid
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    load_trusted_oauth_clients(path)
            path.write_text('{')
            with self.assertRaises(ValueError):
                load_trusted_oauth_clients(path)


class TrustedBrowserTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.driver = await async_playwright().start()
        self.browser = await self.driver.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL'))
        self.context = await self.browser.new_context()
        await self.context.route('**/*', lambda r: r.fulfill(content_type='text/html', body='<main></main>'))
        self.page = await self.context.new_page()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.driver.stop()

    async def test_oauth_click_requires_task_and_exact_request_and_unique_button(self):
        await self.page.goto(URL)
        clients = [{'origin': ORIGIN, 'actions': [ACTION]}]
        form = '<button onclick="window.clicked=true">Authorize Example</button>'
        await self.page.set_content(form)
        self.assertIsNone(await click_trusted_login(self.page, 'https://other.test', clients, set()))
        await self.page.goto(URL + '&scope=repo')
        await self.page.set_content(form)
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.goto(URL)
        await self.page.set_content(form + form)
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.set_content(form.replace('<button ', '<button disabled '))
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.set_content(form)
        attempted = set()
        self.assertEqual(await click_trusted_login(self.page, ORIGIN, clients, attempted), 'Authorize Example')
        self.assertTrue(await self.page.evaluate('window.clicked'))
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, attempted))

    async def test_password_keys_only_for_explicit_empty_same_origin_login(self):
        await self.page.goto(ORIGIN + '/login')
        clients = [{'origin': ORIGIN, 'chrome_password_dropdown': True}]
        form = '<form onsubmit="event.preventDefault()"><input type=password></form>'
        async def setup(html):
            await self.page.set_content(html)
            await self.page.evaluate("() => { window.keys=[];document.onkeydown=e=>window.keys.push(e.key); }")
        with patch('ruin.auth.autofill.credential', return_value=None):
            await setup(form)
            await offer_chrome_login(self.page, ORIGIN)
            self.assertEqual(await self.page.evaluate('window.keys'), [])
            await offer_chrome_login(self.page, ORIGIN, clients=clients)
            self.assertEqual(await self.page.evaluate('window.keys'), ['ArrowDown', 'Enter'])
            for html in (form.replace('type=password', 'type=password value=existing'),
                         form.replace('type=password', 'type=password autocomplete=new-password'),
                         form.replace('<form ', '<form action="https://other.test" ')):
                await setup(html)
                await offer_chrome_login(self.page, ORIGIN, clients=clients)
                self.assertEqual(await self.page.evaluate('window.keys'), [])
        with patch('ruin.auth.autofill.credential', return_value='fixture-only'):
            await setup(form)
            await offer_chrome_login(self.page, ORIGIN, clients=clients)
            self.assertEqual(await self.page.evaluate('window.keys'), [])

    async def test_login_waits_for_password_and_rejects_cross_origin_submission(self):
        await self.page.goto(ORIGIN + '/login')
        clients = [{'origin': ORIGIN, 'actions': [{'origin': ORIGIN, 'path': '/login',
                    'kind': 'login', 'name': 'Sign in'}]}]
        await self.page.set_content('<form><input type=password><button>Sign in</button></form>')
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.locator('input').fill('fixture-only')
        await self.page.locator('form').evaluate("el => el.action='https://other.test/'")
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.locator('form').evaluate("el => {el.action='/login';el.onsubmit=e=>e.preventDefault()}")
        self.assertEqual(await click_trusted_login(self.page, ORIGIN, clients, set()), 'Sign in')

    async def test_wildcard_rule_cannot_move_between_tenants(self):
        pattern = 'https://*.myworkdayjobs.com'
        task = 'https://one.wd5.myworkdayjobs.com/login'
        clients = [{'origin': pattern, 'actions': [{'origin': pattern, 'path': '/login',
                    'kind': 'stay_signed_in', 'name': 'Stay signed in'}]}]
        await self.page.goto('https://two.wd5.myworkdayjobs.com/login')
        await self.page.set_content('<button>Stay signed in</button>')
        self.assertIsNone(await click_trusted_login(self.page, task, clients, set()))
        await self.page.goto(task)
        await self.page.set_content('<button>Stay signed in</button>')
        self.assertEqual(await click_trusted_login(self.page, task, clients, set()), 'Stay signed in')

    async def test_standard_oauth_button_still_requires_exact_request(self):
        action = copy.deepcopy(ACTION)
        del action['name']
        clients = [{'origin': ORIGIN, 'actions': [action]}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trusted-auth.json'
            path.write_text(json.dumps({'trusted_oauth_clients': clients}))
            self.assertEqual(load_trusted_oauth_clients(path), clients)
        await self.page.goto(URL.replace('fixture', 'other'))
        await self.page.set_content('<h1>Glama</h1><button name=authorize>Authorize Glama</button>')
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
        await self.page.goto(URL)
        await self.page.set_content('<button id=js-oauth-authorize-btn name=authorize>Authorize Example</button>')
        self.assertEqual(await click_trusted_login(self.page, ORIGIN, clients, set()), 'Authorize Example')
        await self.page.set_content('<button name=authorize>Allow</button><button name=authorize>Allow</button>')
        self.assertIsNone(await click_trusted_login(self.page, ORIGIN, clients, set()))
