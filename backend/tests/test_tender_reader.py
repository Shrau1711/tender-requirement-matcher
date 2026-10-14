import json
import shutil
from collections import Counter
from pathlib import Path

import pymupdf
import pytest
from conftest import FakeLLM
from test_ocr import picture_only_pdf
from test_tender import SPEC, doc, heading, table

from app.services.pdf_reader import PageRecord, ReadDocument, read_pdf
from app.services.tender import Item
from app.services.tender_files import read_tender_documents, tender_pdfs
from app.services.tender_reader import (
    ALL_ITEMS,
    MAX_BATCH_CHARS,
    batches,
    on_page,
    read_document,
    read_tender,
    states_quantity,
)

GATE = "Gate valve 250 mm, rating 1500#, body material A217 WC9"
PAGE_TEXT = f"1. {GATE}\nEnd connection: butt weld\nTesting standard: API 598"


def pdf(path, *pages: str):
    document = pymupdf.open()
    for text in pages:
        document.new_page().insert_text((72, 72), text)
    document.save(path)
    return path


def row(item: str, name: str, value: str, quote: str, page: int = 1) -> dict:
    return {"item": item, "name": name, "value": value, "quote": quote, "page": page}


def reply(items: list[dict] | None = None, rows: list[dict] | None = None) -> str:
    return json.dumps({"items": items or [], "rows": rows or []})


def tender_folder(tmp_path, text: str = PAGE_TEXT):
    folder = tmp_path / "GeM-Bidding-1"
    folder.mkdir()
    pdf(folder / "GeM-Bidding-1.pdf", text)
    return folder


def page(n: int, chars: int) -> PageRecord:
    return PageRecord(pdf_page=n, text="x" * chars, n_chars=chars, n_images=0, needs_ocr=False, lines=[])


def test_the_bid_document_comes_first_and_a_copy_is_read_once(tmp_path):
    pdf(tmp_path / "GeM-Bidding-1.pdf", "The bid document lists the items to be bought, with quantities")
    pdf(tmp_path / "spec.pdf", "The specification states the size, rating and material of every item")
    shutil.copy(tmp_path / "spec.pdf", tmp_path / "spec2.pdf")
    read = read_tender_documents(tmp_path)
    assert [p.name for p in tender_pdfs(tmp_path)] == ["GeM-Bidding-1.pdf", "spec.pdf", "spec2.pdf"]
    assert [Path(d.path).name for d in read.documents] == ["GeM-Bidding-1.pdf", "spec.pdf"]
    assert read.duplicates == ["spec2.pdf"]


def test_a_single_pdf_is_a_tender_of_one_file(tmp_path):
    path = pdf(tmp_path / "tender.pdf", "A tender that is a single file, with enough text to count")
    assert tender_pdfs(path) == [path]


def test_a_folder_without_pdfs_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="No PDF files"):
        tender_pdfs(tmp_path)


def test_requirements_come_with_their_item_file_and_page(tmp_path):
    llm = FakeLLM([reply([{"label": "Valve Gate 250", "quantity": 10}], [row("Valve Gate 250", "Rating", "1500#", "rating 1500#")])])
    read = read_tender(llm, tender_folder(tmp_path))
    [r] = read.requirements
    assert (r.item.title, r.item.quantity, r.name, r.value, r.file, r.pdf_page) == ("Valve Gate 250", 10, "Rating", "1500#", "GeM-Bidding-1.pdf", 1)
    assert read.notes == []


def test_a_quote_that_is_not_on_the_page_is_dropped_and_reported(tmp_path):
    rows = [row("Valve Gate 250", "Rating", "1500#", "rating 1500#"), row("Valve Gate 250", "Seat", "PTFE", "PTFE seat")]
    read = read_tender(FakeLLM([reply([{"label": "Valve Gate 250"}], rows)]), tender_folder(tmp_path))
    assert [r.name for r in read.requirements] == ["Rating"]
    assert any("quote was not found" in n for n in read.notes)


def test_a_requirement_for_an_item_that_does_not_exist_is_dropped_and_reported(tmp_path):
    rows = [row("Valve Gate 250", "Rating", "1500#", "rating 1500#"), row("Ball valve", "Rating", "1500#", "rating 1500#")]
    read = read_tender(FakeLLM([reply([{"label": "Valve Gate 250"}], rows)]), tender_folder(tmp_path))
    assert len(read.requirements) == 1 and any("does not exist" in n for n in read.notes)


def test_a_requirement_for_all_items_is_given_to_each_item_and_rows_are_in_item_order(tmp_path):
    items = [{"label": "Valve A", "quantity": 1}, {"label": "Valve B", "quantity": 2}]
    rows = [row("Valve B", "Size", "80", "Gate valve 250 mm"), row(ALL_ITEMS, "Testing", "API 598", "Testing standard: API 598"), row("Valve A", "Size", "250", "Gate valve 250 mm")]
    read = read_tender(FakeLLM([reply(items, rows)]), tender_folder(tmp_path))
    assert [(r.item.title, r.name) for r in read.requirements] == [
        ("Valve A", "Testing"), ("Valve A", "Size"), ("Valve B", "Size"), ("Valve B", "Testing"),
    ]


def test_the_same_requirement_stated_twice_counts_once(tmp_path):
    rows = [row("Valve A", "Rating", "1500#", "rating 1500#"), row("Valve A", " rating", "1500# ", "rating 1500#")]
    assert len(read_tender(FakeLLM([reply([{"label": "Valve A"}], rows)]), tender_folder(tmp_path)).requirements) == 1


def test_items_found_in_earlier_documents_are_told_to_the_model_for_later_ones(tmp_path):
    folder = tender_folder(tmp_path, "Item list: Valve Gate 250, quantity 10, supply to the site")
    pdf(folder / "spec.pdf", PAGE_TEXT)
    llm = FakeLLM([reply([{"label": "Valve Gate 250", "quantity": 10}]), reply(rows=[row("Valve Gate 250", "Rating", "1500#", "rating 1500#")])])
    read = read_tender(llm, folder)
    assert json.loads(llm.prompts[0])["known_items"] == []
    assert json.loads(llm.prompts[1])["known_items"] == [{"label": "Valve Gate 250", "quantity": 10}]
    assert read.requirements[0].item.quantity == 10


def test_an_item_without_requirements_is_reported(tmp_path):
    read = read_tender(FakeLLM([reply([{"label": "Valve Gate 250"}])]), tender_folder(tmp_path))
    assert read.requirements == [] and any("Valve Gate 250" in n and "no requirements" in n for n in read.notes)


def test_a_tender_with_no_items_is_reported(tmp_path):
    assert any("no items" in n for n in read_tender(FakeLLM([reply()]), tender_folder(tmp_path)).notes)


def test_pages_read_from_pictures_are_reported(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    picture_only_pdf(folder / "GeM-Bidding-1.pdf")
    read = read_tender(FakeLLM([reply()]), folder, lambda png: PAGE_TEXT)
    assert any("scanned images" in n for n in read.notes)


def test_a_page_that_could_not_be_read_is_reported(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    picture_only_pdf(folder / "GeM-Bidding-1.pdf")
    read = read_tender(FakeLLM([]), folder, lambda png: "")
    assert any("no text could be read from pages [1]" in n for n in read.notes)


def test_a_document_with_specification_tables_is_read_without_the_model():
    document = doc([heading("Valves ( 5 pieces )", 150)], [table(200, SPEC)])
    items: dict[str, Item] = {}
    found = read_document(FakeLLM([]), document, items, Counter())
    assert [r.name for r in found] == ["Nominal Size (DN) (mm)", "Nominal Pressure (PN) (MPa)"] and list(items) == ["valves"]


def test_pages_are_grouped_up_to_a_size_and_empty_pages_are_left_out():
    document = ReadDocument(path="t.pdf", sha256="0", n_pages=4, pages=[page(1, 5000), page(2, 0), page(3, MAX_BATCH_CHARS - 5000), page(4, 5000)])
    assert [[p.pdf_page for p in group] for group in batches(document)] == [[1, 3], [4]]


def test_a_drawn_page_is_part_of_a_tender_like_any_other(tmp_path):
    path = tmp_path / "drawn.pdf"
    document = pymupdf.open()
    new = document.new_page()
    for n in range(30):
        new.draw_rect(pymupdf.Rect(10, 10 + n * 20, 100, 20 + n * 20))
    document.save(path)
    assert read_pdf(path, lambda png: PAGE_TEXT).pages[0].ocr


def test_a_quote_may_differ_from_the_page_in_spacing_and_punctuation_but_not_in_letters_and_digits():
    assert on_page("DESIGN STANDARD: ASME B16.34", "DESIGN \nSTANDARD:ASME \nB16.34,TESTING")
    assert not on_page("DESIGN STANDARD: ASME B16.35", "DESIGN STANDARD:ASME B16.34")


def test_a_dropped_requirement_is_reported_with_what_was_dropped(tmp_path):
    read = read_tender(FakeLLM([reply([{"label": "Valve Gate 250"}], [row("Valve Gate 250", "Seat", "PTFE", "PTFE seat")])]), tender_folder(tmp_path))
    assert any("Seat = PTFE" in n for n in read.notes)


def test_a_quantity_found_in_a_later_document_is_given_to_the_item_found_earlier(tmp_path):
    folder = tender_folder(tmp_path, "Item list: Valve Gate 250 to be supplied")
    pdf(folder / "spec.pdf", f"{PAGE_TEXT}\nRequired quantity 10 NOS")
    quantity = {"items": [], "quantities": [{"label": "Valve Gate 250", "quantity": 10}], "rows": [row("Valve Gate 250", "Rating", "1500#", "rating 1500#")]}
    read = read_tender(FakeLLM([reply([{"label": "Valve Gate 250"}]), json.dumps(quantity)]), folder)
    assert read.requirements[0].item.quantity == 10


def test_a_quantity_is_accepted_only_when_the_number_stands_alone_on_the_pages():
    assert states_quantity(10, "NOS 10 ") and not states_quantity(10, "100 or 1.10 or 10.5")


def test_the_model_reads_a_table_with_its_cells_whole_and_a_quote_from_a_cell_is_accepted():
    from app.services.pdf_reader import RawTable
    from app.services.tender_reader import page_text

    mixed = PageRecord(pdf_page=1, text="DESIGN\n 1 1600 STANDARD:ASME", n_chars=30, n_images=0, needs_ocr=False, lines=[],
                       tables=[RawTable(bbox=(0, 0, 1, 1), rows=[["1", "DESIGN\nSTANDARD:ASME B16.34", None]])])
    assert "1 | DESIGN STANDARD:ASME B16.34 | " in page_text(mixed)
    assert on_page("DESIGN STANDARD:ASME B16.34", page_text(mixed))


def test_a_heading_that_only_names_the_goods_in_general_is_not_an_item(tmp_path):
    folder = tender_folder(tmp_path, "Supply of valves for the plant, as listed in the schedule of this bid")
    pdf(folder / "spec.pdf", PAGE_TEXT)
    bid = {"items": [{"label": "Supply of valves", "quantity": 1}], "rows": [row("Supply of valves", "Warranty", "1 year", "Supply of valves for the plant")]}
    spec = {"items": [{"label": "Valve A", "quantity": 2}, {"label": "Valve B", "quantity": 3}], "rows": [
        row("Valve A", "Rating", "1500#", "rating 1500#"), row("Valve B", "Testing", "API 598", "Testing standard: API 598"), row(ALL_ITEMS, "End", "butt weld", "End connection: butt weld")]}
    read = read_tender(FakeLLM([json.dumps(bid), json.dumps(spec)]), folder)
    assert {r.item.title for r in read.requirements} == {"Valve A", "Valve B"}
    assert any("Supply of valves" in n and "heading" in n for n in read.notes)
