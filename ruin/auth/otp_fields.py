"""Enter a code into the verification controls of the original page."""

import re

from playwright.async_api import Error

# react-otp-input labels each cell, including when maxlength is absent.
OTP_INPUTS = ('input[autocomplete=one-time-code]:visible, input[maxlength="1"]:visible, input[size="1"]:visible, '
              'input[aria-label*="OTP character" i]:visible')
OTP_PROMPT = re.compile(r'验证码|verification code|security code|one[- ]time (?:code|password)|\bOTP\b', re.I)


async def sms_fields(page):
    dialog = page.locator('dialog:visible, [role=dialog]:visible').filter(has_text=OTP_PROMPT)
    group = page.get_by_role('group', name=OTP_PROMPT)
    for scope in (group, dialog):
        if await scope.count() != 1:
            continue
        marked = scope.locator(OTP_INPUTS)
        plain = scope.locator('input:is(:not([type]), [type=text], [type=tel], [type=number])'
                              ':not([readonly]):not([disabled]):visible')
        if await marked.count() <= 1 and 4 <= await plain.count() <= 8:
            return plain, True
        return marked, False
    return page.locator(OTP_INPUTS), False


async def fill_otp(fields, code, url, *, labeled_group=False):
    """Keep paste, focus and input events scoped to one verified set of controls."""
    if not re.fullmatch(r'[A-Za-z0-9]{4,8}', code):
        raise ValueError("Expected a four- to eight-character verification code.")
    try:
        return await fields.evaluate_all("""async (cells, {code, url, labeled}) => {
            const valid = () => location.href === url && cells.every(el =>
                el instanceof HTMLInputElement && el.isConnected && !el.disabled && !el.readOnly &&
                ['text', 'tel', 'number', 'password', 'search'].includes(el.type) && el.getClientRects().length);
            if (!valid() || !cells.length) return false;
            const first = cells[0], split = cells.length > 1;
            if (split) {
                const owner = el => el.closest('fieldset, [role=group], form, [role=dialog], dialog');
                if (cells.length !== code.length || cells.some(el => owner(el) !== owner(first))) return false;
                if (!labeled && !cells.every(el =>
                    el.maxLength === 1 || el.size === 1 || /OTP character/i.test(el.getAttribute('aria-label') || ''))) return false;
            } else if (first.maxLength >= 0 && first.maxLength < code.length) return false;

            const matches = () => split
                ? cells.every((el, index) => el.value === code[index])
                : first.value === code;
            const tick = () => new Promise(resolve => setTimeout(resolve, 0));
            if (matches()) return true;
            if (split) {
                first.focus();
                const data = new DataTransfer();
                data.setData('text/plain', code);
                first.dispatchEvent(new ClipboardEvent('paste', {clipboardData:data, bubbles:true, cancelable:true}));
                await tick();
                if (!valid()) return false;
                if (matches()) return true;
            }
            const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            for (const [index, el] of cells.entries()) {
                const value = split ? code[index] : code;
                if (el.value === value) continue;
                el.focus();
                await tick();
                if (!valid()) return false;
                setValue.call(el, value);
                el.dispatchEvent(new InputEvent('input', {bubbles:true, data:value, inputType:'insertText'}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                await tick();
                if (!valid()) return false;
            }
            return matches();
        }""", {"code": code, "url": url, "labeled": labeled_group})
    except Error:
        raise RuntimeError("The verification controls changed during entry. Check the original tab.") from None
