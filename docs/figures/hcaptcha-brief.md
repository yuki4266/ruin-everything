# Nested hCaptcha execution

Reader question: Why did an iCIMS challenge report an ambiguous target, and where should input land?
Audience: Browser-agent maintainers.
Components: Original tab, iCIMS content frame, cross-origin hCaptcha challenge, indexed grid or canvas, Ruin executor, site continuation.
Sequence: Prefer the visible challenge; classify provider markup before slider heuristics; inspect image; resolve indexed cells or normalized canvas points; accumulate frame content origins; send browser input; click the widget submit control; observe the original tab.
Boundary: A cleared widget or redirect is not an application receipt. Unsupported or uncertain tasks stay pending. Hidden ancestor frames are excluded. Local Ollama remains the default vision provider.
Overview sketch: A nested cutaway of the tab, form frame and challenge; beside it a three-route decision for grid, canvas and checkbox.
Detail sketch: One coordinate equation per ancestor, with scroll-relative bounds, borders, padding and scale; an outcome strip distinguishing widget continuation from the site's receipt.
Verification: Compare with detect_puzzle.js, viewport_box, solve_grid, solve_hcaptcha_drag, solve_hcaptcha_points, and tests/test_hcaptcha.py. The live Planview task was a two-dimensional drag misclassified as a slider; it was not evidence of multiple selector matches. Isolated cross-origin tests exposed omitted iframe borders in Chromium bounding boxes.
