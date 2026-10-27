from builders import ev, req

from app.evaluation.gold import Label, answer_keys, compare
from app.evaluation.rows import (
    compare_by_row,
    keys_by_row,
    load_anchors,
    row_anchors,
    save_anchors,
)
from app.judging.match import match_requirement
from app.judging.measure import load_aliases

ALIASES = load_aliases()


def from_row(attribute, name, value, values, kind="text"):
    """A requirement read from the tender row `name: value`."""
    return req(attribute, kind, values).model_copy(update={"source_name": name, "source_value": value})


# How the labels were made: one row gives one requirement, another row is split into two.
LABELLED = [
    from_row("valve_end_connection", "End Connection", "Wafer", ["Wafer"]),
    from_row("pressure_class", "Rating", "Class 150 and PN 16", ["Class 150"]),
    from_row("nominal_pressure", "Rating", "Class 150 and PN 16", ["PN 16"]),
]
SHEET = {
    "valve_end_connection": {"a": Label(status="fully matched", page=2)},
    "pressure_class": {"a": Label(status="missing capability")},
    "nominal_pressure": {"a": Label(status="missing capability")},
}


def outcomes(atoms):
    return [match_requirement(a, "a", [ev(a.values[0], items=a.values)] if a.attribute.endswith("connection") else [], ALIASES) for a in atoms]


def test_with_the_names_the_labels_were_made_with_rows_and_names_give_the_same_result():
    rows, how = compare_by_row(outcomes(LABELLED), SHEET, row_anchors(LABELLED))
    assert rows == compare(outcomes(LABELLED), SHEET) and how == {"row": 3}


def test_a_requirement_named_differently_is_still_found_by_its_tender_row():
    renamed = [LABELLED[0].model_copy(update={"attribute": "end_connection"}), *LABELLED[1:]]
    assert len(compare(outcomes(renamed), SHEET)) == 2  # by name, the renamed requirement has no label
    rows, _ = compare_by_row(outcomes(renamed), SHEET, row_anchors(LABELLED))
    assert [r.attribute for r in rows] == ["valve_end_connection", "pressure_class", "nominal_pressure"]


def test_a_split_row_is_paired_in_order_even_when_both_names_change():
    renamed = [LABELLED[0], LABELLED[1].model_copy(update={"attribute": "class"}), LABELLED[2].model_copy(update={"attribute": "pn"})]
    keys, how = keys_by_row(renamed, row_anchors(LABELLED))
    assert list(keys.values()) == ["valve_end_connection", "pressure_class", "nominal_pressure"] and how == {"row": 3}


def test_a_row_split_differently_or_not_in_the_anchors_falls_back_to_the_name():
    once = [LABELLED[0], LABELLED[1].model_copy(update={"values": ["Class 150", "PN 16"]})]  # one requirement where there were two
    other_row = from_row("bore", "Bore", "Full", ["Full"])
    keys, how = keys_by_row([*once, other_row], row_anchors(LABELLED))
    assert list(keys.values()) == ["valve_end_connection", "pressure_class", "bore"] and how == {"row": 1, "name": 2}


def test_anchors_survive_saving_and_are_not_taken_for_answer_keys(tmp_path):
    save_anchors(row_anchors(LABELLED), tmp_path / "T.rows.json")
    (tmp_path / "T.json").write_text("{}", encoding="utf-8")
    assert load_anchors(tmp_path / "T.rows.json") == row_anchors(LABELLED)
    assert [p.name for p in answer_keys(tmp_path)] == ["T.json"]


def test_every_shipped_answer_key_has_anchors_that_cover_all_its_entries():
    from app.evaluation.gold import load_gold
    from app.evaluation.rows import anchors_file

    for key_file in answer_keys():
        anchors = load_anchors(anchors_file(key_file.stem))
        assert set(load_gold(key_file)) <= {k for keys in anchors.values() for k in keys}, key_file.name
