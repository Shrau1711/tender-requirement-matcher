from app.services.atomize import AtomicRequirement
from app.services.queries import load_unit_views, queries_for
from app.services.tender import Item

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
        "valve end connection Flangeless Wafer Valve"
    ]


def test_each_alternative_value_is_searched():
    found = queries_for(req("class", "choice", ["125", "150"], None), VIEWS)
    assert found == ["class 125", "class 150"]


def test_unknown_unit_does_not_crash():
    assert queries_for(req("x", "number", ["5"], "furlongs per fortnight squared"), VIEWS) == ["x 5 furlongs per fortnight squared"]


def test_a_standard_is_searched_by_its_identifier_alone():
    assert queries_for(req("governing_specification", "standard", ["IS 13095"], None), VIEWS) == ["IS 13095"]