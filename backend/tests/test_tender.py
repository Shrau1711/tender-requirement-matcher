from app.services.pdf_reader import Line, PageRecord, RawTable, ReadDocument
from app.services.tender import name_value_rows, parse_item, read_requirements


def heading(text: str, y: float) -> Line:
    return Line(text=text, x0=0, y0=y, x1=300, y1=y + 10, size=12, bold=True, block=0)


def table(y: float, rows: list[list[str | None]]) -> RawTable:
    return RawTable(bbox=(0, y, 500, y + 100), rows=rows)


def doc(lines: list[Line], tables: list[RawTable]) -> ReadDocument:
    page = PageRecord(pdf_page=1, text="x", n_chars=1, n_images=0, needs_ocr=False, lines=lines, tables=tables)
    return ReadDocument(path="t.pdf", sha256="0", n_pages=1, pages=[page])


SPEC = [
    ["Specification", "Specification Name", "Bid Requirement (Allowed Values)"],
    [None, None, None],
    ["TYPE / SIZE", "Nominal Size (DN) (mm)", "125"],
    [None, "Nominal Pressure (PN)\n(MPa)", "1.6"],
]


def test_parse_item_reads_title_and_quantity():
    item = parse_item("Additional Specification Parameters - Butterfly Valves (V2) As Per IS 13095 ( 50 pieces )")
    assert (item.title, item.quantity) == ("Butterfly Valves (V2) As Per IS 13095", 50)


def test_parse_item_ignores_ordinary_lines():
    assert parse_item("Payment shall be made within 10 days") is None


def test_rows_skip_header_and_spacer_and_carry_group():
    assert name_value_rows(table(0, SPEC)) == [
        ("TYPE / SIZE", "Nominal Size (DN) (mm)", "125"),
        ("TYPE / SIZE", "Nominal Pressure (PN) (MPa)", "1.6"),
    ]


def test_only_tables_under_an_item_heading_are_requirements():
    bid_details = table(0, [["Bid End Date", "07-10-2026"]])
    spec = table(200, SPEC)
    found = read_requirements(doc([heading("Valves ( 5 pieces )", 150)], [bid_details, spec]))
    assert [r.name for r in found] == ["Nominal Size (DN) (mm)", "Nominal Pressure (PN) (MPa)"]
    assert found[0].item.quantity == 5