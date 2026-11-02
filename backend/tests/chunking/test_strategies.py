import itertools

from builders import chunk_page

from app.chunking.base import maker
from app.chunking.strategies import STRATEGIES, strategy
from app.chunking.strategies.parent_child import CHILD_CHARS, ParentChild, children
from app.chunking.strategies.recursive import Recursive, overlap, split
from app.chunking.strategies.sections import Sections
from app.chunking.strategies.structure import Structure, clause_of, flow_chunks
from app.reading.pdf_reader import Line, PageRecord, RawTable


def line(text, block, y0=0.0, x0=0.0, size=10.0, bold=False):
    return Line(text=text, x0=x0, y0=y0, x1=x0 + 200, y1=y0 + 9, size=size, bold=bold, block=block)


def page(lines, number=2, text="", tables=(), boxes=(), links=()) -> PageRecord:
    return PageRecord(pdf_page=number, text=text, n_chars=len(text), n_images=0, needs_ocr=False, lines=lines, tables=list(tables), boxes=list(boxes), links=list(links))


def box_around(l):
    return (l.x0 - 4, l.y0 - 4, l.x1 + 4, l.y1 + 4)


def test_every_strategy_is_registered_by_its_name():
    assert set(STRATEGIES) == {"table_rows", "recursive", "sections", "parent_child", "structure"}
    assert all(strategy(name).name == name for name in STRATEGIES)


def test_recursive_cuts_at_paragraphs_before_lines_and_keeps_pieces_small():
    text = "First paragraph about pressure.\n\nSecond paragraph about size.\n\nThird about material."
    assert split(text, size=40) == ["First paragraph about pressure.", "Second paragraph about size.", "Third about material."]
    assert all(len(p) <= 40 for p in split("word " * 100, size=40))


def test_recursive_repeats_the_end_of_a_piece_at_the_start_of_the_next():
    assert overlap(["the rated pressure is 16 bar", "at 20 degrees"], chars=10) == ["the rated pressure is 16 bar", "is 16 bar at 20 degrees"]


def test_recursive_chunks_the_page_text():
    chunks = chunk_page(page([], text="Size DN 50 to 600\n\nPressure PN 16"), "ksb", "k.pdf", Recursive())
    assert [c.text for c in chunks] == ["Size DN 50 to 600\n\nPressure PN 16"] and chunks[0].kind == "text"


def test_sections_keep_a_heading_with_its_lines_and_a_table_whole():
    lines = [line("Technical Data", 0, y0=10, bold=True), line("Max. pressure 16 bar", 1, y0=30), line("Pressure Rating", 2, y0=200, bold=True)]
    table = RawTable(bbox=(0, 215, 300, 300), rows=[["DN", "PN", "Weight"], ["50", "16", "4"], ["80", "16", "6"]])
    chunks = chunk_page(page(lines, tables=[table]), "ksb", "k.pdf", Sections())
    tables = [c for c in chunks if c.kind == "table"]
    assert len(tables) == 1 and tables[0].text.startswith("Pressure Rating\n") and "DN: 50" in tables[0].text and "DN: 80" in tables[0].text
    assert any(c.kind == "section" and c.section == "Technical Data" and "16 bar" in c.text for c in chunks)


def test_children_are_short_and_overlap_by_one_line():
    text = "\n".join(f"line {i} " + "x" * 80 for i in range(6))
    pieces = children(text, size=200)
    assert len(pieces) > 1 and all(len(p) <= 200 for p in pieces)
    assert all(a.splitlines()[-1] == b.splitlines()[0] for a, b in itertools.pairwise(pieces))


def test_a_long_parent_is_searched_by_its_children_and_read_whole():
    body = [line(f"Material of part {i}: stainless steel 316 with a long description", 0, y0=10 * i) for i in range(12)]
    chunks = chunk_page(page(body), "ksb", "k.pdf", ParentChild())
    assert len(chunks) > 1 and all(len(c.text) <= CHILD_CHARS for c in chunks)
    assert {c.parent for c in chunks} == {chunks[0].for_model()} and len(chunks[0].for_model()) > CHILD_CHARS


def test_a_short_chunk_has_no_parent_and_is_read_as_it_is():
    chunks = chunk_page(page([line("Pressure PN 16", 0)]), "ksb", "k.pdf", ParentChild())
    assert [(c.text, c.parent, c.for_model()) for c in chunks] == [("Pressure PN 16", None, "Pressure PN 16")]


def test_numbered_clauses_are_found_and_a_bare_number_with_a_unit_is_not():
    assert clause_of("3.2 Casing") == ("3.2", 2) and clause_of("3. Pumps") == ("3", 1) and clause_of("2) Valves") == ("2", 1)
    assert clause_of("16 bar") is None and clause_of("3.2") is None


def test_each_clause_starts_with_the_path_above_it_and_a_new_top_clause_closes_the_old_ones():
    lines = [line(t, i) for i, t in enumerate(["1. Pumps", "Flow 20 m3/h", "1.1 Casing", "Material SS 316", "2. Valves", "Size DN 50"])]
    chunks = Structure().chunk([page(lines)], maker("ksb", "k.pdf"))
    assert [(c.section, c.text) for c in chunks] == [
        ("1. Pumps", "1. Pumps\nFlow 20 m3/h"),
        ("1. Pumps > 1.1 Casing", "1. Pumps\n1.1 Casing\nMaterial SS 316"),
        ("2. Valves", "2. Valves\nSize DN 50"),
    ]


def test_a_clause_continued_on_the_next_page_keeps_its_whole_path():
    first = page([line("1. Pumps", 0), line("1.1 Casing", 1), line("Material SS 316", 2)], number=1)
    second = page([line("Impeller SS 304", 0)], number=2)
    last = Structure().chunk([first, second], maker("ksb", "k.pdf"))[-1]
    assert (last.pdf_page, last.text) == (2, "1. Pumps > 1.1 Casing\nImpeller SS 304")


STEPS = ["Receive order", "Check stock", "Pick valve", "Test valve", "Pack", "Ship"]


def boxed_page(links):
    lines = [line(s, 0, y0=100 * i, x0=50 * (i % 2)) for i, s in enumerate(STEPS)]  # one text block, as PDF readers often give
    return page([*lines, line("Order flow", 1, y0=900)], boxes=map(box_around, lines), links=links)


def test_a_flowchart_box_is_a_chunk_with_the_boxes_joined_to_it():
    chunks = Structure().chunk([boxed_page([(i, i + 1) for i in range(5)])], maker("ksb", "k.pdf"))
    assert [c.text for c in chunks][:3] == ["Order flow", "Receive order\n-> Check stock", "Receive order ->\nCheck stock\n-> Pick valve"]
    assert flow_chunks(["Fluid?", "Slurry", "Knife gate"], [(0, 1), (1, 2)])[1] == "Fluid? ->\nSlurry\n-> Knife gate"


def test_boxes_with_no_lines_between_them_are_not_a_flowchart():
    chunks = Structure().chunk([boxed_page([])], maker("ksb", "k.pdf"))  # an ordering-code grid looks like this
    assert len(chunks) == 1 and chunks[0].text.startswith("Receive order\nCheck stock")


def test_short_texts_without_drawn_boxes_are_not_a_flowchart():
    lines = [line(s, i, y0=100 * i) for i, s in enumerate(["Size", "DN 50", "Pressure", "PN 16", "Body", "Steel"])]
    chunks = Structure().chunk([page(lines)], maker("ksb", "k.pdf"))
    assert len(chunks) == 1 and chunks[0].text == "Size\nDN 50\nPressure\nPN 16\nBody\nSteel"
