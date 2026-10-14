from __future__ import annotations

import re
from itertools import groupby

from pydantic import BaseModel

from app.services.pdf_reader import PageRecord, RawTable, ReadDocument
from app.services.tables import clean

# "Butterfly Valves (V2) As Per IS 13095 ( 50 pieces )" starts an item block.
ITEM_HEADING = re.compile(r"^(?P<title>.+?)\(\s*(?P<qty>\d+)\s*[A-Za-z]+\s*\)\s*$")
HEADER_CELL = re.compile(r"specification|allowed values|bid requirement", re.IGNORECASE)


class Item(BaseModel):
    title: str
    quantity: int


class Requirement(BaseModel):
    item: Item
    group: str | None  # the heading a run of rows sits under, e.g. "TYPE / SIZE"
    name: str
    value: str
    pdf_page: int


def parse_item(text: str) -> Item | None:
    match = ITEM_HEADING.match(clean(text))
    if not match:
        return None
    title = match["title"].split(" - ")[-1].strip()  # drop "Additional ... Parameters - "
    return Item(title=title, quantity=int(match["qty"]))


def item_above(page: PageRecord, table: RawTable) -> Item | None:
    """The nearest item heading printed above the table on this page."""
    above = [line for line in page.lines if line.y1 <= table.bbox[1] and parse_item(line.text)]
    return parse_item(max(above, key=lambda line: line.y1).text) if above else None


def name_value_rows(table: RawTable) -> list[tuple[str | None, str, str]]:
    """(group, name, value) per row of a 2 or 3 column table, header and spacer rows dropped."""
    width = max(len(row) for row in table.rows)
    if width not in (2, 3):
        return []
    rows = table.rows[1:] if any(HEADER_CELL.search(clean(c)) for c in table.rows[0]) else table.rows
    result, group = [], None
    for row in rows:
        cells = [clean(c) for c in row]
        name, value = cells[-2], cells[-1]
        if width == 3 and cells[0]:
            group = cells[0]
        if name and value:
            result.append((group, name, value))
    return result


def read_requirements(doc: ReadDocument) -> list[Requirement]:
    """Technical requirements: name/value rows of tables that sit under an item heading."""
    requirements: list[Requirement] = []
    current: Item | None = None
    for page in doc.pages:
        for table in sorted(page.tables, key=lambda t: t.bbox[1]):
            current = item_above(page, table) or current
            if current is None:
                continue
            for group, name, value in name_value_rows(table):
                requirements.append(
                    Requirement(item=current, group=group, name=name, value=value, pdf_page=page.pdf_page)
                )
    return requirements


def by_item(requirements: list[Requirement]) -> list[tuple[Item, list[Requirement]]]:
    """Requirements grouped per item, in document order."""
    return [(item, list(rows)) for item, rows in groupby(requirements, key=lambda r: r.item)]