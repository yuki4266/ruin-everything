# Local Auth Vault figure brief

Reader question: How does one manual login become a reusable local login without clicking Chrome's save-password prompt?

Audience: People running browser agents against their own persistent local Chrome profile.

Overview: A manual submit in a page or nested iframe sends the frame hostname, username and password through the local Playwright/CDP binding to a detached singleton listener. The listener atomically writes auth_vault.json with mode 0600. A selected Ruin task looks up the exact hostname, then a saved registrable-domain record, fills one login form and uses the existing executor.

Detail: Storage.getCookies and frame Web Storage snapshots go to cookies_snapshot.json. A new Chrome generation restores missing unexpired cookies and empty local/session storage. Session storage stays associated with its original tab; ambiguous tab matches are skipped. CLI disconnect is not listener shutdown. The existing background target path preserves OS focus.

Boundaries: HTTPS credential capture only; never search sibling tenant records. One credential attempt per tenant/credential in fifteen minutes. A password capture, redirect or restored cookie is not an application receipt. IndexedDB, service-worker caches, passkeys and server-side expiry are outside this module. An active task can wait for manual login; the listener does not create a resume-upload workflow on its own.

Sketch: Panel A uses browser window → local vault. Panel B uses an exact-host decision → executor. Panel C uses snapshot folder → next browser generation. Warm paper, violet browser work, mint local records, amber match/retry decisions; use distinct shapes and label all arrows. Compare against tests/test_local_vault.py and ruin/auth/vault_runtime.py. Verify mobile and README widths.
