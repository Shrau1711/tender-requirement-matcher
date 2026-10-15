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


def test_a_product_of_the_wrong_type_does_not_win_even_when_it_scores_higher_elsewhere():
    kind = req("pump_type", "text", ["vertical multistage"])
    table = {
        (0, "m"): [ev("pump type ETNE", items=["ETNE"], name="End-suction"), ev("vertical multistage", items=["vertical multistage"], name="In-line")],
        (1, "m"): [size_of("End-suction")],
        (2, "m"): [handle_of("End-suction")],
    }
    product, _ = best_product([kind, SIZE, HANDLE], "m", table, ALIASES, True)
    assert product == "In-line"


def test_a_statement_about_a_part_of_the_product_counts_for_the_product_of_its_document():
    motor_says = ev("Lever", items=["Lever"], name="Standard motors")
    table = {(0, "m"): [size_of("A")], (1, "m"): [motor_says]}
    product, outcomes = best_product([SIZE, HANDLE], "m", table, ALIASES, True)
    assert product == "A" and outcomes[1].score == 100


def test_a_part_is_not_a_product_but_a_pump_named_after_its_drive_is():
    from app.services.products import is_component
    assert is_component("Standard motors") and is_component("Cartridge mechanical seal")
    assert not is_component("Canned Motor Pump - i-CM") and not is_component("CR, CRI, CRN pumps")
