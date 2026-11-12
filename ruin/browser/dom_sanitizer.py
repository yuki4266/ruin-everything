from ruin.browser.driver import Page


async def snapshot(page: Page):
    """Capture labels and element handles together so a re-render invalidates old IDs."""
    elements = await page.locator(
        'a[href], button, input[type=submit], [role=button]'
    ).element_handles()
    targets = {}
    labels = []
    for element in elements:
        if not await element.is_visible() or not await element.is_enabled():
            continue
        label = await element.evaluate(
            """el => (el.getAttribute('aria-label') || el.innerText ||
                (el.type === 'submit' ? el.value : '') || '').trim().slice(0, 160)"""
        )
        if label:
            index = len(labels) + 1
            labels.append({"id": index, "label": label})
            targets[index] = element
    return labels, targets
