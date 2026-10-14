from builders import ev, req

from app.services.by_product import best_products
from app.services.gold import blank_gold, compare
from app.services.match import ItemSummary, Summary, match_all, overall, summarize_items
from app.services.measure import load_aliases
from app.services.tender import Item, distinct_items

ALIASES = load_aliases()
FIRST, SECOND = Item(title="Valve 250", quantity=10), Item(title="Valve 80", quantity=4)
SIZE = req("nominal_size", "number", ["125"], "mm").model_copy(update={"item": FIRST})
HANDLE = req("handle_type", "text", ["Lever"]).model_copy(update={"item": SECOND})
SIZE_EVIDENCE = ev("40mm to 500mm", "range", [40, 500], "mm", name="A")
HANDLE_EVIDENCE = ev("Lever", items=["Lever"], name="B")


def summary(compatibility: float | None, counted: int = 2) -> Summary:
    return Summary(manufacturer="m", compatibility=compatibility, coverage=compatibility, counted=counted)


def test_items_are_listed_once_in_order():
    assert distinct_items([SECOND, FIRST, SECOND]) == [SECOND, FIRST]


def test_the_tender_score_is_the_average_of_its_items():
    per_item = [ItemSummary(item=FIRST, summary=summary(100)), ItemSummary(item=SECOND, summary=summary(0, 3))]
    total = overall("m", per_item)
    assert (total.compatibility, total.counted) == (50, 5)


def test_an_item_that_could_not_be_assessed_does_not_count_in_the_average():
    per_item = [ItemSummary(item=FIRST, summary=summary(80)), ItemSummary(item=SECOND, summary=summary(None, 0))]
    assert overall("m", per_item).compatibility == 80
    assert overall("m", [per_item[1]]).compatibility is None


def test_each_item_gets_its_own_summary():
    outcomes = match_all([SIZE, HANDLE], ["m"], {(0, "m"): [SIZE_EVIDENCE]}, ALIASES, {"m"})
    assert [(s.item.title, s.summary.compatibility) for s in summarize_items("m", outcomes)] == [("Valve 250", 100), ("Valve 80", 0)]


def test_different_items_can_be_met_by_different_products():
    table = {(0, "m"): [SIZE_EVIDENCE], (1, "m"): [HANDLE_EVIDENCE]}
    chosen = best_products([SIZE, HANDLE], "m", table, ALIASES, True)
    assert [(item.title, product, outs[0].score) for item, product, outs in chosen] == [("Valve 250", "A", 100), ("Valve 80", "B", 100)]


def test_label_sheets_name_the_item_only_when_there_are_several():
    assert list(blank_gold([SIZE], ["m"])) == ["nominal_size"]
    assert list(blank_gold([SIZE, HANDLE], ["m"])) == ["Valve 250 | nominal_size", "Valve 80 | handle_type"]


def test_labels_are_matched_to_the_right_item():
    gold = blank_gold([SIZE, HANDLE], ["m"])
    gold["Valve 250 | nominal_size"]["m"].status = "fully matched"
    outcomes = match_all([SIZE, HANDLE], ["m"], {(0, "m"): [SIZE_EVIDENCE]}, ALIASES, {"m"})
    [row] = compare(outcomes, gold)
    assert (row.attribute, row.agrees) == ("Valve 250 | nominal_size", True)
