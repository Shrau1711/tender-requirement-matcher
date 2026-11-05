"""Product -> family -> attribute links, from category.json."""
import json

import pymupdf
import pytest

from app.categories.config import CATEGORIES_DIR, load_categories, read_config
from app.extraction import atomize
from app.graph import products
from app.graph.layout import tender_layout


@pytest.fixture
def root(tmp_path):
    folder = tmp_path / "valves"
    (folder / "manufacturers").mkdir(parents=True)
    (folder / "category.json").write_text(json.dumps({
        "product_words": ["valve"], "type_attributes": ["valve_type"],
        "attributes": ["nominal_size", "body_material"],
        "families": {"butterfly valve": {"words": ["butterfly"], "attributes": ["disc_material"]},
                     "gate valve": {"words": ["gate", "sluice"]}},
    }), encoding="utf-8")
    load_categories.cache_clear()
    yield tmp_path
    load_categories.cache_clear()


def test_the_graph_links_product_to_family_to_attribute_and_says_where(root):
    graph = products.build(root)
    assert graph.linked("product:valves", "has_family") == {"family:valves:butterfly valve": ["valves/category.json"],
                                                            "family:valves:gate valve": ["valves/category.json"]}
    assert graph.linked("family:valves:butterfly valve", "has_attribute") == {"attribute:disc_material": ["valves/category.json"]}
    assert products.expected_attributes(graph, "valves", "butterfly valve") == ["nominal_size", "body_material", "disc_material"]
    assert products.expected_attributes(graph, "valves", None) == ["nominal_size", "body_material"]


def test_a_family_is_named_by_the_title_first_then_by_the_type_value(root):
    config = read_config(root / "valves")
    assert products.family_of(config, "BUTTERFLY VALVE PN 16") == ("butterfly valve", "title")
    assert products.family_of(config, "VALVE MOTORISE 300", ["Sluice"]) == ("gate valve", "type value")
    assert products.family_of(config, "Valve, 150 NB") == (None, None)


def test_whole_words_only(root):
    config = read_config(root / "valves")
    assert products.family_of(config, "Aggregate of valves for the gatehouse") == (None, None)


def test_the_shipped_categories_have_families_and_every_attribute_is_a_plain_name():
    for config in load_categories(CATEGORIES_DIR):
        assert config.families and config.attributes
        names = config.attributes + [a for f in config.families.values() for a in f.attributes]
        assert all(n == n.strip().lower() and " " not in n for n in names)


def test_no_prompt_reads_the_new_fields():
    """Only extraction_rules reach the tender-reading prompt, so families and attributes change no saved answer."""
    for config in load_categories(CATEGORIES_DIR):
        for name in config.families:
            assert name not in atomize.SYSTEM
        assert all(f'"{a}"' not in atomize.SYSTEM for a in config.attributes)


def test_a_tender_whose_reading_is_not_saved_is_refused_without_asking(tmp_path, monkeypatch):
    from app.llm import llm_factory
    monkeypatch.setattr(llm_factory, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(llm_factory, "SEED_DIR", tmp_path / "no_seed")
    asked = []
    monkeypatch.setattr(llm_factory.SavedOnly, "generate", lambda self, s, u: asked.append(u))
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Item: Gate valve. Size: DN 50. Quantity: 2", fontsize=11)
    (tmp_path / "tender").mkdir()
    doc.save(tmp_path / "tender" / "bid.pdf")
    with pytest.raises(RuntimeError, match="limit 0"):
        tender_layout("T", tmp_path / "tender", CATEGORIES_DIR)
    assert asked == []
