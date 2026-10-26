import pytest

from app.extraction.atomize import AtomicRequirement
from app.extraction.evidence import Evidence
from app.graph.standards import build
from app.judging import compare
from app.judging.compare import CANNOT_COMPARE, EQUIVALENT, items_verdict
from app.tender.items import Item


def standard(value, source_value=None):
    return AtomicRequirement(item=Item(title="Valve"), pdf_page=1, source_name="Standard", source_value=source_value or value,
                             attribute="design_standard", kind="standard", operator="equals", values=[value], unit=None, evidence="product")


def stated(text):
    return Evidence(manufacturer="m", file="f.pdf", pdf_page=3, product="p", same_product_type="yes", stated=text, items=[text], quote=text)


@pytest.fixture
def graph_on(monkeypatch):
    monkeypatch.setattr(compare, "KNOWLEDGE_GRAPH", "on")
    monkeypatch.setattr(compare, "standards_graph", lambda: build([("API 600 / BS 1873", "l_and_t p8")]))


def test_with_the_graph_off_nothing_changes():
    assert items_verdict(standard("ISO 5208"), stated("BS EN ISO 5208")).score == 0


def test_the_same_standard_under_another_name_is_met(graph_on):
    verdict = items_verdict(standard("ISO 5208"), stated("BS EN ISO 5208"))
    assert verdict.score == 100 and "under another body's name" in verdict.reason


def test_a_standard_only_named_together_goes_to_a_person_when_the_tender_accepts_an_equivalent(graph_on):
    verdict = items_verdict(standard("API 600", "API 600 or equivalent"), stated("BS 1873"))
    assert verdict.score == CANNOT_COMPARE and verdict.flags == [EQUIVALENT] and "l_and_t p8" in verdict.reason


def test_named_together_is_never_a_match_and_is_ignored_without_or_equivalent(graph_on):
    assert items_verdict(standard("API 600"), stated("BS 1873")).score == 0
