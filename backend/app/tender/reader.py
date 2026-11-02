from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.extraction.evidence import squash
from app.llm.llm import LLM, ask
from app.reading.ocr import ImageReader
from app.reading.pdf_reader import MIN_TEXT_CHARS, PageRecord, ReadDocument
from app.tender.files import BID_DOCUMENT_PREFIX, read_tender_documents
from app.tender.items import Item, Requirement, read_requirements

ALL_ITEMS = "ALL ITEMS"  # the label for a requirement that applies to every item of the tender
MAX_BATCH_CHARS = 12000  # pages are read a few at a time, so one reply stays short and a failure costs little

SYSTEM = f"""You read pages of a tender (a buyer's request to buy goods) and list what the buyer wants to buy and what the goods must be.
The input has "known_items" (items already found in earlier pages, with quantities) and "pages" (each with a page number and its text). A page's text can mix up the columns of a table, so after it come the page's tables, one row per line with cells separated by " | "; read tables from there.
Reply with:
- items: items to be bought that these pages name and that are not in known_items. "label" is the item as printed, with its item code if there is one, kept short. "quantity" is the number as printed, or null.
- quantities: for items in known_items whose quantity is null, the quantity these pages state for them. "label" is copied exactly from known_items.
- rows: requirements for the goods. "item" is a label from known_items or from the items you just listed, copied exactly, or "{ALL_ITEMS}" when the requirement applies to every item. "name" says what is specified, "value" is what is required, as printed. "quote" is copied word for word from the page, as short as possible while still showing the requirement. "page" is the page number it is on.
Rules:
- A requirement is about the goods: type, size, rating, pressure, temperature, material, construction, design, performance, accessories, a standard the goods must meet, how the goods are tested, warranty, and documents or certificates that come with the goods. Working conditions the goods must suit (flow, head, pressure, temperature, fluid) count.
- These are not requirements: prices, payment, deposits, delivery dates and places, the bidder's finances or experience, penalties, arbitration, purchase preferences (Make in India, MSE), how to use the bidding portal, form templates, lists of vendors. If the pages hold only such terms, reply with empty lists.
- An item is one kind of goods to buy, as a price schedule would list it. A heading that names the goods of the whole tender is not an item when the tender lists specific types or models of them.
- Where a table or description gives different values for different types, sizes or models of the same goods, make each its own item and give each its own rows.
- When a table or datasheet names tag numbers, sizes or item codes, its values belong only to the item with those tags, size or code, never to another item. Several datasheets may repeat the same item; give each row to the item it names.
- Copy values exactly as printed. Never convert units, calculate, or fill in what is not there. Leave out what you cannot read."""


class NewItem(BaseModel):
    label: str
    quantity: int | None = None


class Row(BaseModel):
    item: str
    name: str
    value: str
    quote: str
    page: int


class PageReading(BaseModel):
    items: list[NewItem] = []
    quantities: list[NewItem] = []
    rows: list[Row] = []


def letters_and_digits(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def on_page(quote: str, text: str) -> bool:
    """True when the quote's letters and digits appear in order on the page. Spacing, line breaks and punctuation may differ, as tables split them oddly; the letters and digits may not."""
    wanted = letters_and_digits(quote)
    return bool(wanted) and wanted in letters_and_digits(text)


def states_quantity(quantity: int, text: str) -> bool:
    """True when the number stands alone somewhere on the pages, so a quantity the model invented is not accepted."""
    return re.search(rf"(?<![\d.,]){quantity}(?![\d.,]*\d)", text) is not None


@dataclass
class TenderRead:
    requirements: list[Requirement]
    notes: list[str]  # what a reader of the report should know about how the tender was read


def batches(doc: ReadDocument) -> list[list[PageRecord]]:
    """Consecutive pages with text, in groups that fit one reading. Pages without any text are left out."""
    groups: list[list[PageRecord]] = [[]]
    size = 0
    for page in (p for p in doc.pages if p.n_chars >= MIN_TEXT_CHARS):
        if groups[-1] and size + page.n_chars > MAX_BATCH_CHARS:
            groups.append([])
            size = 0
        groups[-1].append(page)
        size += page.n_chars
    return [g for g in groups if g]


def page_text(page: PageRecord) -> str:
    """What the model reads for a page: its text, then its tables with each cell kept whole (the text alone mixes up table columns)."""
    tables = [" | ".join(" ".join((cell or "").split()) for cell in row) for table in page.tables for row in table.rows]
    return page.text + ("\nTABLES\n" + "\n".join(tables) if tables else "")


def reading_prompt(items: dict[str, Item], pages: list[PageRecord]) -> str:
    known = [{"label": i.title, "quantity": i.quantity} for i in items.values()]
    return json.dumps({"known_items": known, "pages": [{"page": p.pdf_page, "text": page_text(p)} for p in pages]})


def read_batch(llm: LLM, file: str, pages: list[PageRecord], items: dict[str, Item], dropped: Counter) -> list[Requirement]:
    """The requirements the model finds in a few pages. New items are added to `items`. Rows that cannot be trusted are counted in `dropped`."""
    reading = ask(llm, SYSTEM, reading_prompt(items, pages), PageReading)
    for new in reading.items:
        items.setdefault(squash(new.label), Item(title=new.label.strip(), quantity=new.quantity))
    for new in reading.quantities:
        item = items.get(squash(new.label))
        if item and item.quantity is None and new.quantity and states_quantity(new.quantity, " ".join(p.text for p in pages)):
            item.quantity = new.quantity
    text = {p.pdf_page: page_text(p) for p in pages}
    found = []
    for row in reading.rows:
        item = Item(title=ALL_ITEMS) if squash(row.item) == squash(ALL_ITEMS) else items.get(squash(row.item))
        if item is None:
            dropped[f"a requirement named an item that does not exist ({row.item}: {row.name} = {row.value})"] += 1
        elif row.page not in text or not on_page(row.quote, text[row.page]):
            dropped[f"a requirement's quote was not found on its page ({row.item}: {row.name} = {row.value}, quote '{row.quote}')"] += 1
        else:
            found.append(Requirement(item=item, group=None, name=row.name, value=row.value, pdf_page=row.page, file=file))
    return found


def read_document(llm: LLM, doc: ReadDocument, items: dict[str, Item], dropped: Counter) -> list[Requirement]:
    """A document with GeM specification tables is read by plain code. Any other document is read by the model."""
    file = Path(doc.path).name
    rows = read_requirements(doc)
    if rows:
        for row in rows:
            items.setdefault(squash(row.item.title), row.item)
        return rows
    return [r for pages in batches(doc) for r in read_batch(llm, file, pages, items, dropped)]


def headings(rows: list[Requirement], items: dict[str, Item]) -> list[str]:
    """Keys of items that only head the tender. The bid document names the goods in general, and the attached specification then lists the real types: an item that no attached specification row names, while two or more others have rows of their own, is that heading."""
    own = {squash(r.item.title) for r in rows if r.item.title != ALL_ITEMS and not r.file.lower().startswith(BID_DOCUMENT_PREFIX)}
    return [key for key in items if key not in own] if len(own) >= 2 else []


def spread_shared(rows: list[Requirement], items: dict[str, Item]) -> list[Requirement]:
    """A requirement for every item becomes one row for each item, and rows are put in item order."""
    order = {squash(i.title): n for n, i in enumerate(items.values())}
    unique: dict[tuple[str, str, str], Requirement] = {}  # the same row twice counts once
    for row in rows:
        for item in items.values() if row.item.title == ALL_ITEMS else [row.item]:
            copy = row.model_copy(update={"item": item})
            unique.setdefault((squash(item.title), squash(row.name), squash(row.value)), copy)
    return sorted(unique.values(), key=lambda r: order[squash(r.item.title)])


def notes_for(documents: list[ReadDocument], duplicates: list[str], dropped: Counter, items: dict[str, Item], rows: list[Requirement], heads: list[str]) -> list[str]:
    notes = [f"{name} is a copy of an earlier file and was not read again" for name in duplicates]
    notes += [f"'{title}' was treated as the heading of the tender, not as an item, because the attached specification lists its own types" for title in heads]
    for doc in documents:
        scanned = [p.pdf_page for p in doc.pages if p.ocr and p.n_chars >= MIN_TEXT_CHARS]
        blank = [p.pdf_page for p in doc.pages if p.needs_ocr and p.n_chars < MIN_TEXT_CHARS]
        name = Path(doc.path).name
        if scanned:
            notes.append(f"{name}: {len(scanned)} page(s) were read from scanned images, so some words may be misread")
        if blank:
            notes.append(f"{name}: no text could be read from pages {blank}")
    notes += [f"{count} requirement(s) dropped: {why}" for why, count in dropped.items()]
    with_rows = {squash(r.item.title) for r in rows}
    notes += [f"item '{i.title}' has no requirements in the documents, so it is not evaluated" for key, i in items.items() if key not in with_rows]
    if not items:
        notes.append("no items to buy were found in the tender documents")
    return notes


def read_tender(llm: LLM, path: str | Path, read_image: ImageReader | None = None) -> TenderRead:
    """Every item of a tender and its requirements, from all the PDFs of the tender."""
    read = read_tender_documents(path, read_image)
    items: dict[str, Item] = {}
    dropped: Counter = Counter()
    rows = [r for doc in read.documents for r in read_document(llm, doc, items, dropped)]
    heads = {key: items.pop(key).title for key in headings(rows, items)}
    rows = spread_shared([r for r in rows if squash(r.item.title) not in heads], items)
    return TenderRead(rows, notes_for(read.documents, read.duplicates, dropped, items, rows, list(heads.values())))
