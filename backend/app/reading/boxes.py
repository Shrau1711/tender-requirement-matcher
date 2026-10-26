"""Finding the boxes of a flowchart on a PDF page, and the lines drawn between them.

A box is a drawn rectangle about the size of a few words that holds text and stands apart from other rectangles.
Table cells are rectangles too, but they share their edges, so a rectangle touching another one is not a box.
"""
from __future__ import annotations

import pymupdf

BOX_WIDTH = (15, 300)   # a rectangle this wide and this high can be a box around a few words
BOX_HEIGHT = (8, 120)
BOX_GAP = 2             # points of space a box keeps from every other rectangle
REACH = 4               # a drawn line ending this close to a box is joined to it

Box = tuple[float, float, float, float]


def text_boxes(page: pymupdf.Page) -> list[Box]:
    """The boxes on the page, top to bottom and left to right."""
    (low_w, high_w), (low_h, high_h) = BOX_WIDTH, BOX_HEIGHT
    found = {tuple(d["rect"]) for d in page.get_drawings()  # a box drawn twice (fill, then border) counts once
             if any(item[0] == "re" for item in d["items"]) and low_w < d["rect"].width < high_w and low_h < d["rect"].height < high_h}
    rects = [pymupdf.Rect(r) for r in found]
    apart = [r for r in rects if not any(o is not r and (r + (-BOX_GAP, -BOX_GAP, BOX_GAP, BOX_GAP)).intersects(o) for o in rects)]
    words = [pymupdf.Rect(w[:4]) for w in page.get_text("words")]
    return sorted((tuple(r) for r in apart if any(r.contains(w) for w in words)), key=lambda b: (round(b[1]), b[0]))


def box_at(point: pymupdf.Point, boxes: list[Box]) -> int | None:
    for i, box in enumerate(boxes):
        if (pymupdf.Rect(box) + (-REACH, -REACH, REACH, REACH)).contains(point):
            return i
    return None


def box_links(page: pymupdf.Page, boxes: list[Box]) -> list[tuple[int, int]]:
    """(from, to) for each straight line drawn from one box to another, as positions in `boxes`.

    A line has no direction of its own, so it is read top to bottom (left to right when level), the way flowcharts run."""
    links = set()
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            ends = sorted([item[1], item[2]], key=lambda p: (round(p.y), p.x))
            start, end = box_at(ends[0], boxes), box_at(ends[1], boxes)
            if start is not None and end is not None and start != end:
                links.add((start, end))
    return sorted(links)
