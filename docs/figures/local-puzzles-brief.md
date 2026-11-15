# Local puzzle matching

Reader question: How does Ruin choose a drag without asking a visual model?
Audience: runtime users and maintainers.
Components: original page images, ddddocr/OpenCV gap matcher, NumPy polar seam matcher, calibrated rail, pointer, site SMS countdown.
Sequence: recognize rotation before generic pieces; read pixels; solve; scale or calibrate; drag; check site evidence.
Boundary: ambiguous contours, unreadable images, and a single image without a reference remain pending. No claim of universal solving or login completion.
Overview: separate horizontal and circular image paths converge on measured movement.
Detail: ease-out path, 15–25 moves (rotation: 5 probe + 18 final), Y jitter, final 150–250 ms hold. Distinguish motion from the site's countdown.
Verification: compare with puzzle_images.py, feishu.py, puzzles.py and the nested-provider browser fixture. Review at 720 and 360 CSS pixels.
