# Universal browser figure brief

Reader question: How does Ruin start and continue an ordinary web task when Chrome has only a blank tab?
Audience: Browser agents and people configuring their default local browser runtime.
Components: Agent, ruin_browser MCP tool, Python Playwright, shared Chrome on 127.0.0.1:9222, existing session, destination page and returned observation.
Sequence: The agent requests a URL; Ruin reuses the matching page, a single blank tab, or creates a tab; Playwright navigates in the existing context; the page returns its current URL, text and controls. The next call uses that current URL. Clicks and Enter use the existing Ruin executor.
Boundary: No domain allowlist for general browser operations. Dedicated challenge and receipt adapters retain their own supported providers. Existing unrelated tabs remain open. Input values are not read for observations.
Overview sketch: agent command -> local runtime -> Chrome window with a destination page.
Detail sketch: blank/new task, existing exact tab, and redirect continuation are stacked annotated specimens beneath the overview.
Style: Warm paper, dark ink, Rough.js outlines, Kalam headings, sans-serif labels, violet browser operations, amber tab decisions and mint returned observations.
Verification: Compare with ruin/browser/universal.py and tests/test_universal.py, plus tests/test_mcp.py. Inspect exported SVG at 720 and 360 pixels wide.
