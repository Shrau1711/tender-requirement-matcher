"""Products, their families and their attributes, from each category's category.json: product -> family -> attribute.

A category is one product (valves); its families (butterfly valve, gate valve) are named by words in an item's title or
in its type value ("valve_type: butterfly"); each family has the category's attributes plus its own. Built from the
config files only: no model, no documents, and nothing here changes matching.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.categories.config import CATEGORIES_DIR, CategoryConfig, load_categories
from app.graph.graph import Graph


def product_id(category: str) -> str:
    return f"product:{category}"


def family_id(category: str, family: str) -> str:
    return f"family:{category}:{family}"


def attribute_id(attribute: str) -> str:
    return f"attribute:{attribute}"


def build(root: Path = CATEGORIES_DIR) -> Graph:
    graph = Graph()
    for config in load_categories(root):
        product, where = product_id(config.name), f"{config.name}/category.json"
        graph.node(product, "product", config.name)
        for attribute in config.attributes:
            graph.node(attribute_id(attribute), "attribute", attribute)
            graph.link(product, attribute_id(attribute), "has_attribute", where)
        for name, family in config.families.items():
            graph.node(family_id(config.name, name), "family", name)
            graph.link(product, family_id(config.name, name), "has_family", where)
            for attribute in family.attributes:
                graph.node(attribute_id(attribute), "attribute", attribute)
                graph.link(family_id(config.name, name), attribute_id(attribute), "has_attribute", where)
    return graph


def names(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word.lower())}\b", text.lower()) is not None


def family_of(config: CategoryConfig, title: str, type_values: list[str] = ()) -> tuple[str | None, str | None]:
    """(the family, and what named it: "title" or "type value"), or (None, None). The title is looked at first; the
    families are tried in the order category.json lists them."""
    for source, texts in (("title", [title]), ("type value", list(type_values))):
        for name, family in config.families.items():
            if any(names(text, word) for text in texts for word in family.words):
                return name, source
    return None, None


def expected_attributes(graph: Graph, category: str, family: str | None) -> list[str]:
    """What a product of this category, and of this family if known, is described by: the category's attributes, then the family's."""
    ids = [product_id(category)] + ([family_id(category, family)] if family else [])
    found = [graph.nodes[l.target].label for node in ids for l in graph.links if l.source == node and l.relation == "has_attribute"]
    return list(dict.fromkeys(found))
