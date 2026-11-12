# Figure brief: ordered icon clicks

Reader question: How does Ruin turn GeeTest's visual order into accurate clicks?

Audience: browser-agent users and runtime contributors.

Overview: visible prompt and clipped square board → ddddocr candidate boxes → numbered crops and local Ollama order → CSS viewport clicks → provider confirmation.

Detail: the transparent image may extend into the footer. Capture the board wrapper, scale each detected center by screenshot width/height and current CSS dimensions, including iframe transforms. Compare the prompt and board again before clicking. Click in order, wait 250–400 ms between selections, then wait 300 ms before OK. A still-visible challenge refreshes and retries, at most three attempts. Never replay the application submission.

Boundaries: only the cropped challenge is sent to the local vision model. A cleared challenge is not a login or application receipt. Uncertain/changed images stay pending.

Style: warm paper, violet browser operations, amber retry decision, mint provider result; Rough.js lines, Kalam headings, sans-serif details. Use a two-panel sequence with a boxed coordinate equation. No copied website artwork or private session data.

Strong rotated-template matches can cross-check the order. Otherwise local vision compares each uniformly spaced target slot separately. Ambiguous or duplicate candidate IDs stop that attempt.
