"""A tender as a graph: the tender has items, an item has requirement rows, a row splits into atomic requirements, and a
row may cite standards. A row printed once for all items (the same file, page, name and value) is one node shared by
those items, so "which items does this apply to" and "what does this item require" are both one lookup.

Built from the requirements the pipeline has already read; it asks no model and changes nothing about matching.
"""
from __future__ import annotations

from app.extraction.atomize import AtomicRequirement
from app.graph.graph import Graph
from app.graph.standards import names_in, standard_of

HIERARCHY = {"has_item", "has_row", "splits_into"}


def row_id(a: AtomicRequirement) -> str:
    return f"row:{a.file}:{a.pdf_page}:{a.source_name}={a.source_value}"


def build(tender: str, atoms: list[AtomicRequirement]) -> Graph:
    graph = Graph()
    graph.node("tender", "tender", tender)
    for n, a in enumerate(atoms):
        item, row, atom = f"item:{a.item.title}", row_id(a), f"requirement:{n}"
        graph.node(item, "item", a.item.title)
        graph.node(row, "row", f"{a.source_name}: {a.source_value}")
        graph.node(atom, "requirement", f"{a.attribute} {a.operator} {', '.join(a.values)}")
        graph.link("tender", item, "has_item")
        graph.link(item, row, "has_row")
        graph.link(row, atom, "splits_into")
        for name in names_in(a.source_value):
            graph.node(standard_of(name), "standard", standard_of(name), name)
            graph.link(row, standard_of(name), "cites", f"{a.file} page {a.pdf_page}")
    return graph


def items_of(graph: Graph, row: str) -> list[str]:
    """The items a requirement row applies to."""
    return sorted(graph.nodes[l.source].label for l in graph.links if l.relation == "has_row" and l.target == row)


def shared_rows(graph: Graph) -> list[str]:
    """The rows that apply to more than one item: requirements the tender states once for several items."""
    return [node_id for node_id, node in graph.nodes.items() if node.kind == "row" and len(items_of(graph, node_id)) > 1]


def unreachable(graph: Graph) -> list[str]:
    """Requirements that cannot be reached from the tender through items and rows. Should always be empty."""
    reached = graph.below("tender", HIERARCHY)
    return [node_id for node_id, node in graph.nodes.items() if node.kind == "requirement" and node_id not in reached]
