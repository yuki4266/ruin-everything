# Turnstile continuation

Reader question: how does the runtime find a closed-shadow verification widget, operate it without resubmitting the application, and preserve genuine clearance?
Audience: users and maintainers of the local Chrome runtime.
Components: existing Chrome profile, Ruin action lock, CDP outer iframe geometry, local rendered-state observer, trusted mouse path, site-issued token/cookie, private snapshot and employer receipt.
Sequence: observe original URL; locate one visible widget; reject ambiguous/covered geometry; move and click once; observe verification; preserve unexpired site-scoped clearance if issued; independently verify application receipt.
Boundaries: no synthetic success/token, no repeated Submit, no cookie sharing between profiles, no fixed toolbar offset, no Chrome restart while forms are pending. Normal Turnstile may issue only a token. Website rejection stays pending.
Overview: horizontal sequence in panel A. Detail B annotates the widget and trusted gesture. Detail C separates browser clearance from site submission.
Verification: isolated browser tests cover closed roots, DPR 2, overlays, stale geometry, no duplicate submission and private profile-bound cookies. Live outcome is documented in the runtime reference, never inferred from a click.
