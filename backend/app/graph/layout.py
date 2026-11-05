"""A tender's layout for the web page: items, the printed requirement rows (a row shared by several items once), the
atomic requirements each row splits into, the standards cited, and each item's family and the attributes its family
lists that the tender's reading does not name.

Built from the tender's saved reading only (llm_factory.saved_answers_only): it cannot ask the model, and a tender whose
reading is not saved raises instead. It is for showing; matching does not use it, whatever KNOWLEDGE_GRAPH says.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.categories.config import category_by_words, load_categories
from app.extraction.atomize import AtomicRequirement
from app.graph import products
from app.graph.standards import standards_graph
from app.graph.tender import build, items_of, row_id
from app.llm.llm_factory import saved_answers_only
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for


class LayoutRow(BaseModel):
    name: str
    value: str
    file: str
    page: int
    requirements: list[str]
    shared_with: list[str]  # the other items this printed row applies to
    standards: list[str]


class LayoutItem(BaseModel):
    title: str
    category: str | None
    family: str | None
    family_from: str | None  # "title" or "type value"
    not_named: list[str]     # attributes category.json lists for this kind of product that the tender's reading does not name (it may use another name)
    rows: list[LayoutRow]


class LayoutStandard(BaseModel):
    name: str
    also_written: list[str]
    named_together: list[str]


class Layout(BaseModel):
    tender: str
    items: list[LayoutItem]
    standards: list[LayoutStandard]
    shared_rows: int
    requirements: int


def layout(tender: str, atoms: list[AtomicRequirement], root: Path, default_category: str = "") -> Layout:
    graph, catalogue, configs = build(tender, atoms), products.build(root), {c.name: c for c in load_categories(root)}
    first = {row_id(a): a for a in reversed(atoms)}  # each printed row's first requirement, for its name, value and page
    items = []
    for item_node in (l.target for l in graph.links if l.relation == "has_item"):
        title = graph.nodes[item_node].label
        mine = [a for a in atoms if a.item.title == title]
        category = next(iter(category_by_words(title, root)), None) or default_category or None
        config = configs.get(category or "")
        types = [v for a in mine if config and a.attribute in config.type_attributes for v in a.values]
        family, source = products.family_of(config, title, types) if config else (None, None)
        expected = products.expected_attributes(catalogue, category, family) if config else []
        asked = {a.attribute for a in mine}
        rows = []
        for row in (l.target for l in graph.links if l.relation == "has_row" and l.source == item_node):
            a = first[row]
            rows.append(LayoutRow(
                name=a.source_name, value=a.source_value, file=a.file, page=a.pdf_page,
                requirements=[graph.nodes[l.target].label for l in graph.links if l.relation == "splits_into" and l.source == row
                              and atoms[int(l.target.split(":")[1])].item.title == title],  # a shared row: this item's own only
                shared_with=[t for t in items_of(graph, row) if t != title],
                standards=sorted(graph.nodes[l.target].label for l in graph.links if l.relation == "cites" and l.source == row),
            ))
        items.append(LayoutItem(title=title, category=category, family=family, family_from=source,
                                not_named=[x for x in expected if x not in asked], rows=rows))
    known = standards_graph()
    cited = [n for n in graph.nodes if graph.nodes[n].kind == "standard"]
    standards = [LayoutStandard(name=graph.nodes[n].label, also_written=sorted(set(known.nodes[n].names) - {graph.nodes[n].label}) if n in known.nodes else [],
                                named_together=sorted(known.linked(n, "named_together"))) for n in cited]
    shared = sum(1 for n, node in graph.nodes.items() if node.kind == "row" and len(items_of(graph, n)) > 1)
    return Layout(tender=tender, items=items, standards=standards, shared_rows=shared, requirements=len(atoms))


def tender_layout(tender: str, folder: Path, root: Path, category: str = "") -> Layout:
    """The layout of a tender whose reading is saved. Raises RuntimeError when it is not: nothing is asked."""
    llm = saved_answers_only()
    atoms, _ = read_atoms(llm, folder, reader_for(llm))
    return layout(tender, atoms, root, category)
