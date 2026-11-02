from builders import req

from app.chunking.base import Chunk
from app.judging.match import Outcome
from app.reporting.audit import audit, to_markdown
from app.vocabulary.terms import candidates, share_said

NOISE = req("noise_level", "number", ["85"], "dBA")


def chunk(text: str, maker: str = "m", page: int = 3) -> Chunk:
    return Chunk(manufacturer=maker, file="f.pdf", pdf_page=page, kind="text", section=None, text=text)


def outcome(found: bool, status: str = "missing capability", maker: str = "m") -> Outcome:
    return Outcome(requirement=NOISE, manufacturer=maker, status=status, score=0, found=found, review=False, reason="r")


def test_a_chunk_saying_the_attribute_and_the_wanted_number_is_a_candidate():
    assert share_said(NOISE, chunk("Sound level: noise level 85 dBA at 1 m")) >= 0.6


def test_a_chunk_without_the_wanted_number_is_ruled_out():
    assert share_said(NOISE, chunk("noise level 70 dBA")) == 0


def test_candidates_come_from_anywhere_in_the_documents_best_first():
    chunks = [chunk("unrelated"), chunk("noise level 85 dBA", page=7)]
    assert [c.pdf_page for c in candidates(NOISE, chunks)] == [7]


def test_a_zero_that_has_evidence_is_a_real_mismatch():
    assert audit([outcome(True)], [])[0].kind == "found but does not meet it"


def test_a_zero_with_nothing_found_is_a_possible_miss_when_the_documents_say_it_somewhere():
    found = audit([outcome(False)], [chunk("noise level 85 dBA", page=7)])[0]
    assert found.kind == "possibly missed by the search" and found.where == ["f.pdf p7"]


def test_a_zero_with_nothing_found_is_likely_absent_when_no_passage_says_it():
    assert audit([outcome(False)], [chunk("flow rate 20 m3/h")])[0].kind == "likely absent from the documents"


def test_the_markdown_counts_each_kind_per_manufacturer():
    text = to_markdown(audit([outcome(False), outcome(True, maker="n")], []))
    assert "| m | 0 | 0 | 1 |" in text and "| n | 1 | 0 | 0 |" in text
