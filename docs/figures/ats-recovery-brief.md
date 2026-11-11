# ATS account recovery

Reader question: What happens when an employer login rejects a saved password?
Audience: Browser-agent users and maintainers.
Components: Private local env file, selected iCIMS/Workday tenant, observed account form, Ruin executor, provider email verification, candidate application.
Sequence: Explicitly enable recovery and initialize a fixed password; classify identifier/current/new password; try a visible registration entry on explicit failure; retry the configured password once; request recovery from the visible control; continue password setup when its verified form is available.
Boundaries: No guessed registration endpoints. No password in arguments, tool results or repository. Check identity and same-origin POST before submission. Session markers limit each phase per tenant and email for fifteen minutes across reconnects. A recovery request does not prove mailbox delivery or an application receipt.
Overview sketch: Local configuration feeds the selected tenant; a branching diagram labels new password, credential rejection and continued failure.
Detail sketch: Keep the mail request and password setup distinct from the application receipt. Show waiting for site verification at the mail boundary.
Verification: Compare with ats_config.py, ats_accounts.py, workday.py and test_ats_accounts.py. The Planview live page used current-password and exposed no registration entry. The site acknowledged the reset request; inbox/junk checks did not yet show a matching message.
