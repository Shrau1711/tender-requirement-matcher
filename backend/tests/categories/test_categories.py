import json

import numpy as np
import pytest

from app.categories.config import (
    CATEGORIES_DIR,
    category_by_words,
    load_categories,
    union,
)
from app.categories.routing import by_category, route_items


def category(root, name, config=None):
    (root / name / "manufacturers" / "maker").mkdir(parents=True)
    if config is not None:
        (root / name / "category.json").write_text(json.dumps(config), encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    category(tmp_path, "pumps", {"product_words": ["pump"], "type_attributes": ["pump_type"]})
    category(tmp_path, "valves", {"product_words": ["valve"], "filler_words": ["valve"]})
    category(tmp_path, "motors")  # no config file: a category with no words of its own
    (tmp_path / "notes").mkdir()  # no manufacturers folder: not a category
    return tmp_path


def test_every_folder_with_manufacturers_is_a_category_and_its_file_is_optional(root):
    assert [(c.name, c.product_words) for c in load_categories(root)] == [("motors", []), ("pumps", ["pump"]), ("valves", ["valve"])]


def test_the_vocabulary_is_the_union_over_all_categories(root):
    assert union("type_attributes", root) == ["pump_type"] and union("filler_words", root) == ["valve"]


def test_the_shipped_categories_keep_the_words_and_rules_that_used_to_be_in_the_code():
    assert union("product_words", CATEGORIES_DIR) == ["pump", "valve"]
    assert union("type_attributes", CATEGORIES_DIR) == ["pump_type", "valve_type"]
    assert union("filler_words", CATEGORIES_DIR) == ["valve"]
    assert len(union("extraction_rules", CATEGORIES_DIR)) == 1


def test_a_title_is_matched_by_the_product_words_it_says(root):
    assert category_by_words("BALL VALVE 150 mm", root) == ["valves"]
    assert category_by_words("Pump set with non return valve", root) == ["pumps", "valves"]
    assert category_by_words("Induction motor 7.5 kW", root) == []


class Near:
    """An index whose chunks all sit at one point, so routing by documents can be steered."""

    def __init__(self, point):
        self.vectors = np.array([point] * 6, dtype=np.float32)


def test_words_decide_first_and_the_documents_decide_the_rest(root):
    points = {"pumps": [1, 0, 0], "valves": [0, 1, 0], "motors": [0, 0, 1]}
    opened = []

    def index_for(folder):
        opened.append(folder.name)
        return Near(points[folder.name])

    def embed(titles):
        return np.array([[0, 0, 1] if "motor" in t.lower() else [1, 0.1, 0] for t in titles], dtype=np.float32)

    titles = ["Gate valve DN 50", "Pump set with non return valve", "Induction motor 7.5 kW", "Gate valve DN 50"]
    routed = route_items(titles, index_for, root, embed)
    assert routed == {"Gate valve DN 50": "valves", "Pump set with non return valve": "pumps", "Induction motor 7.5 kW": "motors"}
    assert sorted(opened) == ["motors", "pumps", "valves"]
    assert by_category(routed) == {"motors": ["Induction motor 7.5 kW"], "pumps": ["Pump set with non return valve"], "valves": ["Gate valve DN 50"]}


def test_the_documents_are_not_read_when_the_words_decide_every_item(root):
    def index_for(folder):
        raise AssertionError("no index should be opened")

    assert route_items(["Gate valve", "Booster pump"], index_for, root) == {"Gate valve": "valves", "Booster pump": "pumps"}


def test_a_category_with_no_documents_is_never_the_closest(root):
    class Empty:
        vectors = None

    routed = route_items(["Something else"], lambda f: Empty() if f.name != "pumps" else Near([1, 0, 0]), root,
                         lambda titles: np.array([[0, 1, 0]] * len(titles), dtype=np.float32))
    assert routed == {"Something else": "pumps"}
