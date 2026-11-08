"""Locate the piece origin in the board's intrinsic pixel coordinates."""

from functools import lru_cache

import cv2
import numpy as np


@lru_cache(maxsize=1)
def slide_engine():
    from ddddocr import DdddOcr

    return DdddOcr(det=False, ocr=False, show_ad=False)


def gap_x(background, piece, *, relative_size=(1.0, 1.0), row=0):
    bg = cv2.imdecode(np.frombuffer(background, np.uint8), cv2.IMREAD_GRAYSCALE)
    tile = cv2.imdecode(np.frombuffer(piece, np.uint8), cv2.IMREAD_UNCHANGED)
    if bg is None or tile is None:
        return None
    # Express the piece pixels at the background's pixel density.
    width, height = (round(n * scale) for n, scale in zip(tile.shape[1::-1], relative_size))
    if not (4 <= width <= bg.shape[1] and 4 <= height <= bg.shape[0] + 2):
        return None
    tile = cv2.resize(tile, (width, height))
    alpha = tile[:, :, 3] if tile.ndim == 3 and tile.shape[2] == 4 else None
    mask = (alpha > 128).astype(np.uint8) if alpha is not None else np.ones((height, width), np.uint8)
    x, y, w, h = cv2.boundingRect(mask)
    top = round(row) + y
    if min(w, h) < 4 or top < -3 or top + h > bg.shape[0] + 3:
        return None
    # Restrict both methods to the piece's actual rendered row.
    start, stop = max(0, top - 3), min(bg.shape[0], top + h + 3)
    if stop - start < h:
        return None
    band = bg[start:stop]
    part = tile[y : y + h, x : x + w]
    encoded = lambda image: cv2.imencode(".png", image)[1].tobytes()
    # ddddocr 1.6 returns the center of the cropped template.
    match = slide_engine().slide_match(encoded(part), encoded(band))
    guess = match["target_x"] - w // 2 - x
    if alpha is None or cv2.countNonZero(mask) == mask.size:
        if match["confidence"] < 0.48:
            return None
        template = cv2.Canny(part, 50, 150)
        scores = cv2.matchTemplate(cv2.Canny(band, 50, 150), template, cv2.TM_CCOEFF_NORMED).max(axis=0)
    else:
        kernel = np.ones((3, 3), np.uint8)
        outline = cv2.morphologyEx(np.pad(mask[y : y + h, x : x + w], 1), cv2.MORPH_GRADIENT, kernel)[
            1:-1, 1:-1
        ]
        edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(bg, (3, 3), 0), 50, 120), kernel)
        scores = cv2.matchTemplate(edges[start:stop], outline, cv2.TM_CCORR).max(axis=0)
        scores /= 255 * max(cv2.countNonZero(outline), 1)
    best = int(scores.argmax())
    rivals = scores[np.abs(np.arange(len(scores)) - best) > 6]
    agrees = abs(best - x - guess) <= 3 and match["confidence"] >= 0.20
    if (
        not rivals.size
        or scores[best] < (0.48 if agrees else 0.65)
        or scores[best] - rivals.max() < (0.05 if agrees else 0.08)
    ):
        return None
    return best - x
