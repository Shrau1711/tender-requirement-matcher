import json

from app.services.atomize import AtomicRequirement
from app.services.chunker import Chunk
from app.services.evidence import find_evidence
from app.services.search import Hit
from app.services.tender import Item


def req(kind: str = "number") -> AtomicRequirement:
    return AtomicRequirement(
        item=Item(title="Butterfly valve", quantity=5), pdf_page=5, source_name="Pressure", source_value="1.6 MPa",
        attribute="nominal_pressure", kind=kind, operator="equals", values=["1.6"], unit="MPa", evidence="product",
    )


def hit(text: str, keyword: float = 1.0) -> Hit:
    chunk = Chunk(manufacturer="ksb", file="k.pdf", pdf_page=2, kind="text", section=None, text=text)
    return Hit(score=1.0, keyword=keyword, meaning=0.5, chunk=chunk)


def reply(passage: int, quote: str, same: str = "yes") -> str:
    finding = {"passage": passage, "stated": "PN 10/16", "product": "BOAX-B", "same_product_type": same, "quote": quote}
    return json.dumps({"findings": [finding]})


def test_a_quote_found_in_the_passage_is_kept(fake_llm):
    found = find_evidence(fake_llm([reply(0, "nominal pressure  PN 10/16")]), req(), [hit("Nominal pressure\nPN 10/16")])
    assert found[0].pdf_page == 2 and found[0].stated == "PN 10/16"


def test_a_quote_not_in_the_passage_is_dropped(fake_llm):
    assert find_evidence(fake_llm([reply(0, "Nominal pressure PN 25")]), req(), [hit("Nominal pressure PN 10/16")]) == []


def test_a_passage_number_that_does_not_exist_is_dropped(fake_llm):
    assert find_evidence(fake_llm([reply(4, "PN 10/16")]), req(), [hit("PN 10/16")]) == []


def test_a_standard_with_no_keyword_match_costs_no_model_call(fake_llm):
    llm = fake_llm([])
    assert find_evidence(llm, req("standard"), [hit("something else", keyword=0.0)]) == []
    assert llm.prompts == []


def test_statements_about_another_type_of_product_are_dropped(fake_llm):
    assert find_evidence(fake_llm([reply(0, "PN 10/16", same="no")]), req(), [hit("PN 10/16")]) == []


def test_the_same_statement_from_two_rows_counts_once(fake_llm):
    two = json.dumps({"findings": [json.loads(reply(0, "PN 10/16"))["findings"][0], json.loads(reply(1, "PN 10/16"))["findings"][0]]})
    assert len(find_evidence(fake_llm([two]), req(), [hit("PN 10/16 a"), hit("PN 10/16 b")])) == 1


class OneHitIndex:
    chunks: list = []

    def search_many(self, queries, manufacturer, top_k):
        return [hit("Nominal pressure\nPN 10/16")]


def test_a_requirement_shared_by_two_items_is_looked_up_once_per_manufacturer(fake_llm):
    from app.services.evidence import evidence_table

    other = req().model_copy(update={"item": Item(title="Butterfly valve 80", quantity=2)})
    llm = fake_llm([reply(0, "PN 10/16")])
    table = evidence_table(llm, OneHitIndex(), [req(), other], ["ksb"], {})
    assert len(llm.prompts) == 1 and table[0, "ksb"] == table[1, "ksb"] and table[0, "ksb"][0].stated == "PN 10/16"


class RankedIndex:
    """A search that returns one chunk; the manufacturer's other chunks are only reachable by scanning."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def search_many(self, queries, manufacturer, top_k):
        return [Hit(score=1.0, keyword=1.0, meaning=0.5, chunk=self.chunks[0])]


def chunk(text: str, page: int, maker: str = "ksb") -> Chunk:
    return Chunk(manufacturer=maker, file="k.pdf", pdf_page=page, kind="text", section=None, text=text)


def test_a_passage_saying_the_requirements_words_and_number_is_read_even_when_the_search_ranked_it_low():
    from app.services.evidence import retrieve

    index = RankedIndex([chunk("unrelated", 1), chunk("Nominal pressure 1.6 MPa", 9), chunk("Nominal pressure 2.5 MPa", 10), chunk("Nominal pressure 1.6 MPa", 4, maker="other")])
    assert [h.chunk.pdf_page for h in retrieve(index, req(), "ksb", {})] == [1, 9]


def test_the_term_scan_can_be_switched_off_and_never_repeats_a_passage_already_read():
    from app.services.evidence import retrieve

    index = RankedIndex([chunk("Nominal pressure 1.6 MPa", 1), chunk("Nominal pressure 1.6 MPa", 9)])
    assert [h.chunk.pdf_page for h in retrieve(index, req(), "ksb", {})] == [1, 9]
    assert [h.chunk.pdf_page for h in retrieve(index, req(), "ksb", {}, rescue=False)] == [1]
    assert len(retrieve(RankedIndex([chunk("Nominal pressure 1.6 MPa", 1)]), req(), "ksb", {})) == 1


def test_an_identifier_is_not_scanned_for_because_the_keyword_search_already_finds_it_exactly():
    from app.services.evidence import retrieve

    index = RankedIndex([chunk("unrelated", 1), chunk("nominal pressure 1.6", 9)])
    assert [h.chunk.pdf_page for h in retrieve(index, req("standard"), "ksb", {})] == [1]
