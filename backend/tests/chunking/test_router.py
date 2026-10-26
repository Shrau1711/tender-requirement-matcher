import pytest

from app.chunking.router import choose, chunker_for
from app.reading.pdf_reader import Line, PageRecord, RawTable, ReadDocument


def line(text, block, bold=False):
    return Line(text=text, x0=0, y0=10 * block, x1=200, y1=10 * block + 9, size=10, bold=bold, block=block)


def doc(*pages: PageRecord) -> ReadDocument:
    return ReadDocument(path="x/ksb/k.pdf", sha256="s", n_pages=len(pages), pages=list(pages))


def page(lines, tables=()) -> PageRecord:
    return PageRecord(pdf_page=1, text="", n_chars=0, n_images=0, needs_ocr=False, lines=lines, tables=list(tables))


TABLE = RawTable(bbox=(0, 0, 100, 100), rows=[["DN", "PN", "Weight"], ["50", "16", "4"]])


def test_a_document_of_numbered_clauses_is_chunked_by_its_structure():
    lines = [line(f"{i}. Clause number {i}", i) for i in range(1, 10)]
    assert choose(doc(page(lines)))[0] == "structure"


def test_a_catalogue_with_tables_keeps_the_original_strategy():
    assert choose(doc(page([line("Pressure ratings", 0, bold=True)], [TABLE])))[0] == "table_rows"


def test_text_with_no_headings_or_tables_is_cut_by_size():
    assert choose(doc(page([line("plain words", 0)]))) == ("recursive", "no headings or tables to follow")


def test_running_text_is_searched_in_small_pieces_and_read_in_big_ones():
    prose = "the valve shall be suitable for continuous duty in clean water service at the stated working pressure and temperature"
    assert choose(doc(page([line("Scope of supply", 0, bold=True), line(prose, 1)])))[0] == "parent_child"


def test_headed_text_with_few_tables_is_chunked_by_section():
    assert choose(doc(page([line("Technical data", 0, bold=True), line("PN 16", 1)])))[0] == "sections"


def test_the_setting_decides_and_the_default_is_the_original_strategy():
    clauses = doc(page([line(f"{i}. Clause number {i}", i) for i in range(1, 10)]))
    assert chunker_for(clauses).name == "table_rows"
    assert chunker_for(clauses, "auto").name == "structure"
    assert chunker_for(clauses, "recursive").name == "recursive"
    with pytest.raises(ValueError, match="Unknown chunking strategy"):
        chunker_for(clauses, "magic")
