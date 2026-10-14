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

def test_a_stated_value_is_read_into_parts(fake_llm):
    finding = {
        "passage": 0, "stated": "Upto PN16", "product": "BOAX-B", "same_product_type": "yes", "quote": "Upto PN16",
        "shape": "up_to", "numbers": [16], "unit": "PN", "condition": "DN 40 - 600",
    }
    found = find_evidence(fake_llm([json.dumps({"findings": [finding]})]), req(), [hit("Pressure Rating: Upto PN16")])
    assert (found[0].shape, found[0].numbers, found[0].unit, found[0].condition) == ("up_to", [16.0], "PN", "DN 40 - 600")