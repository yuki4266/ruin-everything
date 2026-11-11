# Build retry figure brief

Reader question: What happens when browser installation fails in CI?
Audience: Maintainers checking whether a build can publish.
Components: GitHub Actions build job, hosted Ubuntu libraries, Playwright Chromium installer, regression tests, distribution checks, artifact upload and dependent PyPI publish job.
Sequence: Install Chromium using the shared libraries already supplied by hosted Ubuntu. Browser regression tests validate that environment. On failure, wait 15 seconds before attempt two and 30 seconds before attempt three. On success, run tests, build distributions, validate metadata and upload artifacts. Publish requires the build job to succeed.
Boundaries: Three attempts maximum and a 30-minute installation step timeout. Persistent installation failure stops the build. No test or packaging failure is retried by this change. Existing PyPI artifacts are unaffected by a failed build.
Overview sketch: A browser-shaped installation panel flows to a checklist and then a package receipt. An amber inset describes the bounded failure path.
Detail sketch: Label success and failure branches explicitly. The failure path ends at a stop marker; only successful checks move distributions to PyPI.
Style: Warm paper, dark ink, violet browser installation, amber retry decisions and mint checked distributions. Rough.js outlines, embedded Kalam headings and sans-serif details.
Verification: Compare every label and arrow with .github/workflows/publish.yml. Render at README and mobile widths. Exercise the extracted shell script with immediate success, recovered failure and persistent failure.
