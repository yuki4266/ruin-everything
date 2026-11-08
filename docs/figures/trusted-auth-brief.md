# Trusted login figure brief

Reader question: When may the selected browser task use a saved login action?
Audience: users configuring their local Chrome runtime.
Components: selected --autofill task, trusted-auth.json, exact request matcher, one visible button, Chrome profile.
Sequence: load local configuration at CDP attachment; match the task origin and action; click once or leave the original tab open.
Boundaries: no global watchers; no wildcard tenants; GitHub OAuth requires client ID, callback and exact scopes; Chrome popup visibility is not observable through the page DOM.
Overview sketch: task -> local configuration -> exact match -> one click.
Detail sketch: password field -> no keyring password -> opt-in ArrowDown / Enter; no popup guarantee.
Verification: compare with trusted.py, autofill.py, browser_task.py and test_trusted_auth.py. Inspect at 720px and 360px widths.
