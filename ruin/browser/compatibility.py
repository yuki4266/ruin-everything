"""Small, idempotent compatibility changes for the existing Chrome profile."""

import os

# Keep native values when Chrome already supplies them. A guessed toolbar height
# breaks fullscreen, zoom, multi-monitor and iframe coordinates.
SCRIPT = r"""(() => {
    const key = Symbol.for('ruin.inputCompatibility.v1');
    if (globalThis[key]) return;
    Object.defineProperty(globalThis, key, {value: true});
    if (navigator.webdriver === true) {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            configurable: true, get() { return false; }
        });
    }
    // Observe before patching. Modern Chrome already translates screen points
    // correctly; replacing its native getters would add an unnecessary fingerprint.
    if (window !== window.top) return;
    addEventListener('mousemove', function probe(event) {
        if (!event.isTrusted) return;
        removeEventListener('mousemove', probe, true);
        if (outerWidth < innerWidth || outerHeight < innerHeight) return;
        for (const axis of ['X', 'Y']) {
            const name = 'screen' + axis;
            const border = Math.max(0, (outerWidth - innerWidth) / 2);
            const offset = axis === 'X' ? window.screenX + border :
                window.screenY + Math.max(0, outerHeight - innerHeight - border);
            if (!offset || event[name] !== event['client' + axis]) continue;
            const descriptor = Object.getOwnPropertyDescriptor(MouseEvent.prototype, name);
            if (!descriptor?.get || !descriptor.configurable) continue;
            Object.defineProperty(MouseEvent.prototype, name, {
                ...descriptor, get() {
                    const original = descriptor.get.call(this);
                    const client = this['client' + axis];
                    if (!this.isTrusted || original !== client ||
                        outerWidth < innerWidth || outerHeight < innerHeight) return original;
                    const edge = Math.max(0, (outerWidth - innerWidth) / 2);
                    const delta = axis === 'X' ? window.screenX + edge :
                        window.screenY + Math.max(0, outerHeight - innerHeight - edge);
                    return original + delta;
                }
            });
        }
    }, true);
})()"""


async def prepare_compatibility(page, session):
    from .driver import ENGINE
    # Patchright owns its execution contexts and initialization. Avoid layering
    # Playwright-style init-script routing and prototype overrides on top.
    if ENGINE == 'patchright' or os.getenv('RUIN_BROWSER_COMPATIBILITY', '1') == '0':
        return
    if not getattr(page, '_ruin_compatibility_installed', False):
        await session.send('Page.addScriptToEvaluateOnNewDocument', {'source': SCRIPT})
        # Playwright distributes this to future out-of-process child frames too.
        if not getattr(page.context, '_ruin_compatibility_installed', False):
            await page.context.add_init_script(SCRIPT)
            page.context._ruin_compatibility_installed = True
        await session.send('Runtime.evaluate', {'expression': SCRIPT})
        page._ruin_compatibility_installed = True
