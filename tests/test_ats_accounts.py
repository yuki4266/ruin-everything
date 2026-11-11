import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright
from ruin.auth.ats_config import settings, setup
from ruin.auth.ats_accounts import icims_account
from ruin.auth.workday import workday_account

SECRET = 'Fixture-Only_Strong123!'
PROFILE = {'email': 'fixture@example.test', 'auto_signup': True,
           'ats_auto_recover': True, 'ats_default_password': SECRET}


class ConfigurationTests(unittest.TestCase):
    def test_private_stable_setup_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / '.env'
            os.environ['RUIN_ATS_ENV_FILE'] = str(path)
            result = setup()
            original = settings()['ats_default_password']
            self.assertNotIn(original, str(result))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            setup()
            self.assertEqual(settings()['ats_default_password'], original)
            os.environ['ATS_DEFAULT_PASSWORD'] = SECRET
            self.assertEqual(settings()['ats_default_password'], SECRET)

    def test_rejects_insecure_file_and_never_echoes_invalid_password(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / '.env'
            os.environ['RUIN_ATS_ENV_FILE'] = str(path)
            path.write_text('ATS_DEFAULT_PASSWORD=secret-fixture')
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, '0600'):
                settings()
            path.chmod(0o600)
            with self.assertRaises(ValueError) as error:
                settings()
            self.assertNotIn('secret-fixture', str(error.exception))


class AccountsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch('ruin.browser.actions.PROFILE', Path(tmp) / 'chrome'))
        driver = await self.enterAsyncContext(async_playwright())
        self.browser = await driver.chromium.launch(channel=os.getenv('RUIN_TEST_CHANNEL', 'chromium'))
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        self.host = 'https://login.icims.com'
        self.site = self.host + '/u/login/password'
        self.requests = []

    async def serve(self, pages):
        async def route(r):
            self.requests.append((r.request.url, r.request.method, r.request.post_data or ''))
            await r.fulfill(content_type='text/html', body=pages[r.request.url.removeprefix(self.host)])
        await self.context.route(self.host + '/**', route)
        await self.page.goto(self.site)

    def login(self, error='Wrong username or password', extra=''):
        return f'''<title>Log in to Fixture</title><h1>Enter Your Password</h1>
            <form method=post action="/u/login/password"><input autocomplete=username type=text value="fixture@example.test" hidden>
            <input type=password autocomplete=current-password><button>LOG IN</button></form><p>{error}</p>
            <a href="/u/reset-password/request">Reset your password</a>{extra}'''

    async def test_invalid_login_retries_default_once_and_sends_one_reset(self):
        await self.serve({'/u/login/password': self.login(), '/u/reset-password/request': '<h1>Check Your Email</h1><p>Instructions to reset your password have been sent.</p>'})
        result = await icims_account(self.page, self.page.url, PROFILE)
        self.assertEqual(result['state'], 'reset_email_requested')
        await icims_account(self.page, self.page.url, PROFILE)
        self.assertEqual(len([r for r in self.requests if r[1]=='POST']), 1)
        self.assertEqual(len([r for r in self.requests if '/u/reset-password/request' in r[0]]), 1)
        self.assertNotIn(SECRET, str(result))

    async def test_first_password_setup_is_not_login(self):
        await self.serve({'/u/login/password': '''<h1>Set Your Password</h1><form method=post action="/complete">
            <input type=password autocomplete=new-password><input type=password><button>Create Account</button></form>''', '/complete': '<h1>Candidate profile</h1>'})
        self.assertEqual((await icims_account(self.page, self.page.url, PROFILE))['state'], 'account_step_completed')
        self.assertEqual(self.page.url, self.host+'/complete')

    async def test_invalid_login_prefers_registration_entry(self):
        await self.serve({'/u/login/password': self.login(extra='<a href="/create">Create an account</a>'),
            '/create': '<h1>Set Your Password</h1><form method=post action="/complete"><input type=password autocomplete=new-password><button>Create Account</button></form>',
            '/complete': '<h1>Candidate profile</h1>'})
        await icims_account(self.page, self.page.url, PROFILE)
        self.assertEqual(self.page.url, self.host+'/complete')
        self.assertFalse(any(r[1]=='POST' and r[0].endswith('/u/login/password') for r in self.requests))

    async def test_cross_origin_form_is_not_submitted(self):
        await self.serve({'/u/login/password': self.login().replace('action="/u/login/password"','action="https://other.test/steal"')})
        with self.assertRaisesRegex(RuntimeError, 'same HTTPS origin'):
            await icims_account(self.page, self.page.url, PROFILE)
        self.assertEqual(len(self.requests), 1)

    async def test_wrong_identity_and_disabled_policy_are_untouched(self):
        await self.serve({'/u/login/password': self.login().replace('fixture@example.test','other@example.test')})
        result = await icims_account(self.page, self.page.url, PROFILE)
        self.assertIn('identity differs', result['reason'])
        self.assertIsNone(await icims_account(self.page, self.page.url, {**PROFILE,'ats_auto_recover':False}))
        self.assertEqual(len(self.requests), 1)

    async def test_workday_invalid_password_resets_without_loop(self):
        self.host = 'https://fixture.wd1.myworkdayjobs.com'
        self.site = self.host + '/jobs/42'
        login = '''<form method=post action="/signin"><input type=email><input type=password><button>Sign In</button></form>
            <p>Invalid credentials</p><a href="/reset">Forgot Password</a>'''
        await self.serve({'/jobs/42':login, '/signin':login, '/reset': '<form method=post action="/sent"><input type=email><button>Submit</button></form>', '/sent':'<p>Check your email for reset instructions</p>'})
        result = await workday_account(self.page, self.page.url, PROFILE)
        self.assertEqual(result['state'], 'reset_email_requested')
        self.assertEqual(len([r for r in self.requests if r[1]=='POST']), 2)

    async def test_embedded_icims_registration_accepts_required_terms(self):
        self.host='https://careers-fixture.icims.com'
        self.site=self.host+'/jobs/42'
        await self.serve({'/jobs/42':'<iframe id="icims_content_iframe" src="/create" style="width:800px;height:600px"></iframe>',
            '/create':'''<h1>Create Your Password</h1><form method=post action="/complete">
            <input type=password autocomplete=new-password><input type=password><label><input type=checkbox required>Privacy Policy</label><button>Create Account</button></form>''',
            '/complete':'<h1>Candidate profile</h1>'})
        await icims_account(self.page,self.page.url,PROFILE)
        self.assertTrue(any(r[0].endswith('/complete') and r[1]=='POST' for r in self.requests))

    async def test_existing_registration_routes_back_to_login_then_reset(self):
        await self.serve({'/u/login/password':self.login(), '/create':'''<h1>Set Your Password</h1>
            <input type=password autocomplete=new-password><p>Account already exists</p>
            <a href="/u/login/password">Log in</a>''',
            '/u/reset-password/request':'<p>Check your email for password reset instructions</p>'})
        await self.page.goto(self.host+'/create')
        result=await icims_account(self.page,self.page.url,PROFILE)
        self.assertEqual(result['state'],'reset_email_requested')
        self.assertEqual(len([r for r in self.requests if r[1]=='POST']),1)

    async def test_workday_javascript_reset_dialog_and_new_password(self):
        self.host='https://fixture.wd1.myworkdayjobs.com';self.site=self.host+'/jobs/42'
        await self.serve({'/jobs/42':'''<div role=dialog><form method=post onsubmit="event.preventDefault()">
            <input type=email><input type=password><button>Sign In</button></form><p>Invalid credentials</p>
            <button id=forgot>Forgot Password</button></div><script>
            document.querySelector('#forgot').onclick=()=>{
              const dialog=document.querySelector('[role=dialog]');
              dialog.innerHTML='<form><input type=email><button data-automation-id=forgotPasswordSubmitButton>Submit</button></form>';
              dialog.querySelector('button').onclick=e=>{e.preventDefault();document.body.innerHTML='Check your email for reset instructions'};
            };</script>'''})
        result=await workday_account(self.page,self.page.url,PROFILE)
        self.assertEqual(result['state'],'reset_email_requested')
        await self.page.set_content('''<div role=dialog><h1>Reset Password</h1><form>
            <input type=password><input type=password><button data-automation-id=resetPasswordSubmitButton
            onclick="event.preventDefault();document.body.innerHTML='Password changed'">Reset Password</button></form></div>''')
        result=await workday_account(self.page,self.page.url,PROFILE)
        self.assertEqual(result['state'],'account_step_completed')
