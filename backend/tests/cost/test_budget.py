from builders import CALLS

from app.chunking.base import Chunk
from app.cost.budget import atoms_within, plan, price, prices
from app.extraction.atomize import AtomicRequirement
from app.extraction.evidence import question
from app.retrieval.search import Hit
from app.tender.items import Item


def req(title: str, value: str = "1.6") -> AtomicRequirement:
    return AtomicRequirement(
        item=Item(title=title, quantity=1), pdf_page=1, source_name="Pressure", source_value=f"{value} MPa",
        attribute="nominal_pressure", kind="number", operator="equals", values=[value], unit="MPa", evidence="product",
    )


class Index:
    """Returns as many long passages as it is asked for, so a question costs more the deeper it reads."""

    chunks: list = []

    def search_many(self, queries, manufacturer, depth):
        chunk = Chunk(manufacturer=manufacturer, file="k.pdf", pdf_page=2, kind="text", section=None, text="x" * 4000)
        return [Hit(score=1.0, keyword=1.0, meaning=0.5, chunk=chunk)] * depth


class Plain:
    """A model with no cache."""

    max_calls = CALLS


class Saved:
    """A model whose every answer is already saved."""

    max_calls = CALLS

    def has(self, system, user):
        return True


ATOMS = [req("Valve A", "1"), req("Valve B", "2"), req("Valve C", "3")]
ONE = price(Plain(), ATOMS[0], Index().search_many([], "ksb", 1))  # tokens of one question read from one passage


def planned(llm, budget, depths=(2, 1), atoms=ATOMS):
    return plan(llm, Index(), atoms, ["ksb"], {}, token_budget=budget, depths=depths)


def test_a_tender_that_fits_is_evaluated_whole_at_full_depth_with_nothing_to_say():
    result = planned(Plain(), budget=10 * ONE)
    assert result.atoms == ATOMS and result.depth == 2 and result.notes == []


def test_a_tender_too_big_at_full_depth_is_read_shallower_and_says_so():
    result = planned(Plain(), budget=3 * ONE + 500)  # three questions of one passage fit; three of two do not
    assert result.atoms == ATOMS and result.depth == 1 and "best 1 passages instead of 2" in result.notes[0]


def test_a_tender_too_big_even_shallow_keeps_its_first_items_and_names_the_rest():
    result = planned(Plain(), budget=ONE + 500)
    assert [a.item.title for a in result.atoms] == ["Valve A"] and result.depth == 1
    assert "1 of 3 items in full" in result.notes[-1] and "Valve B; Valve C" in result.notes[-1]


def test_answers_already_saved_cost_nothing_so_a_big_tender_that_was_run_before_is_not_cut():
    assert planned(Saved(), budget=1).atoms == ATOMS


def test_one_item_is_always_kept_even_when_it_alone_is_over_budget():
    assert [a.item.title for a in planned(Plain(), budget=1).atoms] == ["Valve A"]


def test_a_question_two_items_share_is_paid_for_once():
    atoms = [req("Valve A"), req("Valve B")]  # the same question under two items
    priced = prices(Plain(), Index(), atoms, ["ksb"], {}, depth=1)
    assert len(priced) == 1
    assert atoms_within(atoms, ["ksb"], priced, tokens=ONE + 10, calls=5) == atoms


def test_the_number_of_model_calls_is_limited_as_well_as_the_tokens():
    priced = prices(Plain(), Index(), ATOMS, ["ksb"], {}, depth=1)
    assert atoms_within(ATOMS, ["ksb"], priced, tokens=10**9, calls=2) == ATOMS[:2]
    assert question(ATOMS[0]) != question(ATOMS[1])


def test_when_the_first_item_alone_is_over_budget_only_its_first_requirements_are_evaluated_and_the_note_says_so():
    one_item = [req("Valve A", "1"), req("Valve A", "2"), req("Valve A", "3")]
    result = planned(Plain(), budget=ONE + 500, atoms=one_item)
    assert result.atoms == one_item[:1] and result.depth == 1
    assert "0 of 1 items in full" in result.notes[-1] and "first 1 of 3 requirements" in result.notes[-1]


def test_a_later_item_that_does_not_fit_is_dropped_whole_never_cut_in_half():
    atoms = [req("Valve A", "1"), req("Valve B", "2"), req("Valve B", "3")]
    result = planned(Plain(), budget=2 * ONE + 500, atoms=atoms)  # A plus one of B's two questions would fit; B whole would not
    assert [a.item.title for a in result.atoms] == ["Valve A"]


def test_an_answer_saved_by_a_real_request_is_recognised_so_it_costs_nothing(tmp_path):
    """The saved answer is found by the system prompt the model really received, which carries the reply schema."""
    from app.extraction.evidence import SYSTEM, Found, passages_prompt
    from app.llm.llm import Reply, request_system
    from app.llm.llm_cache import CachedLLM

    class Model:
        model, settings = "m", "s"

        def generate(self, system, user):
            return Reply(text='{"findings": []}')

    hits = Index().search_many([], "ksb", 1)
    llm = CachedLLM(Model(), tmp_path, max_calls=CALLS)
    assert price(llm, ATOMS[0], hits) > 0
    llm.generate(request_system(SYSTEM, Found), passages_prompt(ATOMS[0], hits))
    assert price(llm, ATOMS[0], hits) == 0
