from app.services.chunker import (
    caption_for,
    chunk_document,
    chunk_page,
    join_rows,
    pack,
    page_headings,
)
from app.services.layout import build_sections
from app.services.pdf_reader import (
    Line,
    PageRecord,
    RawTable,
    ReadDocument,
    lines_from_text,
)


def line(text, block, y0=0.0, size=6.9, bold=False):
    return Line(text=text, x0=0, y0=y0, x1=50, y1=y0 + 9, size=size, bold=bold, block=block)


def page(lines) -> PageRecord:
    return PageRecord(pdf_page=2, text="", n_chars=0, n_images=0, needs_ocr=False, lines=lines)


def test_empty_page_gives_no_sections_and_no_chunks():
    assert build_sections([]) == []
    assert chunk_page(page([]), "ksb", "x.pdf") == []


def test_fallback_keeps_a_label_and_its_value_in_one_chunk():
    lines = [line("Max. pressure [bar]", 0), line("16 (DN 40 - 600)", 0), line("Other text", 1)]
    chunks = chunk_page(page(lines), "ksb", "x.pdf")
    assert "Max. pressure [bar]\n16 (DN 40 - 600)" in chunks[0].text
    assert chunks[0].section is None


def test_pack_never_cuts_inside_a_block():
    pieces = ["a" * 600, "b" * 600]
    assert pack(pieces, max_chars=1000) == ["a" * 600, "b" * 600]


def test_page_headings_are_the_bold_lines_top_to_bottom_without_repeats():
    lines = [
        line("GATE, GLOBE AND CHECK VALVES", 0, y0=10, bold=True),
        line("Some body text that is long enough", 1, y0=20),
        line("Cast Steel Swing Check Valves", 2, y0=30, bold=True),
        line("GATE, GLOBE AND CHECK VALVES", 3, y0=40, bold=True),
        line("12345", 4, y0=50, bold=True),
    ]
    assert page_headings(lines) == ["GATE, GLOBE AND CHECK VALVES", "Cast Steel Swing Check Valves"]


def test_every_chunk_of_a_page_carries_the_page_headings():
    lines = [line("DOUBLE OFFSET BUTTERFLY VALVE", 0, y0=10, bold=True), line("Max. pressure [bar]", 1, y0=30), line("16", 1, y0=40)]
    chunks = chunk_page(page(lines), "duncan", "x.pdf")
    assert chunks and all(c.page_headings == ["DOUBLE OFFSET BUTTERFLY VALVE"] for c in chunks)


def test_a_colon_value_is_joined_to_its_label_even_when_stored_as_separate_blocks():
    label = Line(text="Face to Face", x0=63, y0=335, x1=115, y1=346, size=10.6, bold=False, block=9)
    value = Line(text=": API 609 Category-A", x0=154, y0=335, x1=300, y1=346, size=10.6, bold=False, block=7)
    assert [l.text for l in join_rows([value, label])] == ["Face to Face : API 609 Category-A"]


def test_side_by_side_columns_are_not_joined():
    left = Line(text="Upto PN10", x0=213, y0=157, x1=260, y1=166, size=10, bold=False, block=1)
    right = Line(text="Wafer / Lugged", x0=300, y0=157, x1=370, y1=166, size=10, bold=False, block=2)
    assert [l.text for l in join_rows([left, right])] == ["Upto PN10", "Wafer / Lugged"]


def test_a_page_with_no_colon_values_keeps_the_files_own_order():
    lower = line("Second in the file", block=1, y0=300)
    upper = line("First on the page", block=2, y0=100)
    assert join_rows([lower, upper]) == [lower, upper]


def test_a_table_takes_the_short_line_above_it_as_its_caption():
    table = RawTable(bbox=(277, 638, 578, 678), rows=[])
    caption = Line(text="Pressure Rating", x0=276, y0=622, x1=351, y1=634, size=11.7, bold=True, block=1)
    far = Line(text="Unrelated heading", x0=276, y0=300, x1=351, y1=312, size=11.7, bold=True, block=2)
    assert caption_for(table, [far, caption]) == "Pressure Rating" and caption_for(table, [far]) is None


def read_page(number: int, text: str) -> PageRecord:
    return PageRecord(pdf_page=number, text=text, n_chars=len(text), n_images=1, needs_ocr=True, ocr=True, lines=lines_from_text(text))


def test_table_rows_read_from_a_picture_become_table_chunks_under_their_heading():
    text = "# Pressure Rating\n\nInch: 2 to 12; DN: 50-300; BARG: 12\nInch: 2 to 40; DN: 50-1000; BARG: 6\n\nValves up to size 12 have lever handles."
    chunks = chunk_page(read_page(7, text), "delval", "d.pdf")
    tables = [c for c in chunks if c.kind == "table"]
    assert [c.text for c in tables] == ["Pressure Rating\nInch: 2 to 12; DN: 50-300; BARG: 12", "Pressure Rating\nInch: 2 to 40; DN: 50-1000; BARG: 6"]
    assert all(c.ocr for c in chunks)
    assert not any("BARG" in c.text for c in chunks if c.kind != "table")


def test_every_chunk_of_a_document_carries_the_headings_of_its_first_page():
    cover = read_page(1, "# Resilient Seated Butterfly Valves\nWafer, Lug Body")
    inner = read_page(2, "Size Range: 2 to 40 inch")
    doc = ReadDocument(path="x/delval/d.pdf", sha256="s", n_pages=2, pages=[cover, inner])
    assert all(c.document_headings == ["Resilient Seated Butterfly Valves"] for c in chunk_document(doc))