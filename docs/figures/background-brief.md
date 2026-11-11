# Background execution figure brief

Reader question: How can Ruin keep a task interactive without switching the user's app or overwriting their tab?
Audience: People using local Chrome while an agent works.
Components: User's frontmost application, shared Chrome profile, explicit destination tab, marked agent target, private target-ID registry, CDP renderer emulation, macOS background launcher.
Sequence: Select an explicit/exact destination or an unchanged owned target; otherwise create a target with background=true. Enable focus emulation and active lifecycle on the task page. Dispatch browser input and capture the viewport. Persist target ID, purpose and URL hash for later reconnects.
Boundaries: No OS activation commands. Manual navigation prevents implicit reuse. Other tabs are not emulated. The existing Chrome process is not restarted; launch flags apply on the next launch. Focus emulation does not guarantee a site's challenge verdict. The identity editor also opens in a background tab, selected manually when needed.
Overview sketch: A user application above an independent Chrome task strip, separated by an OS-focus boundary. The task strip connects the selector, owned target and CDP renderer.
Detail sketch: Decision specimen for ownership and a launcher specimen for next-start flags.
Style: Warm paper and dark ink, Rough.js outlines, Kalam headings, violet browser work, amber decisions and mint verification results. Editable SVG and generator retained.
Verification: Compare with background.py, context.py, universal.py and test_background.py. Check nested-frame input in test_hcaptcha.py and live frontmost-app equality before/after input and reconnect. Inspect at 720 and 390 pixels.
