"""Find and operate visual challenges on the original page, independent of its hostname."""

import asyncio
import math
import random
from base64 import b64decode
from contextlib import AsyncExitStack
from dataclasses import dataclass
from importlib.resources import files
from io import BytesIO

from PIL import Image, ImageDraw
from playwright.async_api import Error

from .puzzle_vision import visual_answer

DETECT = files(__package__).joinpath("detect_puzzle.js").read_text()
# Canvas readback preserves transparent margins and the original pixel dimensions.
PIXELS = """async el => {
    const canvas = document.createElement('canvas');
    const w = el.naturalWidth || el.width, h = el.naturalHeight || el.height;
    if (!(w && h) || w*h > 4000000) return null;
    canvas.width=w; canvas.height=h;
    try {
        canvas.getContext('2d').drawImage(el,0,0,w,h);
        return canvas.toDataURL('image/png').split(',')[1];
    } catch {
        if (!el.currentSrc) return null;
        try {
            const res=await fetch(el.currentSrc,{credentials:'omit',redirect:'error',signal:AbortSignal.timeout(3500)});
            if (!res.ok || !res.headers.get('Content-Type')?.startsWith('image/')) return null;
            const blob=await res.blob();
            if (blob.size > 4000000) return null;
            const reader=new FileReader();
            return await new Promise(resolve=>{
                reader.onload=()=>resolve(reader.result.split(',')[1]);
                reader.onerror=()=>resolve(null); reader.readAsDataURL(blob);
            });
        } catch { return null; }
    }
}"""
METRICS = r"""e => [e.currentSrc || getComputedStyle(e).backgroundImage.match(/^url\("(.*)"\)$/)?.[1] || '',
    e.naturalWidth || e.width || 0, e.naturalHeight || e.height || 0]"""


@dataclass
class Puzzle:
    kind: str
    parts: dict
    frame: object


async def detect(page, stack: AsyncExitStack):
    fallback = None
    # An open challenge wins over its still-mounted checkbox and form widgets.
    frames = sorted(page.frames, key=lambda f: 'frame=challenge' not in f.url)
    for frame in frames:
        if frame.parent_frame:
            ancestor = frame.parent_frame
            hidden = False
            while ancestor.parent_frame:
                outer = await ancestor.frame_element()
                stack.push_async_callback(outer.dispose)
                if not await outer.is_visible():
                    hidden = True
                    break
                ancestor = ancestor.parent_frame
            if hidden:
                continue
            element = await frame.frame_element()
            stack.push_async_callback(element.dispose)
            if not await element.is_visible() or not await element.evaluate("""e => {
                const r=e.getBoundingClientRect(), hit=e.ownerDocument.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
                return hit===e;
            }"""):
                continue
        result = await frame.evaluate_handle(DETECT, frame != page.main_frame)
        stack.push_async_callback(result.dispose)
        props = await result.get_properties()
        for prop in props.values():
            stack.push_async_callback(prop.dispose)
        if "kind" in props:
            parts = {k: v.as_element() for k, v in props.items() if v.as_element()}
            widget = Puzzle(await props["kind"].json_value(), {**parts, "cells": props.get("cells")}, frame)
            if widget.kind != "unresolved":
                return widget
            fallback = widget
    return fallback


async def image_bytes(frame, element, source):
    pixels = await element.evaluate(PIXELS)
    if pixels:
        return b64decode(pixels)
    if not source:
        return None
    # A tainted canvas is common for CDN-hosted pieces. Read only the image
    # already loaded by this frame, without issuing a credentialed request.
    try:
        session = await frame.page.context.new_cdp_session(frame)
    except Error:
        session = await frame.page.context.new_cdp_session(frame.page)
    try:
        tree = await session.send("Page.getResourceTree")
        frames = [tree["frameTree"]]
        for node in frames:
            frames.extend(node.get("childFrames", []))
            if node["frame"]["url"].split("#")[0] != frame.url.split("#")[0]:
                continue
            if any(
                asset["type"] == "Image" and asset["url"] == source for asset in node.get("resources", [])
            ):
                res = await session.send(
                    "Page.getResourceContent", {"frameId": node["frame"]["id"], "url": source}
                )
                if res["base64Encoded"] and len(res["content"]) <= 6_000_000:
                    return b64decode(res["content"])
    finally:
        await session.detach()
    return None


async def match_distance(widget):
    from .puzzle_images import gap_x

    board, piece = widget.parts["board"], widget.parts["piece"]
    metrics = await asyncio.gather(board.evaluate(METRICS), piece.evaluate(METRICS))
    a, b = metrics
    image, tile = await asyncio.gather(
        image_bytes(widget.frame, board, a[0]), image_bytes(widget.frame, piece, b[0])
    )
    board_box, piece_box = await asyncio.gather(board.bounding_box(), piece.bounding_box())
    if not all((board_box, piece_box, image, tile)):
        return None
    with Image.open(BytesIO(image)) as bg, Image.open(BytesIO(tile)) as fg:
        width, height = bg.size
        tile_width, tile_height = fg.size
        if max(width * height, tile_width * tile_height) > 4_000_000:
            return None
    # Readback uses naturalWidth for an image, canvas.width for a canvas.
    # Cached resources may have a different native density (e.g. srcset).
    scale = board_box["width"] / width
    scale_y = board_box["height"] / height
    row = (piece_box["y"] - board_box["y"]) / scale_y
    size = (piece_box["width"] / tile_width / scale, piece_box["height"] / tile_height / scale_y)
    intrinsic = await asyncio.to_thread(gap_x, image, tile, relative_size=size, row=row)
    if intrinsic is None or metrics != await asyncio.gather(board.evaluate(METRICS), piece.evaluate(METRICS)):
        return None
    # Subtract the *displayed* starting offset, including positioned ancestors and transforms.
    return board_box["x"] + intrinsic * scale - piece_box["x"]


async def visual_points(board):
    instruction = (
        "Find the movable piece and its matching gap. Return their center X positions "
        "and the piece center Y position as fractions of the image dimensions. "
        "Set all to zero if uncertain."
    )
    keys = ("piece", "hole", "y")
    schema = {"type": "object", "properties": {k: {"type": "number"} for k in keys}, "required": list(keys)}
    original = await board.screenshot(timeout=2500)
    answer = await asyncio.to_thread(visual_answer, original, instruction, schema)
    if original != await board.screenshot(timeout=2500):
        return None
    if (
        all(isinstance(answer.get(k), (float, int)) and 0 < answer[k] < 1 for k in keys)
        and answer["hole"] > answer["piece"]
    ):
        return answer
    return None


async def drag(page, widget, site):
    parts = widget.parts
    knob = parts.get("knob") or parts["board"]
    track = parts.get("track") or knob
    await page.bring_to_front()
    await knob.hover(timeout=2000)
    button, rail = await asyncio.gather(knob.bounding_box(), track.bounding_box())
    if not button or not rail:
        return False
    if widget.kind == "canvas_drag":
        points = await visual_points(knob)
        if not points:
            return False
        x = button["x"] + points["piece"] * button["width"]
        y = button["y"] + points["y"] * button["height"]
        distance = (points["hole"] - points["piece"]) * button["width"]
        return await drag_path(page, site, x, y, distance, button["x"] + button["width"] - x)
    if widget.kind == "range":
        # Chromium's native range thumb is square and centered vertically by default.
        button = {**rail, "width": min(rail["height"], rail["width"])}
        fraction = await knob.evaluate(
            "e=>(e.valueAsNumber-Number(e.min||0))/(Number(e.max||100)-Number(e.min||0))"
        )
        button["x"] += fraction * (rail["width"] - button["width"])
    travel = rail["x"] + rail["width"] - button["x"] - button["width"]
    distance = travel
    piece = parts.get("piece")
    if piece:
        delta = await match_distance(widget)
        if delta is None:
            return False
        board_box, tile = await asyncio.gather(parts["board"].bounding_box(), piece.bounding_box())
        if not board_box or not tile:
            return False
        remaining = board_box["x"] + board_box["width"] - tile["x"] - tile["width"]
        if remaining <= 0:
            return False
        distance = delta * travel / remaining
    elif widget.kind == "visual_slider":
        points = await visual_points(parts["board"])
        if not points:
            return False
        box = await parts["board"].bounding_box()
        if not box:
            return False
        distance = (points["hole"] - points["piece"]) * box["width"]
    if distance is None or not 1 < distance <= travel + 2 or page.url != site:
        return False
    x, y = button["x"] + button["width"] / 2, button["y"] + button["height"] / 2

    async def correct(position):
        # Sample the rendered piece after animation frames. Some rails have non-linear end padding.
        if piece:
            distance = position
            for _ in range(3):
                await widget.frame.evaluate(
                    "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
                )
                now = await piece.bounding_box()
                if not now or page.url != site:
                    return False
                moved = now["x"] - tile["x"]
                if abs(delta - moved) <= 1.5:
                    return True
                if moved < 1:
                    return False
                distance = min(travel, max(0.0, distance + (delta - moved) * distance / moved))
                await page.mouse.move(x + distance, y, steps=4)
        return True

    return await drag_path(page, site, x, y, distance, travel, correct)


async def drag_path(page, site, x, y, distance, travel, correct=None):
    if page.url != site:
        return False
    distance = min(distance, travel)
    peak = min(travel, distance + random.uniform(3, 5))
    await page.mouse.move(x, y)
    await page.mouse.down()
    try:
        for step in range(1, 30):
            if page.url != site:
                return False
            t = step / 29
            progress = t * t / 0.7 if t < 0.7 else 1 - (1 - t) ** 2 / 0.3
            await page.mouse.move(x + peak * progress, y + math.sin(math.pi * t) * random.uniform(-1.2, 1.2))
            await asyncio.sleep(random.uniform(0.009, 0.017))
        await asyncio.sleep(0.12)
        if page.url != site:
            return False
        await page.mouse.move(x + distance, y, steps=4)
        return await correct(distance) if correct else True
    finally:
        await page.mouse.up()


async def numbered_grid(scope, cells, board, image):
    # Work in frame-local CSS coordinates, even when the frame is cross-origin.
    bounds = "e => {const r=e.getBoundingClientRect(); return [r.x,r.y,r.width,r.height]}"
    sx, sy, sw, sh = await scope.evaluate(bounds)
    if cells:
        boxes = await cells.evaluate(
            "a=>a.map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})"
        )
    else:
        x, y, w, h = await board.evaluate(bounds)
        boxes = [(x + i % 3 * w / 3, y + i // 3 * h / 3, w / 3, h / 3) for i in range(9)]
    side = math.isqrt(len(boxes))
    source = Image.open(BytesIO(image)).convert("RGB")
    ax, ay = source.width / sw, source.height / sh
    mosaic = Image.new("RGB", (side * 144, side * 144), "white")
    draw = ImageDraw.Draw(mosaic)
    for i, (x, y, w, h) in enumerate(boxes):
        patch = source.crop(((x - sx) * ax, (y - sy) * ay, (x + w - sx) * ax, (y + h - sy) * ay))
        left, top = i % side * 144, i // side * 144
        mosaic.paste(patch.resize((142, 142)), (left, top))
        draw.rectangle((left, top, left + 25, top + 24), fill="white")
        draw.text((left + 3, top + 1), str(i + 1), fill="black", font_size=19)
    output = BytesIO()
    mosaic.save(output, format="PNG")
    return output.getvalue()


async def solve_grid(page, widget, site):
    parts = widget.parts
    scope = parts["scope"]
    cells = parts.get("cells")
    count = await cells.evaluate("a=>a.length") if cells else 9
    schema = {
        "type": "object",
        "properties": {"cells": {"type": "array", "items": {"type": "integer"}}},
        "required": ["cells"],
    }
    image = await scope.screenshot(timeout=2500)
    annotated = await numbered_grid(scope, cells, parts.get("board"), image)
    prompt = (await scope.inner_text()).strip()[:450]
    question = (
        f"The puzzle asks: {prompt}. Each tile has its number in the top left corner. "
        "Identify the tiles that match the requested object or color. Give only their printed numbers "
        'in the JSON field "cells". Return an empty array if none match.'
    )
    answer = await asyncio.to_thread(visual_answer, annotated, question, schema)
    selected = answer.get("cells")
    if (
        not isinstance(selected, list)
        or not selected
        or any(type(n) is not int or not 1 <= n <= count for n in selected)
    ):
        return False
    if page.url != site or image != await scope.screenshot(timeout=2500):
        return False
    for n in sorted(set(selected)):
        if page.url != site:
            return False
        if cells:
            cell = await cells.get_property(str(n - 1))
            try:
                if widget.kind == "hcaptcha_grid":
                    if not await viewport_click(page, cell.as_element(), site):
                        return False
                else:
                    await cell.as_element().click(timeout=2000)
            finally:
                await cell.dispose()
        else:
            board = parts["board"]
            box = await board.bounding_box()
            if not box:
                return False
            col, row = (n - 1) % 3, (n - 1) // 3
            await board.click(
                position={"x": (col + 0.5) * box["width"] / 3, "y": (row + 0.5) * box["height"] / 3},
                timeout=2000,
            )
    if page.url == site:
        if widget.kind == "hcaptcha_grid":
            return await viewport_click(page, parts["verify"], site)
        await parts["verify"].click(timeout=2000)
        return True
    return False


async def viewport_click(page, element, site):
    """Playwright mouse uses CDP Input events in top-level CSS viewport pixels."""
    if page.url != site or not await element.is_visible():
        return False
    await element.scroll_into_view_if_needed(timeout=2000)
    box = await viewport_box(element)
    if not box or page.url != site:
        return False
    await viewport_point(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    return True


async def viewport_point(page, x, y):
    # Let Chromium update its OOPIF hit-test data after scrolling/screenshotting
    # before pressing. Otherwise the first press can be delivered to the parent.
    await page.mouse.move(x, y)
    await asyncio.sleep(0.1)
    await page.mouse.click(x, y, delay=50)


async def viewport_box(element):
    """Map local CSS bounds through all iframe content origins into the viewport.

    Chromium's cross-process bounding boxes can omit iframe borders. Compute
    each content origin explicitly, including scrolling, borders and CSS scale.
    """
    box = await element.evaluate("e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}")
    frame = await element.owner_frame()
    while frame and frame.parent_frame:
        outer = await frame.frame_element()
        try:
            metrics = await outer.evaluate("""e=>{
                const r=e.getBoundingClientRect(), s=getComputedStyle(e);
                const sx=r.width/e.offsetWidth, sy=r.height/e.offsetHeight;
                return {x:r.x+(e.clientLeft+parseFloat(s.paddingLeft))*sx,
                        y:r.y+(e.clientTop+parseFloat(s.paddingTop))*sy,sx,sy};
            }""")
        finally:
            await outer.dispose()
        box = {"x": metrics["x"] + box["x"] * metrics["sx"],
               "y": metrics["y"] + box["y"] * metrics["sy"],
               "width": box["width"] * metrics["sx"], "height": box["height"] * metrics["sy"]}
        frame = frame.parent_frame
    return box if all(math.isfinite(v) for v in box.values()) and box["width"] > 0 and box["height"] > 0 else None


async def solve_hcaptcha_drag(page, widget, site):
    board = widget.parts["board"]
    image = await board.screenshot(timeout=2500)
    prompt = (await widget.parts["scope"].inner_text()).strip()[:450]
    keys = ("from_x", "from_y", "to_x", "to_y")
    schema = {"type": "object", "properties": {k: {"type": "number"} for k in keys},
              "required": list(keys)}
    answer = await asyncio.to_thread(
        visual_answer, image,
        f"The puzzle asks: {prompt}. Identify the correct movable item and its destination. "
        "Return their center coordinates as fractions of image width and height in "
        "from_x, from_y, to_x, to_y. All zeros if uncertain.", schema,
    )
    if any(type(answer.get(k)) not in (int, float) or not 0 < answer[k] < 1 for k in keys):
        return False
    if page.url != site or image != await board.screenshot(timeout=2500):
        return False
    box = await viewport_box(board)
    if not box:
        return False
    x, y = box["x"] + answer["from_x"] * box["width"], box["y"] + answer["from_y"] * box["height"]
    tx, ty = box["x"] + answer["to_x"] * box["width"], box["y"] + answer["to_y"] * box["height"]
    await page.mouse.move(x, y)
    await asyncio.sleep(0.1)
    await page.mouse.down()
    try:
        for step in range(1, 25):
            if page.url != site:
                return False
            await page.mouse.move(x + (tx-x)*step/24, y + (ty-y)*step/24)
            await asyncio.sleep(0.02)
    finally:
        await page.mouse.up()
    return await viewport_click(page, widget.parts["verify"], site)


async def solve_hcaptcha_points(page, widget, site):
    board = widget.parts["board"]
    image = await board.screenshot(timeout=2500)
    prompt = (await widget.parts["scope"].inner_text()).strip()[:450]
    schema = {"type": "object", "properties": {"points": {"type": "array", "items": {
        "type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
        "required": ["x", "y"]}}}, "required": ["points"]}
    answer = await asyncio.to_thread(visual_answer, image,
        f"The puzzle asks: {prompt}. Return the centers to click as points with x and y "
        "fractions of image width and height. Return an empty array if uncertain.", schema)
    points = answer.get("points")
    if (not isinstance(points, list) or not 1 <= len(points) <= 16 or
        any(not isinstance(p, dict) or any(type(p.get(k)) not in (int, float) or not 0 < p[k] < 1
                                           for k in ("x", "y")) for p in points)):
        return False
    if page.url != site or image != await board.screenshot(timeout=2500):
        return False
    for point in points:
        if page.url != site:
            return False
        box = await viewport_box(board)
        if not box:
            return False
        await viewport_point(page, box["x"] + point["x"] * box["width"], box["y"] + point["y"] * box["height"])
    return await viewport_click(page, widget.parts["verify"], site)


async def solve(page, widget, site):
    if widget.kind == "hcaptcha_checkbox":
        return await viewport_click(page, widget.parts["checkbox"], site)
    if widget.kind == "hcaptcha_drag":
        return await solve_hcaptcha_drag(page, widget, site)
    if widget.kind == "hcaptcha_points":
        return await solve_hcaptcha_points(page, widget, site)
    if widget.kind == "rotation":
        from ruin.auth.feishu import rotate

        return await rotate(page, widget.frame.locator(".vc-captcha-verify.whirl:visible"), site)
    if widget.kind in {"grid", "hcaptcha_grid"}:
        return await solve_grid(page, widget, site)
    if widget.parts.get("knob") or widget.kind == "canvas_drag":
        return await drag(page, widget, site)
    return False
