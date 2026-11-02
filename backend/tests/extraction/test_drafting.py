from builders import req

from app.extraction.drafting import (
    Answer,
    Draft,
    check,
    document_prompt,
    label_of,
    merge,
    questions,
    to_gold,
)

SIZE = req("nominal_size", "number", ["125"], "mm")
PAGES = {3: "Nominal size: 40 mm to 500 mm", 4: "other"}


def test_two_items_asking_the_same_thing_are_one_question():
    other = SIZE.model_copy(update={"item": SIZE.item.model_copy(update={"title": "Valves 80"})})
    assert len(questions([SIZE, other])) == 1


def test_the_prompt_marks_pages_and_numbers_the_requirements():
    prompt = document_prompt(["Valves"], [SIZE], [(3, "text")])
    assert "=== PAGE 3 ===" in prompt and '"id": 0' in prompt


def test_a_quote_on_the_cited_page_is_verified():
    answer = Answer(id=0, status="fully matched", page=3, quote="40 mm to 500 mm")
    assert check(answer, PAGES) == (answer, True)


def test_a_quote_found_on_another_page_corrects_the_page():
    fixed, ok = check(Answer(id=0, status="fully matched", page=4, quote="40 mm to 500 mm"), PAGES)
    assert ok and fixed.page == 3


def test_a_quote_found_nowhere_is_unverified_and_a_missing_answer_needs_no_quote():
    assert check(Answer(id=0, status="fully matched", page=3, quote="made up"), PAGES)[1] is False
    assert check(Answer(id=0, status="missing capability"), PAGES)[1] is True


def test_a_checked_answer_beats_a_stronger_unchecked_one_and_then_the_stronger_status_wins():
    weak = Answer(id=0, status="partially matched", page=3, quote="q")
    strong = Answer(id=0, status="fully matched", page=9, quote="q")
    assert merge([("a.pdf", weak, True), ("b.pdf", strong, False)]).status == "partially matched"
    assert merge([("a.pdf", weak, True), ("b.pdf", strong, True)]).pages == [9]


def test_an_unverified_quote_is_flagged_in_the_note_and_a_missing_label_names_no_page():
    flagged = label_of(Draft(status="fully matched", pages=[3], file="a.pdf", quote="q", verified=False))
    assert flagged.note.startswith("UNVERIFIED") and flagged.page == [3] and flagged.checked is False
    assert label_of(Draft(status="missing capability", pages=[], file=None, quote="", verified=True)).page is None


def test_the_drafted_sheet_has_a_label_for_every_manufacturer_with_a_draft():
    from app.extraction.evidence import question

    draft = Draft(status="fully matched", pages=[3], file="a.pdf", quote="q", verified=True)
    gold = to_gold([SIZE], ["a", "b"], {(question(SIZE), "a"): draft})
    assert list(gold["nominal_size"]) == ["a"] and gold["nominal_size"]["a"].status == "fully matched"
