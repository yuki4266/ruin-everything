"""Recognize institutional discovery controls only on academic service origins."""
from dataclasses import dataclass, field
from time import monotonic
from urllib.parse import urlsplit

from ruin.auth.autofill import offer_chrome_login
from ruin.auth.trusted import trusted_client

PUBLISHERS = {
    "ieeexplore.ieee.org", "dl.acm.org", "link.springer.com", "link.springernature.com",
    "wayf.springernature.com",
}
DISCOVERY = {
    "idp.springer.com", "fsso.springer.com",
    "service.seamlessaccess.org", "use.thiss.io", "wayf.openathens.net",
}
DUKE = "shib.oit.duke.edu"
WATCHED = PUBLISHERS | DISCOVERY | {DUKE}


def host(url):
    loc = urlsplit(url)
    return loc.netloc if loc.scheme == "https" and loc.netloc == loc.hostname else ""


# Return a handle to the inspected node, so navigation cannot retarget a locator.
FIND_CONTROL = r"""() => {
    const visible = e => e.getClientRects().length && e.checkVisibility({visibilityProperty:true, opacityProperty:true}) &&
        !e.disabled && e.getAttribute('aria-disabled') !== 'true';
    const norm = s => (s || '').replace(/\s+/g, ' ').trim();
    const name = e => norm(e.getAttribute('aria-label') || e.innerText || e.textContent);
    const select = s => [...document.querySelectorAll(s)].filter(visible);
    const unique = es => {
        if (es.length <= 1) return es[0] || null;
        const exposed = es.filter(e => {
            const r = e.getBoundingClientRect();
            return e.contains(document.elementFromPoint(r.x + r.width/2, r.y + r.height/2));
        });
        return exposed.length === 1 ? exposed[0] : null;
    };
    if (/Access (?:provided by|through)\s*:\s*Duke University/i.test(document.body?.innerText || ''))
        return null;
    const controls = select('a,button,[role=option],[role=button],[role=link],li');
    const nameIs = regex => controls.filter(e => regex.test(name(e)))
        .filter(e => !controls.some(child => child !== e && e.contains(child) && regex.test(name(child))));
    const search = unique(select('input:not([type]),input[type=text],input[type=search],input[role=combobox]')
        .filter(e => /institut|organi[sz]ation|university|federation/i.test(
            [e.placeholder, e.getAttribute('aria-label'), e.name, e.id,
             ...(e.labels || [])].map(x => typeof x === 'string' ? x : x?.textContent).join(' '))));
    if (search && (search.readOnly || (search.value && search.value !== 'Duke University')))
        return null;
    const change = unique(nameIs(/^(?:add or change institution|choose another institution|access through your institution)$/i));
    const cached = unique(nameIs(/^access (?:through|via) Duke University(?: Libraries)?$/i));
    const institution = unique(nameIs(/^Duke University(?: Libraries)?(?:\s*\(duke\.edu\)|\s+duke\.edu)?$/i)
        .filter(e => search || e.closest('[role=listbox],[role=dialog],dialog') || e.matches('[role=option]')));
    if (institution) return {action:'select', node:institution};
    if (search) {
        if (!search.value) return {action:'search', node:search};
        return null;
    }
    if (change) return {action:'directory',node:change};
    if (cached) return {action:'select',node:cached};
    if (select('[role=dialog],dialog[open],.modal.show').length) return null;
    const entry = unique(nameIs(/^(?:institutional sign[ -]?in|institutional login|institutional access|sign in (?:via|through|with) (?:your|an) institution|access (?:via|through) (?:your|an) institution|log in via an institution|find my institution)$/i));
    return entry ? {action:'entry',node:entry} : null;
}"""


@dataclass
class AcademicFlow:
    checked_opener: bool = False
    expires: float = 0
    attempts: dict = field(default_factory=dict)

    def started(self):
        self.expires = monotonic() + 300

    def active(self):
        return monotonic() < self.expires

    def claim(self, key):
        now = monotonic()
        self.attempts = {k: v for k, v in self.attempts.items() if now - v < 300}
        if key in self.attempts:
            return False
        self.attempts[key] = now
        return True


async def duke_login(page, flow, *, saved_only=False):
    url = page.url
    if not flow.active() or host(url) != DUKE:
        return
    fields = await page.locator('input[type=password]:visible').element_handles()
    try:
        if len(fields) != 1:
            return
        return await _use_duke_form(page, fields[0], flow, url, saved_only=saved_only)
    finally:
        for field in fields:
            await field.dispose()


async def _use_duke_form(page, field, flow, url, *, saved_only=False):
    eligible = await field.evaluate("""e => location.origin === 'https://shib.oit.duke.edu' &&
        e.form && new URL(e.form.action).origin === location.origin &&
        !e.form.querySelector('[autocomplete~=new-password]') &&
        e.form.querySelector('input[autocomplete=username],input[name=j_username],input[name=username],#netid') &&
        !e.disabled && !e.readOnly""")
    if not eligible or page.url != url:
        return
    clients = getattr(page.context, "ruin_trusted_oauth_clients", [])
    policy = trusted_client(clients, url)
    if policy is None:
        # Starting the Duke watcher opts in for this single identity provider.
        clients = [{"origin": f"https://{DUKE}", "chrome_password_dropdown": True}]
    if not await field.evaluate("e => Boolean(e.value)"):
        if saved_only or (policy is not None and not policy.get("chrome_password_dropdown")):
            return
        if flow.claim(("chrome",)):
            await page.bring_to_front()
            await offer_chrome_login(page, url, clients=clients,
                                     chrome_only=True)
            return "chrome"
        return
    submit = await field.evaluate_handle("""e => {
        const username = e.form.querySelector('input[autocomplete=username],input[name=j_username],input[name=username],#netid');
        if (!username?.value) return null;
        const buttons = [...e.form.querySelectorAll('button,input[type=submit]')].filter(b =>
            b.type === 'submit' && b.getClientRects().length && !b.disabled &&
            new URL(b.getAttribute('formaction') || e.form.action, location.href).origin === location.origin &&
            (b.id === 'Submit' || /^(?:log ?in|sign ?in|login with netid)$/i.test((b.innerText || b.value || '').trim())));
        return buttons.length === 1 ? buttons[0] : null;
    }""")
    try:
        if submit.as_element() and page.url == url and flow.claim(("login",)):
            from ruin.auth.saved_login import click_once
            if await click_once(page, submit.as_element(), url):
                return "login"
    finally:
        await submit.dispose()


async def academic_step(page, flow):
    from ruin.auth.saved_login import duo_trust, is_duo
    top = host(page.url)
    if top == DUKE:
        return await duke_login(page, flow) or (await duo_trust(page) if flow.active() else None)
    if is_duo(page.url) and flow.active():
        return await duo_trust(page)
    if top not in PUBLISHERS and not (top in DISCOVERY and flow.active()):
        return
    for frame in page.frames:
        origin = host(frame.url)
        if origin not in PUBLISHERS | DISCOVERY:
            continue
        if frame != page.main_frame:
            owner = await frame.frame_element()
            try:
                if not await owner.is_visible():
                    continue
            finally:
                await owner.dispose()
        start = page.url
        result = await frame.evaluate_handle(FIND_CONTROL)
        try:
            if not await result.evaluate("r => Boolean(r)"):
                continue
            action = await result.evaluate("r => r.action")
            element = await result.get_property("node")
            try:
                node = element.as_element()
                if page.url != start or not node or not flow.claim((origin, start, action)):
                    continue
                flow.started()
                if action == "search":
                    # Typeahead providers may start their request on keyup.
                    await node.type("Duke University", delay=25, timeout=2500)
                else:
                    # Background Chrome throttles the animation frames used by
                    # pointer clicks. Activate the already inspected DOM control.
                    await node.evaluate("""e => {
                        if (e.isConnected && e.checkVisibility({visibilityProperty:true, opacityProperty:true}) && !e.disabled)
                            e.click();
                    }""")
                return action
            finally:
                await element.dispose()
        finally:
            await result.dispose()
