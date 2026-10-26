from app.extraction.atomize import AtomicRequirement
from app.graph.tender import build, items_of, shared_rows, unreachable
from app.tender.items import Item


def atom(item, name, value, attribute, page=1):
    return AtomicRequirement(item=Item(title=item), pdf_page=page, source_name=name, source_value=value, attribute=attribute,
                             kind="text", operator="equals", values=[value], unit=None, evidence="product")


ATOMS = [
    atom("Gate valve", "Size", "DN 50", "nominal_size"),
    atom("Gate valve", "Standard", "API 600 / BS 1873", "design_standard", page=2),
    atom("Globe valve", "Standard", "API 600 / BS 1873", "design_standard", page=2),  # printed once for both items
    atom("Globe valve", "Rating", "Class 150 and PN 16", "pressure_class"),
    atom("Globe valve", "Rating", "Class 150 and PN 16", "nominal_pressure"),      # one row, two requirements
]


def test_a_row_printed_once_for_several_items_is_one_shared_node():
    graph = build("T-1", ATOMS)
    [shared] = shared_rows(graph)
    assert items_of(graph, shared) == ["Gate valve", "Globe valve"]


def test_every_requirement_hangs_from_the_tender_and_rows_cite_their_standards():
    graph = build("T-1", ATOMS)
    kinds = [n.kind for n in graph.nodes.values()]
    assert (kinds.count("item"), kinds.count("row"), kinds.count("requirement")) == (2, 3, 5)
    assert unreachable(graph) == []
    cited = {l.target for l in graph.links if l.relation == "cites"}
    assert cited == {"API600", "BS1873"}


def test_the_graph_can_be_drawn():
    assert build("T-1", ATOMS[:1]).to_mermaid().startswith("flowchart LR")
