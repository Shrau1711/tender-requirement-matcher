from app.services.evaluation import confusion, overclaims, per_status, to_markdown, trust, underclaims
from app.services.gold import Row


def row(gold: str, ours: str, page: int | None = 1, gold_pages: list[int] | None = None) -> Row:
    return Row(attribute="a", manufacturer="m", gold=gold, ours=ours, score=0, gold_pages=gold_pages or [1], our_page=page, reason="r")


ROWS = [row("fully matched", "fully matched"), row("fully matched", "partially matched"), row("missing capability", "fully matched"), row("missing capability", "missing capability", None)]


def test_precision_and_recall_are_counted_per_status():
    full = per_status(ROWS)["fully matched"]
    assert (full["said"], full["labelled"], full["right"]) == (2, 2, 1)
    assert full["precision"] == 0.5 and full["recall"] == 0.5


def test_a_status_nobody_labelled_has_no_recall():
    assert per_status([row("fully matched", "fully matched")])["missing capability"]["recall"] is None


def test_saying_more_than_the_person_found_is_an_overclaim_and_saying_less_an_underclaim():
    assert [r.ours for r in overclaims(ROWS)] == ["fully matched"] and [r.ours for r in underclaims(ROWS)] == ["partially matched"]


def test_the_confusion_matrix_counts_each_pair():
    assert confusion(ROWS)[("fully matched", "partially matched")] == 1


def test_the_markdown_has_every_section_and_lists_the_disagreements():
    text = to_markdown({"T1": ROWS})
    assert all(h in text for h in ("## Agreement per tender", "## Per status", "## Confusion matrix", "## Disagreements")) and "| T1 | 4 | 0 |" in text


def test_answers_are_grouped_by_the_warnings_they_carried():
    plain, scanned = row("fully matched", "fully matched"), row("missing capability", "fully matched").model_copy(update={"flags": ["scanned page"]})
    groups = trust([plain, scanned, row("fully matched", "missing capability")])
    assert groups["fully matched, no warning"] == [plain] and groups["fully matched, with a warning"] == [scanned]
    assert groups["warning: scanned page"] == [scanned] and "partially matched, no warning" not in groups


def test_a_missing_capability_is_grouped_by_whether_anything_was_found():
    nothing, failed = row("missing capability", "missing capability"), row("fully matched", "missing capability").model_copy(update={"found": True})
    groups = trust([nothing, failed])
    assert groups["missing capability, nothing found"] == [nothing] and groups["missing capability, found but does not meet it"] == [failed]
