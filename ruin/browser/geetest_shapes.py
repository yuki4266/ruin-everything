"""Cross-check icon order against the prompt using local rotated templates."""

import cv2
import numpy as np


def template_matches(board, tip, boxes):
    board = cv2.imdecode(np.frombuffer(board, np.uint8), cv2.IMREAD_COLOR)
    tip = cv2.imdecode(np.frombuffer(tip, np.uint8), cv2.IMREAD_GRAYSCALE)
    tip = cv2.resize(tip, (round(tip.shape[1] * 80 / tip.shape[0]), 80))
    target = np.uint8(tip < 190) * 255
    matches = []
    for box in boxes:
        x, y, right, bottom = map(round, box)
        crop = board[y:bottom, x:right]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        vivid = (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 100)
        colors = crop[vivid].astype(np.int32) // 16
        if not len(colors):
            matches.append((0, 0))
            continue
        # A colored icon has a repeated foreground color; the photograph varies.
        ids = colors[:, 0] + 16 * colors[:, 1] + 256 * colors[:, 2]
        mode = int(np.bincount(ids, minlength=4096).argmax())
        color = np.median(crop[vivid][ids == mode], axis=0)
        mask = np.uint8(np.linalg.norm(crop.astype(float) - color, axis=2) < 38) * 255
        height, width = mask.shape
        scale = min(1, 180 / max(height, width))
        mask = cv2.resize(mask, (round(width * scale), round(height * scale)))
        height, width = mask.shape
        size = max(height, width) * 2
        padded = np.zeros((size, size), np.uint8)
        top, left = (size - height) // 2, (size - width) // 2
        padded[top:top + height, left:left + width] = mask
        best = (-1, 0)
        for angle in range(0, 360, 6):
            rotation = cv2.getRotationMatrix2D((size / 2, size / 2), angle, 1)
            rotated = cv2.warpAffine(padded, rotation, (size, size))
            x, y, width, height = cv2.boundingRect(rotated)
            if min(width, height) < 3:
                continue
            rotated = rotated[y:y + height, x:x + width]
            for length in range(40, 81, 4):
                scale = length / max(width, height)
                template = cv2.resize(rotated, (round(width * scale), round(height * scale)))
                if template.shape[0] > target.shape[0] or template.shape[1] > target.shape[1]:
                    continue
                result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, location = cv2.minMaxLoc(result)
                if confidence > best[0]:
                    best = (confidence, location[0] + template.shape[1] / 2)
        matches.append(best)
    return matches


def template_order(board, tip, boxes, count):
    """Override vision only for distinct, strong matches with separated centers."""
    ranked = sorted(enumerate(template_matches(board, tip, boxes), 1),
                    key=lambda item: item[1][0], reverse=True)
    selected = ranked[:count]
    if len(selected) != count or any(match[0] < .60 for _, match in selected):
        return []
    if len(ranked) > count and selected[-1][1][0] - ranked[count][1][0] < .10:
        return []
    ordered = sorted(selected, key=lambda item: item[1][1])
    if any(b[1][1] - a[1][1] < 28 for a, b in zip(ordered, ordered[1:])):
        return []
    return [index for index, _ in ordered]
