import json

import pytest

from app.services.atomize import atomize, atomize_tender, uncovered_rows
from app.services.tender import Item, Requirement

ITEM = Item(title="Valves", quantity=5)


def row(name: str, value: str) -> Requirement:
    return Requirement(item=ITEM, group=None, name=name, value=value, pdf_page=5)


def atom(row_no: int, attribute: str) -> dict:
    return {"row": row_no, "attribute": attribute, "kind": "text", "operator": "equals",
            "values": ["x"], "unit": None, "evidence": "product"}


def reply(*atoms: dict) -> str:
    return json.dumps({"requirements": list(atoms)})


def test_one_row_can_become_two_requirements(fake_llm):
    rows = [row("Face to face", "Wafer Short Class 125/150")]
    found = atomize(fake_llm([reply(atom(0, "face_to_face"), atom(0, "flange_class"))]), rows, [])
    assert [a.attribute for a in found] == ["face_to_face", "flange_class"]
    assert found[0].source_value == "Wafer Short Class 125/150"


def test_rows_that_do_not_exist_are_rejected(fake_llm):
    with pytest.raises(ValueError, match="do not exist"):
        atomize(fake_llm([reply(atom(3, "size"))]), [row("Size", "125")], [])


def test_silently_dropped_rows_are_reported(fake_llm):
    rows = [row("Size", "125"), row("Pressure", "1.6")]
    found = atomize(fake_llm([reply(atom(0, "size"))]), rows, [])
    assert [r.name for r in uncovered_rows(rows, found)] == ["Pressure"]


def test_each_item_is_a_separate_call(fake_llm):
    other = Requirement(item=Item(title="Valves", quantity=9), group=None, name="Size", value="80", pdf_page=6)
    llm = fake_llm([reply(atom(0, "size")), reply(atom(0, "size"))])
    found = atomize_tender(llm, [row("Size", "125"), other])
    assert len(llm.prompts) == 2 and [a.item.quantity for a in found] == [5, 9]


def test_later_items_are_told_the_names_already_used(fake_llm):
    other = Requirement(item=Item(title="Valves", quantity=9), group=None, name="Size", value="80", pdf_page=6)
    llm = fake_llm([reply(atom(0, "nominal_size")), reply(atom(0, "nominal_size"))])
    atomize_tender(llm, [row("Size", "125"), other])
    assert json.loads(llm.prompts[0])["known_attributes"] == []
    assert json.loads(llm.prompts[1])["known_attributes"] == ["nominal_size"]


def test_two_files_that_state_an_item_differently_are_reported():
    from app.services.atomize import AtomicRequirement, contradictions

    def atom(file: str, value: str, name: str = "Pressure") -> AtomicRequirement:
        return AtomicRequirement(item=ITEM, file=file, pdf_page=1, source_name=name, source_value=value, attribute="pressure",
                                 kind="number", operator="equals", values=[value], unit=None, evidence="product")

    [note] = contradictions([atom("a.pdf", "0.4"), atom("b.pdf", "1.5")])
    assert "pressure" in note and "a.pdf" in note and "b.pdf" in note
    assert contradictions([atom("a.pdf", "0.4"), atom("b.pdf", "0.4")]) == []
    assert contradictions([atom("a.pdf", "15"), atom("a.pdf", "20")]) == []
