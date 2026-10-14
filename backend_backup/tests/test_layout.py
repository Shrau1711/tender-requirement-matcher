from app.services.layout import build_sections
from app.services.pdf_reader import Line


def line(text, x0, y0, size=6.9, bold=False):
    return Line(text=text, x0=x0, y0=y0, x1=x0 + 50, y1=y0 + 9, size=size, bold=bold, block=0)


def two_column_page() -> list[Line]:
    return [
        line("BALL VALVES", 27, 100, size=12, bold=True),
        line("Size Range :", 35, 120, bold=True),
        line("6mm to 750mm", 35, 129),
        line("BUTTERFLY VALVES", 262, 100, size=12, bold=True),
        line("Size Range :", 263, 120, bold=True),
        line("40mm to 500mm", 263, 129),
        line("Pressure Rating :", 263, 140, bold=True),
        line("PN 1.6 I", 263, 149),
        line("PN 2.5", 263, 158),
    ]


def test_each_column_gets_its_own_values():
    sections = {s.heading: s for s in build_sections(two_column_page())}
    assert sections["BALL VALVES"].fields[0].value == "6mm to 750mm"
    assert sections["BUTTERFLY VALVES"].fields[0].value == "40mm to 500mm"


def test_wrapped_value_is_joined_and_label_loses_colon():
    butterfly = {s.heading: s for s in build_sections(two_column_page())}["BUTTERFLY VALVES"]
    assert butterfly.fields[1].label == "Pressure Rating"
    assert butterfly.fields[1].value == "PN 1.6 I PN 2.5"