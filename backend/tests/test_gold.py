from builders import ev, req

from app.services.gold import Label, blank_gold, compare, load_gold, save_gold, share
from app.services.match import match_requirement
from app.services.measure import load_aliases

ALIASES = load_aliases()
SIZE = req("nominal_size", "number", ["125"], "mm")


def test_a_blank_sheet_has_every_manufacturer_for_every_product_requirement_and_no_paperwork():
    paper = req("test_report", "yes_no", ["Yes"]).model_copy(update={"evidence": "paperwork"})
    sheet = blank_gold([SIZE, paper], ["a", "b"])
    assert list(sheet) == ["nominal_size"] and set(sheet["nominal_size"]) == {"a", "b"}
    assert all(label.status is None for label in sheet["nominal_size"].values())


def test_a_sheet_survives_saving_and_loading(tmp_path):
    sheet = blank_gold([SIZE], ["a"])
    sheet["nominal_size"]["a"] = Label(status="fully matched", page=5, note="range covers it")
    save_gold(sheet, tmp_path / "t.json")
    assert load_gold(tmp_path / "t.json")["nominal_size"]["a"].page == 5


def test_only_labelled_rows_of_readable_manufacturers_are_compared():
    outcomes = [
        match_requirement(SIZE, "a", [ev("50 NB to 350 NB", "range", [50, 350], "NB")], ALIASES),
        match_requirement(SIZE, "b", [], ALIASES),
        match_requirement(SIZE, "c", [], ALIASES, readable=False),
    ]
    sheet = blank_gold([SIZE], ["a", "b", "c"])
    sheet["nominal_size"]["a"] = Label(status="partially matched", page=5)
    sheet["nominal_size"]["c"] = Label(status="fully matched")
    rows = compare(outcomes, sheet)
    assert [(r.manufacturer, r.agrees, r.our_page) for r in rows] == [("a", False, 2)]


def test_share_handles_an_empty_total():
    assert share(1, 4) == "1/4 (25%)" and share(0, 0) == "none"

def test_a_label_may_list_several_pages_and_our_page_agrees_if_it_is_any_of_them():
    sheet = blank_gold([SIZE], ["a"])
    sheet["nominal_size"]["a"] = Label(status="fully matched", page=[2, 5])
    outcome = match_requirement(SIZE, "a", [ev("50 NB to 350 NB", "range", [50, 350], "NB")], ALIASES)
    (row,) = compare([outcome], sheet)
    assert row.gold_pages == [2, 5] and row.page_agrees and Label(page=4).pages == [4] and Label().pages == []