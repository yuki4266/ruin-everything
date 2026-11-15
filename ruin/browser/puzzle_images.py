"""Locate the piece origin in the board's intrinsic pixel coordinates."""

from functools import lru_cache

import cv2
import numpy as np
from ddddocr.utils.exceptions import DDDDOCRError


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
    try:
        match = slide_engine().slide_match(encoded(part), encoded(band), simple_target=True)
        guess = match["target_x"] - w // 2 - x
    except (DDDDOCRError, ValueError, RuntimeError, KeyError, cv2.error):
        # OpenCV remains usable when the corroborating match fails.
        match, guess = {"confidence": 0.0}, float("inf")
    if alpha is None or cv2.countNonZero(mask) == mask.size:
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


def composite_points(image):
    """Find a distinct pair of matching outlines in a flattened puzzle image.

    Only outlined, horizontally translated pieces are supported. A photograph
    without a separable piece silhouette is ambiguous and returns no match.
    """
    bg = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_GRAYSCALE)
    if bg is None or bg.size > 4_000_000:
        return None
    height, width = bg.shape
    edges = cv2.Canny(bg, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (12 <= w <= width * .4 and 12 <= h <= height * .8):
            continue
        if cv2.contourArea(contour) < w * h * .35:
            continue
        if any(abs(x-a) < 4 and abs(y-b) < 4 and abs(w-c) < 4 and abs(h-d) < 4
               for a, b, c, d in boxes):
            continue
        boxes.append((x, y, w, h))
    if len(boxes) > 64:
        return None
    candidates = []
    for x, y, w, h in boxes:
        template = edges[y:y+h, x:x+w]
        for tx, ty, tw, th in boxes:
            if tx <= x + w or abs(ty-y) > 3 or abs(tw-w) > 3 or abs(th-h) > 3:
                continue
            patch = cv2.resize(edges[ty:ty+th, tx:tx+tw], (w, h))
            score = float(cv2.matchTemplate(patch, template, cv2.TM_CCORR_NORMED)[0, 0])
            if score >= .8:
                candidates.append((score, x, y, w, h, tx, tw))
    candidates.sort(reverse=True)
    if not candidates or (len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .08):
        return None
    _, x, y, w, h, tx, tw = candidates[0]
    return {"piece": (x+w/2)/width, "hole": (tx+tw/2)/width, "y": (y+h/2)/height}
