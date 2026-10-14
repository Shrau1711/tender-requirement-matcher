from builders import ev, req

from app.services.compare import verdict
from app.services.evidence import Limit
from app.services.measure import load_aliases

ALIASES = load_aliases()


PRESSURE = req("nominal_pressure", "number", ["1.6"], "MPa")
SIZE = req("nominal_size", "number", ["125"], "mm")


def test_a_list_of_pressure_ratings_that_includes_the_need_is_met():
    assert verdict(PRESSURE, ev("PN 10/16", "options", [10, 16], "PN"), ALIASES).score == 100


def test_a_lower_maximum_is_not_met_and_is_not_rescued_by_the_other_reading():
    assert verdict(PRESSURE, ev("Upto PN10", "up_to", [10], "PN"), ALIASES).score == 0


def test_a_maximum_equal_to_the_need_is_met():
    assert verdict(PRESSURE, ev("Upto PN16", "up_to", [16], "PN"), ALIASES).score == 100


def test_a_higher_maximum_is_credited_but_not_in_full():
    assert verdict(PRESSURE, ev("Upto PN25", "up_to", [25], "PN"), ALIASES).score == 75


def test_pn_written_in_megapascals_is_flagged_as_a_different_reading():
    found = verdict(PRESSURE, ev("PN 1.0 I PN 1.6", "options", [1.0, 1.6], "PN"), ALIASES)
    assert (found.score, found.review) == (50, True)


def test_a_size_range_in_nb_covers_the_size_in_mm():
    assert verdict(SIZE, ev("50 NB to 350 NB", "range", [50, 350], "NB"), ALIASES).score == 100


def test_five_inches_is_a_125_millimetre_nominal_size():
    assert verdict(SIZE, ev("INCH: 5", "single", [5], "INCH"), ALIASES).score == 100


def test_a_size_range_that_misses_the_size_is_not_met():
    assert verdict(SIZE, ev("40mm to 100mm", "range", [40, 100], "mm"), ALIASES).score == 0


def test_a_unit_that_cannot_be_converted_is_flagged_not_failed():
    found = verdict(PRESSURE, ev("Upto ASME Class #150", "up_to", [150], "Class"), ALIASES)
    assert (found.score, found.review) == (25, True)


def test_a_condition_caps_the_score_and_asks_for_review():
    found = verdict(PRESSURE, ev("16 bar", "single", [16], "bar", condition="DN 40 - 600"), ALIASES)
    assert (found.score, found.review) == (75, True) and "DN 40 - 600" in found.reason


def test_an_unnamed_product_caps_the_score():
    assert verdict(SIZE, ev("DN: 125", "single", [125], "DN", product="unclear"), ALIASES).score == 75


def test_a_standard_must_match_exactly_but_not_the_year():
    wanted = req("governing_specification", "standard", ["IS 13095"])
    assert verdict(wanted, ev("x", items=["API 609", "IS 13095:2008"]), ALIASES).score == 100
    assert verdict(wanted, ev("x", items=["API 609", "IS 3095"]), ALIASES).score == 0


def test_a_word_in_common_is_enough_for_a_kind_of_connection():
    wanted = req("valve_end_connection", "choice", ["Flangeless Wafer Valve"])
    assert verdict(wanted, ev("x", items=["Wafer", "Lugged"]), ALIASES).score == 100
    assert verdict(wanted, ev("x", items=["Double Flanged"]), ALIASES).score == 0


def test_several_wanted_values_earn_a_share():
    wanted = req("flange_class", "choice", ["Class 125", "Class 150"])
    assert verdict(wanted, ev("x", items=["Class 150"]), ALIASES).score == 50


def test_a_stated_reference_the_requirement_never_mentions_cannot_be_compared():
    wanted = req("face_to_face_dimension", "choice", ["Wafer Short (PN 2.5) Class 125/150"])
    found = verdict(wanted, ev("x", items=["ISO 5752 Tab 5", "BS EN558"]), ALIASES)
    assert (found.score, found.review) == (25, True)


def test_a_plain_different_choice_is_still_a_miss():
    wanted = req("valve_end_connection", "choice", ["Wafer"])
    assert verdict(wanted, ev("x", items=["Double Flanged"]), ALIASES).score == 0


def test_a_missing_unit_is_read_from_the_statement():
    found = verdict(PRESSURE, ev("PN 1.0 I PN 1.6", "options", [1.0, 1.6], None), ALIASES)
    assert (found.score, found.review) == (50, True)


def test_a_number_with_no_unit_anywhere_cannot_be_compared():
    found = verdict(PRESSURE, ev("16", "single", [16], None), ALIASES)
    assert (found.score, found.review) == (25, True) and "no unit" in found.reason


def test_a_label_naming_the_thing_counts_even_when_the_values_are_model_codes():
    wanted = req("handle_type", "text", ["operating handle (lever) assembly"])
    found = verdict(wanted, ev("Levers: SR+, SP+, S+", items=["SR+", "SP+", "S+"]), ALIASES)
    assert found.score == 100


def test_a_reason_is_one_line_even_when_the_statement_was_printed_over_two():
    found = verdict(PRESSURE, ev("PN 1.0 I\nPN 1.6", "options", [1.0, 1.6], "PN"), ALIASES)
    assert "\n" not in found.reason


def test_a_condition_that_covers_the_size_asked_for_does_not_cap_the_score():
    limit = Limit(shape="range", numbers=[65, 1200], unit="NB")
    found = verdict(PRESSURE, ev("Upto PN16", "up_to", [16], "PN", condition="65 NB to 1200 NB", limit=limit), ALIASES, [SIZE])
    assert (found.score, found.review) == (100, False)


def test_a_condition_that_leaves_out_the_size_asked_for_means_it_does_not_apply():
    limit = Limit(shape="range", numbers=[650, 1000], unit="DN")
    wanted = req("valve_end_connection", "choice", ["Wafer"])
    found = verdict(wanted, ev("Wafer-type body", items=["Wafer-type body"], condition="DN 650 - 1000", limit=limit), ALIASES, [wanted, SIZE])
    assert found.score == 0 and "nominal_size" in found.reason and "125" in found.reason


def test_a_condition_about_something_the_tender_does_not_ask_stays_a_flagged_cap():
    limit = Limit(shape="up_to", numbers=[1], unit="mbar")
    found = verdict(PRESSURE, ev("16 bar", "single", [16], "bar", condition="vacuum up to 1 mbar", limit=limit), ALIASES, [SIZE])
    assert (found.score, found.review) == (75, True)


def test_a_vacuum_level_is_not_mistaken_for_the_pressure_rating_asked_for():
    wanted = req("application", "text", ["Tight Shut Off"])
    limit = Limit(shape="up_to", numbers=[1], unit="mbar")
    found = verdict(wanted, ev("tight shut-off", items=["tight shut-off"], condition="vacuum up to 1 mbar", limit=limit), ALIASES, [wanted, PRESSURE])
    assert (found.score, found.review) == (75, True)


def test_a_match_read_from_a_scanned_page_keeps_its_score_but_is_flagged_for_review():
    wanted = req("handle_type", "text", ["Lever"])
    scanned = ev("Lever", items=["Lever"]).model_copy(update={"ocr": True})
    found = verdict(wanted, scanned, ALIASES)
    assert (found.score, found.review) == (100, True) and "scanned" in found.reason
    assert verdict(wanted, ev("Lever", items=["Lever"]), ALIASES).review is False