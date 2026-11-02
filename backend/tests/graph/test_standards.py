import pytest

from app.graph.graph import Graph
from app.graph.standards import GRAPH_FILE, build, link_between, names_in, standard_of


@pytest.mark.parametrize(("text", "found"), [
    ("Designed to IS:13095-2008", ["IS13095"]),
    ("tested to BS EN ISO 5208", ["ISO5208"]),         # adopted by BS and EN: the ISO standard itself
    ("face to face per BS EN 558-1", ["EN558-1"]),
    ("API standard 614, Chapter 3", ["API614"]),
    ("API 6D and API-610", ["API6D", "API610"]),
    ("flanges to EN 1092-1", ["EN1092-1"]),             # a part number is kept apart from the main number
    ("the pressure is 16 bar", []),                     # "is" in lower case is a word, not the Indian standard IS 16
    ("shaft in EN 8 steel, body 1.4408 (EN 1.4408)", []),  # steel grades and material numbers are not standards
    ("ASME..........................4", []),            # dot leaders of a table of contents
])
def test_standard_names_are_found_and_written_one_way(text, found):
    assert [standard_of(n) for n in names_in(text)] == found


def test_spellings_of_one_standard_are_one_node_and_pairs_are_links_with_where_seen():
    graph = build([("Tested to BS EN ISO 5208 / API 598", "intervalve p5"), ("ISO 5208/API 598", "leader p1"), ("EN 593", "ksb p2")])
    assert graph.nodes["ISO5208"].names == ["BS EN ISO 5208", "ISO 5208"]
    assert graph.linked("ISO5208", "named_together") == {"API598": ["intervalve p5", "leader p1"]}
    assert graph.linked("EN593", "named_together") == {}


def test_a_link_is_same_for_one_standard_and_together_only_for_a_named_pair():
    graph = build([("API 600 / BS 1873", "l_and_t p8")])
    assert link_between(graph, "ISO 5208", "BS EN ISO 5208:1999") == ("same", "ISO 5208", "BS EN ISO 5208", [])
    assert link_between(graph, "API 600", "BS 1873") == ("together", "API 600", "BS 1873", ["l_and_t p8"])
    assert link_between(graph, "API 600", "API 602") is None


def test_the_saved_graph_loads_and_keeps_its_sources():
    graph = Graph.load(GRAPH_FILE)
    assert graph.nodes["ISO5208"].names and all(l.seen_in for l in graph.links)
