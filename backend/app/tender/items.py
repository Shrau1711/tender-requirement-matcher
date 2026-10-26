from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import groupby
from pathlib import Path

from pydantic import BaseModel

from app.reading.pdf_reader import PageRecord, RawTable, ReadDocument
from app.reading.tables import clean

# "Butterfly Valves (V2) As Per IS 13095 ( 50 pieces )" starts an item block.
ITEM_HEADING = re.compile(r"^(?P<title>.+?)\(\s*(?P<qty>\d+)\s*[A-Za-z]+\s*\)\s*$")
HEADER_CELL = re.compile(r"specification|allowed values|bid requirement", re.IGNORECASE)


class Item(BaseModel):
    title: str
    quantity: int | None = None  # None when the tender does not state one


class Requirement(BaseModel):
    item: Item
    group: str | None  # the heading a run of rows sits under, e.g. "TYPE / SIZE"
    name: str
    value: str
    pdf_page: int
    file: str = ""  # the tender document the row was read from


def parse_item(text: str) -> Item | None:
    match = ITEM_HEADING.match(clean(text))
    if not match:
        return None
    title = match["title"].split(" - ")[-1].strip()  # drop "Additional ... Parameters - "
    return Item(title=title, quantity=int(match["qty"]))


def in_page_order(page: PageRecord) -> list[tuple[float, Item | RawTable]]:
    """The item headings and the tables of a page, top to bottom. A heading comes before a table that starts where it ends."""
    headings = [(line.y1, item) for line in page.lines if (item := parse_item(line.text))]
    return sorted([*headings, *((table.bbox[1], table) for table in page.tables)], key=lambda entry: entry[0])


def is_header(name: str, value: str) -> bool:
    """The column titles of a specification table, however many times a page repeats them ("Specification Name | Bid Requirement (Allowed Values)")."""
    return bool(re.search("specification", name, re.IGNORECASE) and re.search("allowed values|bid requirement", value, re.IGNORECASE))


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
        if name and value and not is_header(name, value):
            result.append((group, name, value))
    return result


def read_requirements(doc: ReadDocument) -> list[Requirement]:
    """Technical requirements: name/value rows of tables that sit under an item heading."""
    requirements: list[Requirement] = []
    current: Item | None = None
    file = Path(doc.path).name
    for page in doc.pages:
        for _, entry in in_page_order(page):
            if isinstance(entry, Item):
                current = entry  # a heading at the foot of a page still names the table that opens the next one
            elif current is not None:
                for group, name, value in name_value_rows(entry):
                    requirements.append(
                        Requirement(item=current, group=group, name=name, value=value, pdf_page=page.pdf_page, file=file)
                    )
    return requirements


def by_item(requirements: list[Requirement]) -> list[tuple[Item, list[Requirement]]]:
    """Requirements grouped per item, in document order."""
    return [(item, list(rows)) for item, rows in groupby(requirements, key=lambda r: r.item)]


def distinct_items(items: Iterable[Item]) -> list[Item]:
    """The items without repeats, in the order they first appear."""
    found: list[Item] = []
    for item in items:
        if item not in found:
            found.append(item)
    return found
