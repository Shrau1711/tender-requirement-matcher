from builders import ev, req

from app.services.match import match_all, match_requirement, summarize
from app.services.measure import load_aliases

ALIASES = load_aliases()
SIZE = req("nominal_size", "number", ["125"], "mm")


def test_no_evidence_is_a_missing_capability():
    out = match_requirement(SIZE, "m", [], ALIASES)
    assert (out.status, out.score, out.found) == ("missing capability", 0, False)


def test_unreadable_documents_say_so():
    assert "no readable text" in match_requirement(SIZE, "m", [], ALIASES, readable=False).reason


def test_paperwork_is_unsupported_not_failed():
    paper = req("test_report", "yes_no", ["Yes"]).model_copy(update={"evidence": "paperwork"})
    assert match_requirement(paper, "m", [], ALIASES).status == "unsupported requirement"


def test_the_best_piece_of_evidence_wins():
    weak, strong = ev("40mm to 100mm", "range", [40, 100], "mm"), ev("50 NB to 350 NB", "range", [50, 350], "NB")
    out = match_requirement(SIZE, "m", [weak, strong], ALIASES)
    assert (out.status, out.score) == ("fully matched", 100)


def test_found_but_not_meeting_is_partial_or_zero_but_still_counts_as_found():
    out = match_requirement(SIZE, "m", [ev("40mm to 100mm", "range", [40, 100], "mm")], ALIASES)
    assert (out.score, out.found) == (0, True) and out.reason.startswith("found, but does not meet")


def test_summary_leaves_out_unsupported_requirements():
    paper = req("test_report", "yes_no", ["Yes"]).model_copy(update={"evidence": "paperwork"})
    table = {(0, "m"): [ev("50 NB to 350 NB", "range", [50, 350], "NB")]}
    outcomes = match_all([SIZE, paper], ["m"], table, ALIASES, {"m"})
    summary = summarize("m", outcomes)
    assert (summary.compatibility, summary.coverage, summary.counted) == (100, 100, 1)

def test_an_unreadable_manufacturer_is_not_assessed_rather_than_scored_zero():
    outcomes = match_all([SIZE], ["m"], {}, ALIASES, set())
    summary = summarize("m", outcomes)
    assert (outcomes[0].assessed, summary.compatibility, summary.coverage, summary.counted) == (False, None, None, 0)