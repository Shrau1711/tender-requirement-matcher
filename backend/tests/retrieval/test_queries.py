from app.extraction.atomize import AtomicRequirement
from app.retrieval.queries import (
    load_unit_views,
    product_words,
    queries_for,
    unit_views,
)
from app.tender.items import Item

VIEWS = load_unit_views()


def req(attribute: str, kind: str, values: list[str], unit: str | None) -> AtomicRequirement:
    return AtomicRequirement(
        item=Item(title="Valves", quantity=1), pdf_page=1, source_name="n", source_value="v",
        attribute=attribute, kind=kind, operator="equals", values=values, unit=unit, evidence="product",
    )


def test_pressure_gets_the_other_ways_brochures_write_it():
    found = queries_for(req("nominal_pressure", "number", ["1.6"], "MPa"), VIEWS)
    assert "nominal pressure 1.6 MPa" in found and "16 bar" in found and "PN 16" in found


def test_pn_is_only_for_nominal_pressure():
    found = queries_for(req("test_pressure", "number", ["1.6"], "MPa"), VIEWS)
    assert "16 bar" in found and "PN 16" not in found


def test_size_gets_dn():
    assert "DN 125" in queries_for(req("nominal_size", "number", ["125"], "mm"), VIEWS)


def test_text_requirement_is_just_its_words():
    assert queries_for(req("valve_end_connection", "choice", ["Flangeless Wafer Valve"], None), VIEWS) == [
        "valve end connection Flangeless Wafer Valve",
        "Valves valve end connection Flangeless Wafer Valve",
    ]


def test_each_alternative_value_is_searched():
    found = queries_for(req("class", "choice", ["125", "150"], None), VIEWS)
    assert found == ["class 125", "class 150", "Valves class 125", "Valves class 150"]


def test_unknown_unit_does_not_crash():
    assert queries_for(req("x", "number", ["5"], "furlongs per fortnight squared"), VIEWS) == [
        "x 5 furlongs per fortnight squared", "Valves x 5 furlongs per fortnight squared"
    ]


def test_a_standard_is_searched_by_its_identifier_alone():
    assert queries_for(req("governing_specification", "standard", ["IS 13095"], None), VIEWS) == ["IS 13095"]


def test_an_abbreviation_is_also_searched_written_out():
    found = queries_for(req("end_connection", "choice", ["BW"], None), VIEWS)
    assert found[0] == "end connection BW" and "end connection butt weld" in found


def test_the_products_name_is_the_title_before_its_first_number():
    assert product_words("1600677219 VALVE GATE 250 1500# BW A217 WC") == "VALVE GATE"
    assert product_words("Butterfly Valves (V2) As Per IS 13095") == "Butterfly Valves"
    assert product_words("12345") == ""


def test_every_query_is_also_asked_with_the_product_named():
    found = queries_for(req("body_material", "choice", ["A217 WC9"], None), VIEWS)
    assert found == ["body material A217 WC9", "Valves body material A217 WC9"]


def test_a_size_in_mm_is_also_searched_as_nominal_pipe_size():
    found = queries_for(req("size", "number", ["250"], "mm"), VIEWS)
    assert "NPS 10" in found and "10 inch" in found


def test_a_flow_is_also_searched_as_flow_rate_and_in_cubic_metres_per_hour():
    queries = queries_for(req("discharge", "number", ["38"], "LPS"), load_unit_views())
    assert "flow rate 38 LPS" in queries
    assert "136.8 m³/h" in queries


def test_a_head_in_metres_is_not_also_searched_as_millimetres_but_a_size_is():
    views = load_unit_views()
    assert "160000 mm" not in queries_for(req("head", "number", ["160"], "mtrs"), views)
    assert "250 mm" in queries_for(req("face_to_face_dimension", "number", ["250"], "mm"), views)


def test_what_follows_a_linking_word_in_a_title_is_not_the_product():
    assert product_words("Type-2 pump with motor along with spare mechanical seals") == "pump"


def test_a_line_break_that_lost_the_space_is_read_as_a_space():
    assert product_words("Type-1 pumpwith motor along with spare mechanical seals") == "pump"


def test_a_number_with_no_unit_has_no_other_spellings_and_does_not_crash():
    assert unit_views("pressure", "85", None, VIEWS) == []
    assert unit_views("pressure", "85", "", VIEWS) == []


def test_a_unit_pint_cannot_classify_gives_no_other_spellings_instead_of_crashing():
    assert unit_views("noise level", "85", "dB(A)", VIEWS) == []  # a decibel level is logarithmic
    assert unit_views("size", "85", '"', VIEWS) == []  # a lone quote mark is not a unit
