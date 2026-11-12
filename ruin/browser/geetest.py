"""Locate icon boxes, match the visible order, and click in CSS viewport space."""

import asyncio
import math
import random
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw

from .puzzle_vision import visual_answer


@lru_cache(maxsize=1)
def icon_detector():
    from ddddocr import DdddOcr

    return DdddOcr(det=True, ocr=False, show_ad=False)


def candidate_boxes(png):
    with Image.open(BytesIO(png)) as image:
        width, height = image.size
    if width * height > 4_000_000:
        return []
    boxes = []
    for raw in icon_detector().detection(png):
        if len(raw) != 4 or any(not math.isfinite(float(v)) for v in raw):
            continue
        x1, y1, x2, y2 = map(float, raw)
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        if not (8 <= x2 - x1 <= width * .65 and 8 <= y2 - y1 <= height * .65):
            continue
        boxes.append((x1, y1, x2, y2))
    # Remove duplicate/contained detections, keeping the larger icon box.
    keep = []
    for box in sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True):
        area = (box[2]-box[0])*(box[3]-box[1])
        if any(max(0, min(box[2], b[2])-max(box[0], b[0])) *
               max(0, min(box[3], b[3])-max(box[1], b[1])) / area > .7 for b in keep):
            continue
        keep.append(box)
    return sorted(keep) if 2 <= len(keep) <= 12 else []


def numbered_icons(board_png, tip_png, boxes):
    """Keep the prompt separate from a numbered gallery of exact icon crops."""
    board = Image.open(BytesIO(board_png)).convert('RGB')
    tip = Image.open(BytesIO(tip_png)).convert('RGB')
    columns, cell = min(4, len(boxes)), 170
    width = max(520, columns * cell)
    tip.thumbnail((width - 32, 140))
    scale = min((width - 32) / tip.width, 140 / tip.height)
    tip = tip.resize((round(tip.width * scale), round(tip.height * scale)))
    top = tip.height + 65
    out = Image.new('RGB', (width, top + math.ceil(len(boxes)/columns)*cell), 'white')
    draw = ImageDraw.Draw(out)
    draw.text((12, 6), 'TARGET ORDER: left to right', fill='black', font_size=22)
    out.paste(tip, (12, 35))
    for i, box in enumerate(boxes):
        x, y = (i % columns)*cell, top + (i // columns)*cell
        crop = board.crop(tuple(map(round, box)))
        crop.thumbnail((cell-16, cell-36))
        out.paste(crop, (x+8, y+30))
        draw.text((x+8, y), str(i+1), fill='black', font_size=24)
    output = BytesIO()
    out.save(output, format='PNG')
    return output.getvalue()


def match_order(board, tip, boxes):
    import numpy as np
    from .geetest_shapes import template_order

    schema = {'type': 'object', 'properties': {'target_count': {'type': 'integer'}, 'order': {
        'type': 'array', 'items': {'type': 'integer'}}}, 'required': ['target_count', 'order']}
    answer = visual_answer(numbered_icons(board, tip, boxes),
        'Read ONLY the top strip first. Count its target symbols. Then, for EACH target '
        'symbol from LEFT to RIGHT, select its ONE matching numbered candidate below. '
        'The lower row includes distractors which must be omitted. Return target_count '
        'and order; len(order) MUST equal target_count. Compare the internal strokes, '
        'not just the outline, ignoring rotation, color and background. Do not append '
        'unmatched candidates or sort the numbers. Return [] if uncertain.', schema)
    order = answer.get('order')
    if (not isinstance(order, list) or not 1 <= len(order) <= len(boxes) or
            type(answer.get('target_count')) is not int or len(order) != answer['target_count'] or
            any(type(n) is not int or not 1 <= n <= len(boxes) for n in order) or
            len(set(order)) != len(order)):
        return []
    matched = template_order(board, tip, boxes, len(order))
    if matched:
        return matched
    # The provider's prompt lays out uniformly spaced symbol slots. Ask about
    # each slot separately: a small model can identify symbols yet swap order
    # when it reads the whole strip and gallery in one pass.
    prompt = Image.open(BytesIO(tip)).convert('RGB')
    columns = np.flatnonzero((np.array(prompt.convert('L')) < 190).any(axis=0))
    if not len(columns):
        return []
    left, right = int(columns[0]), int(columns[-1]) + 1
    matched = []
    schema = {'type': 'object', 'properties': {'candidate': {'type': 'integer'}}, 'required': ['candidate']}
    for index in range(len(order)):
        crop = prompt.crop((round(left + (right-left)*index/len(order)), 0,
                            round(left + (right-left)*(index+1)/len(order)), prompt.height))
        output = BytesIO()
        crop.save(output, 'PNG')
        answer = visual_answer(numbered_icons(board, output.getvalue(), boxes),
            'The TOP panel contains ONE target symbol. Which ONE numbered candidate '
            'below depicts the same object or symbol? Ignore rotation, color, square '
            'borders and background. Compare the inner symbol. Return its candidate '
            'number only, or 0 if uncertain.', schema)
        candidate = answer.get('candidate')
        if type(candidate) is not int or not 1 <= candidate <= len(boxes) or candidate in matched:
            return []
        matched.append(candidate)
    return matched


async def solve_icons(page, widget, site):
    from .background import prepare_page
    from .puzzles import viewport_box, viewport_click, viewport_point

    board, tip = widget.parts['board'], widget.parts['tip']
    await prepare_page(page)
    await board.scroll_into_view_if_needed(timeout=2000)
    original = await board.screenshot(timeout=2500)
    prompt = await tip.screenshot(timeout=2500)
    identity = "e => [e.currentSrc || '', getComputedStyle(e).backgroundImage]"
    sources = await asyncio.gather(board.evaluate(identity), tip.evaluate(identity))
    boxes = await asyncio.to_thread(candidate_boxes, original)
    if not boxes:
        return False
    order = await asyncio.to_thread(match_order, original, prompt, boxes)
    if (not order or page.url != site or original != await board.screenshot(timeout=2500) or
            prompt != await tip.screenshot(timeout=2500)):
        return False
    with Image.open(BytesIO(original)) as image:
        width, height = image.size
    # The bitmap may be DPR-scaled. Always recompute the current CSS box;
    # never use screenshot pixels as mouse coordinates or multiply by DPR.
    for n in order:
        if (page.url != site or not await board.is_visible() or sources !=
                await asyncio.gather(board.evaluate(identity), tip.evaluate(identity))):
            return False
        box = await viewport_box(board)
        if not box:
            return False
        x1, y1, x2, y2 = boxes[n-1]
        x = box['x'] + (x1+x2)/2/width*box['width']
        y = box['y'] + (y1+y2)/2/height*box['height']
        await viewport_point(page, x, y)
        await asyncio.sleep(random.uniform(.25, .4))
    await asyncio.sleep(.3)
    if page.url != site or await widget.parts['verify'].evaluate(
        "e => e.matches('.geetest_disable, [aria-disabled=true], :disabled')"
    ):
        return False
    return await viewport_click(page, widget.parts['verify'], site)
