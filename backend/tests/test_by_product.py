from builders import ev, req
from conftest import FakeLLM

from app.services.by_product import best_product
from app.services.match import summarize
from app.services.measure import load_aliases
from app.services.products import canonical_names, canonical_table

ALIASES = load_aliases()
SIZE = req("nominal_size", "number", ["125"], "mm")
HANDLE = req("handle_type", "text", ["Lever"])


def size_of(name: str):
    return ev("40mm to 500mm", "range", [40, 500], "mm", name=name)


def handle_of(name: str):
    return ev("Lever", items=["Lever"], name=name)


def test_credit_cannot_be_combined_from_different_products():
    table = {(0, "m"): [size_of("Wafer valve")], (1, "m"): [handle_of("Gate valve")]}
    product, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert summarize("m", outcomes).compatibility == 50 and product in {"Wafer valve", "Gate valve"}


def test_the_product_that_meets_most_is_chosen_and_named():
    table = {(0, "m"): [size_of("A"), size_of("B")], (1, "m"): [handle_of("B")]}
    product, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert product == "B" and summarize("m", outcomes).compatibility == 100


def test_a_statement_that_names_no_product_counts_for_every_product():
    table = {(0, "m"): [size_of("A")], (1, "m"): [ev("Lever", items=["Lever"], product="unclear", name="unclear")]}
    product, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert product == "A" and outcomes[1].found


def test_with_no_named_product_all_the_evidence_is_used():
    table = {(0, "m"): [ev("40mm to 500mm", "range", [40, 500], "mm", product="unclear", name="unclear")]}
    product, outcomes = best_product([SIZE], "m", table, ALIASES, True)
    assert product is None and outcomes[0].found


def test_the_same_product_written_two_ways_is_one_product():
    llm = FakeLLM(['{"groups": [["BOAX-B", "BOAX-B - Butterfly Valve"]]}'])
    names = canonical_names(llm, ["BOAX-B", "BOAX-B - Butterfly Valve", "Other"])
    assert names == {"BOAX-B": "BOAX-B - Butterfly Valve", "BOAX-B - Butterfly Valve": "BOAX-B - Butterfly Valve", "Other": "Other"}


def test_product_names_are_unified_inside_the_evidence_table():
    llm = FakeLLM(['{"groups": [["BOAX-B", "BOAX-B butterfly valve"]]}'])
    table = {(0, "m"): [size_of("BOAX-B")], (1, "m"): [handle_of("BOAX-B butterfly valve")]}
    unified = canonical_table(llm, table, ["m"])
    assert {e.product for found in unified.values() for e in found} == {"BOAX-B butterfly valve"}


def test_the_cover_headings_are_given_to_the_model_as_context():
    llm = FakeLLM(['{"groups": [["Series 50/52", "lug type valves"]]}'])
    canonical_names(llm, ["Series 50/52", "lug type valves"], ["Series 50/52 Butterfly Valves"])
    assert "Series 50/52 Butterfly Valves" in llm.prompts[0]


def test_a_statement_naming_no_product_is_not_borrowed_from_another_document():
    other = ev("40mm to 500mm", "range", [40, 500], "mm", product="unclear").model_copy(update={"file": "other.pdf"})
    table = {(0, "m"): [other], (1, "m"): [handle_of("A")]}
    _, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert summarize("m", outcomes).compatibility == 50


def test_a_statement_naming_no_product_in_the_products_own_document_is_kept():
    same = ev("40mm to 500mm", "range", [40, 500], "mm", product="unclear")
    table = {(0, "m"): [same], (1, "m"): [handle_of("A")]}
    _, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert outcomes[0].score == 75
