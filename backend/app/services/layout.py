from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from app.services.pdf_reader import Line

HEADING_RATIO = 1.5      # a heading's font is at least this many times the body font
COLUMN_TOLERANCE = 15    # max x-distance between a heading's left edge and its lines'
MAX_LINE_GAP = 30        # a section ends when the gap to the next line is bigger than this


class Field(BaseModel):
    label: str
    value: str


class Section(BaseModel):
    heading: str
    fields: list[Field]
    statements: list[str]  # bold lines with no value, or values with no label
    lines: list[str]       # the section's lines exactly as printed, heading first


def body_size(lines: list[Line]) -> float:
    return Counter(round(line.size, 1) for line in lines).most_common(1)[0][0]


def find_headings(lines: list[Line]) -> list[Line]:
    if not lines:
        return []
    body = body_size(lines)
    return [l for l in lines if l.bold and l.size >= body * HEADING_RATIO]


def lines_under(heading: Line, headings: list[Line], lines: list[Line]) -> list[Line]:
    """Lines that belong to this heading: same column, below it, nearest heading above."""
    owned: list[Line] = []
    last_bottom = heading.y1
    for line in sorted(lines, key=lambda l: l.y0):
        if line.y0 <= heading.y0 or line in headings:
            continue
        if abs(line.x0 - heading.x0) > COLUMN_TOLERANCE:
            continue
        nearer = [h for h in headings if abs(h.x0 - line.x0) <= COLUMN_TOLERANCE
                  and heading.y0 < h.y0 <= line.y0]
        if nearer or line.y0 - last_bottom > MAX_LINE_GAP:
            break
        owned.append(line)
        last_bottom = line.y1
    return owned


def split_fields(lines: list[Line]) -> tuple[list[Field], list[str]]:
    """A bold line starts a field; the non-bold lines after it are its value."""
    fields: list[Field] = []
    statements: list[str] = []
    label: str | None = None
    values: list[str] = []

    def flush() -> None:
        if label and values:
            fields.append(Field(label=label.rstrip(" :"), value=" ".join(values)))
        elif label:
            statements.append(label)
        statements.extend(values if not label else [])

    for line in lines:
        if line.bold:
            flush()
            label, values = line.text, []
        else:
            values.append(line.text)
    flush()
    return fields, statements


def build_sections(lines: list[Line]) -> list[Section]:
    headings = find_headings(lines)
    sections: list[Section] = []
    for h in sorted(headings, key=lambda l: (l.x0, l.y0)):
        owned = lines_under(h, headings, lines)
        fields, statements = split_fields(owned)
        if fields or statements:  # big bold text with nothing under it is not a section
            sections.append(Section(heading=h.text, fields=fields, statements=statements,
                                    lines=[h.text, *(l.text for l in owned)]))
    return sections