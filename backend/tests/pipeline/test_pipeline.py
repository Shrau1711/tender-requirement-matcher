from app.extraction.atomize import AtomicRequirement
from app.pipeline.pipeline import only_items
from app.tender.items import Item


def atom(title):
    return AtomicRequirement(item=Item(title=title), pdf_page=1, source_name="n", source_value="v", attribute="a", kind="text",
                             operator="equals", values=["v"], unit=None, evidence="product")


def test_only_the_given_items_are_kept_and_the_others_are_named_in_a_note():
    atoms, notes = only_items([atom("Gate valve"), atom("Booster pump"), atom("Gate valve")], ["read 2 files"], ["Gate valve"])
    assert [a.item.title for a in atoms] == ["Gate valve", "Gate valve"]
    assert notes == ["read 2 files", "This tender also has items of other product categories, matched in runs of their own: Booster pump."]
