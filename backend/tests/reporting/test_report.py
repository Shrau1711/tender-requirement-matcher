from builders import BIG, SIZE, ev, req, run

from app.reporting.report_markdown import to_markdown
from app.vocabulary.roles import NEEDS_DOCUMENT, NOT_COVERED, key_of, set_aside

ROLES = {"information": ["tag_number"]}
HANDLE = req("handle_type", "text", ["Lever"])
TAG = req("tag_number", "text", ["V-101"])
PAPER = req("test_report", "yes_no", ["Yes"]).model_copy(update={"evidence": "paperwork"})
SEAL = req("seal_material", "text", ["EPDM"])
LEVER = ev("Lever", items=["Lever"], name="Wafer")


def test_requirements_no_catalogue_can_judge_are_set_aside_with_a_reason():
    table = {(0, "a"): [BIG]}
    why = set_aside([SIZE, TAG, PAPER, SEAL], ["a"], table, ROLES)
    assert key_of(SIZE) not in why
    assert why[key_of(PAPER)] == NEEDS_DOCUMENT and why[key_of(SEAL)] == NOT_COVERED and key_of(TAG) in why


def test_set_aside_requirements_do_not_pull_the_percentage_down():
    report = run([SIZE, TAG, PAPER, SEAL], {(0, "a"): [BIG]})
    maker = report.makers[0]
    assert maker.compatibility == 100 and maker.counts["fully matched"] == 1 and maker.counts["unsupported requirement"] == 3
    assert len(report.unsupported) == 3


def test_a_requirement_only_another_maker_covers_still_counts_against_this_one():
    report = run([SIZE, HANDLE], {(0, "a"): [BIG], (1, "a"): [LEVER], (0, "b"): [BIG]}, makers=("a", "b"))
    by_name = {m.manufacturer: m for m in report.makers}
    assert (by_name["a"].compatibility, by_name["b"].compatibility) == (100, 50)
    assert [m.manufacturer for m in report.makers] == ["a", "b"] and by_name["b"].rank == 2


def test_a_maker_with_no_product_of_the_type_scores_zero_not_stray_credit():
    stray = ev("40mm to 500mm", "range", [40, 500], "mm", product="unclear")
    report = run([SIZE], {(0, "a"): [BIG], (0, "b"): [stray]}, makers=("a", "b"))
    b = next(m for m in report.makers if m.manufacturer == "b")
    assert b.compatibility == 0 and "no product of this type" in b.items[0].note.lower()


def test_an_item_nobody_can_be_judged_for_is_not_scored_for_anyone():
    report = run([SIZE], {}, makers=("a", "b"))
    assert report.unscored_items == ["Valves"]
    assert all(m.compatibility is None and m.rank is None for m in report.makers)
    assert any("not scored" in n for n in report.notes)


def test_an_unreadable_maker_is_not_assessed_and_ranked_last():
    report = run([SIZE], {(0, "a"): [BIG]}, makers=("a", "b"), readable={"a"})
    assert [(m.manufacturer, m.rank, m.compatibility) for m in report.makers] == [("a", 1, 100), ("b", None, None)]


def test_every_row_carries_its_evidence_and_the_markdown_shows_it():
    report = run([SIZE], {(0, "a"): [BIG]})
    row = report.makers[0].items[0].rows[0]
    assert (row.document, row.page, row.quote) == ("f.pdf", 2, "40mm to 500mm")
    text = to_markdown(report)
    assert "f.pdf p2" in text and "How the compatibility is calculated" in text and "100.0%" in text


def test_a_product_that_fails_the_requirement_naming_its_type_scores_zero_for_the_item():
    kind = req("pump_type", "text", ["vertical multistage"])
    table = {
        (0, "a"): [ev("pump type ETNE", items=["ETNE"], name="Etanorm")], (1, "a"): [BIG],
        (0, "b"): [ev("vertical multistage", items=["vertical multistage"], name="MV")], (1, "b"): [BIG],
    }
    report = run([kind, SIZE], table, makers=("a", "b"))
    a = next(m for m in report.makers if m.manufacturer == "a")
    item = a.items[0]
    assert a.compatibility == 0 and "not the type the tender asks for" in item.note and "Wafer" in item.note
    assert all(row.score == 0 for row in item.rows)
    assert report.makers[0].manufacturer == "b" and report.makers[0].compatibility == 100
