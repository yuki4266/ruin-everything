# Saved login figure brief

Reader question: How does a shared Chrome login survive a restart and proceed through Duke/Duo without an immediate handoff?

Audience: local browser-agent users.

Overview sequence: fixed user-data directory → Chrome session restoration → selected task tab. Detail sequence: filled Duke form → Ruin executor → Duo device trust → observe current URL. The wait panel distinguishes a redirect from a remaining code or phone push after 15 seconds. Credentials never leave the browser. A document-local marker suppresses duplicate submission.

Boundaries: profile preparation happens offline; running Chrome changes its own settings through the UI. Only Duke same-origin credential forms and visible HTTPS Duo controls are supported. The server sets session and remembered-device expiry. A redirect is not an authentication receipt.

Draw three labeled panels on warm paper with violet browser operations, amber decisions, mint observed continuation and a neutral human handoff. Use Rough.js outlines, embedded Kalam headings and sans-serif details. Each arrow carries an action or state. Compare with context.py, saved_login.py, academic.py and the isolated restart/login tests. Review at 720 px and 360 px.
