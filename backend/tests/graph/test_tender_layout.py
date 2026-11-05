"""The tender's layout as the web page shows it: items, shared rows, requirements, standards and each item's family."""
from app.categories.config import CATEGORIES_DIR
from app.extraction.atomize import AtomicRequirement
from app.graph.layout import layout
from app.llm.gemini import cache_settings
from app.llm.llm_factory import SavedOnly
from app.tender.items import Item


def atom(item, name, value, attribute, page=1, values=None):
    return AtomicRequirement(item=Item(title=item), file="bid.pdf", pdf_page=page, source_name=name, source_value=value,
                             attribute=attribute, kind="text", operator="equals", values=values or [value], unit=None, evidence="product")


ATOMS = [
    atom("BUTTERFLY VALVE DN 200", "Size", "DN 200", "nominal_size"),
    atom("BUTTERFLY VALVE DN 200", "Standard", "IS 13095", "design_standard", page=2),
    atom("VALVE MOTORISED 300", "Type", "Gate", "valve_type", values=["gate"]),
    atom("VALVE MOTORISED 300", "Standard", "IS 13095", "design_standard", page=2),  # printed once for both items
]


def test_items_rows_requirements_and_shared_rows():
    lay = layout("T-1", ATOMS, CATEGORIES_DIR)
    assert [i.title for i in lay.items] == ["BUTTERFLY VALVE DN 200", "VALVE MOTORISED 300"]
    assert (lay.requirements, lay.shared_rows) == (4, 1)
    standard = next(r for r in lay.items[0].rows if r.name == "Standard")
    assert (standard.value, standard.page, standard.shared_with) == ("IS 13095", 2, ["VALVE MOTORISED 300"])
    assert standard.requirements == ["design_standard equals IS 13095"]


def test_each_item_gets_its_family_and_the_names_its_reading_does_not_use():
    butterfly, motorised = layout("T-1", ATOMS, CATEGORIES_DIR).items
    assert (butterfly.category, butterfly.family, butterfly.family_from) == ("valves", "butterfly valve", "title")
    assert (motorised.family, motorised.family_from) == ("gate valve", "type value")
    assert "nominal_size" not in butterfly.not_named and "face_to_face_dimension" in butterfly.not_named
    assert "bypass_arrangement" in motorised.not_named and "face_to_face_dimension" not in motorised.not_named


def test_cited_standards_come_with_their_other_names():
    lay = layout("T-1", ATOMS, CATEGORIES_DIR)
    assert [s.name for s in lay.standards] == ["IS13095"] and "IS 13095" in lay.standards[0].also_written


def test_the_saved_answers_stand_in_uses_the_same_cache_key_as_gemini():
    stand_in = SavedOnly()
    assert (stand_in.model, stand_in.settings) == cache_settings() == ("gemini-3.8-flash", "thinking=LOW")
