# Core workflow figure brief

Reader question: What does Ruin do for me after I give my agent a browser task?
Audience: New users deciding whether to connect their agent to local Chrome.
Components: The user's agent, Ruin, the shared Chrome profile, background task tab, local login vault, supported verification adapters and the site's confirmation.
Sequence: The agent sends a task through MCP. Ruin operates the task tab in shared Chrome. Existing sessions or a matching local credential support login. Supported adapters handle an observed verification step. The site's confirmation supplies evidence; an Ashby watcher can store a receipt.
Boundaries: Background operation does not activate the user's app. Login reuse cannot extend server-side session validity. Verification support depends on the provider; a pending challenge is not success. Receipt persistence is specifically implemented for Ashby. The local password vault is plaintext with owner-only permissions.
Overview sketch: Three vertical stages, each with a distinct object illustration: a browser window for task execution, a key and envelope for login and verification, and a torn receipt for evidence. Label the two downward arrows with the action or evidence that moves.
Detail sketch: Three numbered panels pair the object with two short benefit lines. Put the pending-verification boundary in the last panel, beside the receipt rather than behind a footnote.
Style: Warm paper, dark ink, violet browser work, soft pink mail, mint receipts and amber decisions. Rough.js outlines, embedded Kalam headings and sans-serif labels. Keep a single column legible at 390 px and 720 px.
Verification: Compare with universal.py, background.py, vault_login.py, actions.py and ashby.py. Render at 390 px and 720 px; inspect text bounds and every arrow. Generator and editable SVG are committed together.
