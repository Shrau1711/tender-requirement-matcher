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


def test_naming_only_part_of_the_connection_asked_for_is_a_flagged_partial():
    wanted = req("valve_end_connection", "choice", ["Double flanged short pattern"])
    found = verdict(wanted, ev("x", items=["Double Flanged"]), ALIASES)
    assert (found.score, found.review) == (50, True) and "short" in found.reason and "pattern" in found.reason
    assert verdict(wanted, ev("x", items=["Double Flanged Short Pattern"]), ALIASES).score == 100


def test_a_word_every_product_of_that_kind_has_anyway_need_not_be_stated():
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


def test_an_abbreviation_matches_its_written_out_form_but_not_a_different_one():
    wanted = req("end_connection", "choice", ["BW"])
    assert verdict(wanted, ev("Butt weld ends", items=["Butt weld ends"]), ALIASES).score == 100
    assert verdict(wanted, ev("Socket weld ends", items=["Socket weld ends"]), ALIASES).score == 0


def test_class_ratings_that_do_not_include_the_one_asked_for_are_a_plain_miss():
    wanted = req("pressure_rating", "choice", ["1500#"])
    found = verdict(wanted, ev("ASME Class #150, #300, #600", items=["ASME Class #150", "#300", "#600"]), ALIASES)
    assert (found.score, found.review) == (0, False)


def test_a_class_range_that_includes_the_class_asked_for_is_met():
    wanted = req("pressure_rating", "choice", ["1500#"])
    assert verdict(wanted, ev("Class 150 - 2500", "range", [150, 2500], "Class"), ALIASES).score == 100


def test_a_list_of_class_numbers_without_the_one_asked_for_is_not_met():
    wanted = req("pressure_rating", "choice", ["1500#"])
    assert verdict(wanted, ev("Class 150, 300, 600", "options", [150, 300, 600], "Class"), ALIASES).score == 0


def test_a_pn_rating_is_not_taken_for_a_class_rating():
    wanted = req("pressure_rating", "choice", ["1500#"])
    assert verdict(wanted, ev("PN 250", "single", [250], "PN"), ALIASES).score == 0


def test_a_size_in_nps_is_a_nominal_size_in_mm():
    assert verdict(SIZE, ev("NPS 2 - 8", "range", [2, 8], "NPS"), ALIASES).score == 100


def test_flow_written_two_ways_is_the_same_unit():
    wanted = req("operating_duty_flow", "number", ["20"], "m3/h")
    assert verdict(wanted, ev("20 m\u00b3/h", "single", [20], "m\u00b3/h"), ALIASES).score == 100
    assert verdict(wanted, ev("32 m3/hr", "single", [32], "m3/hr"), ALIASES).score == 0


def test_head_in_metres_is_head_in_metres_of_water_column():
    wanted = req("operating_duty_head", "number", ["100"], "m of water column", operator="at_least")
    assert verdict(wanted, ev("up to 140 m", "up_to", [140], "m"), ALIASES).score == 100


def test_a_floor_below_the_wanted_minimum_does_not_prove_it():
    wanted = req("seal_pressure", "number", ["30"], "bar", operator="at_least")
    assert verdict(wanted, ev("above 25 bar", "at_least", [25], "bar"), ALIASES).score == 25
    assert verdict(wanted, ev("above 35 bar", "at_least", [35], "bar"), ALIASES).score == 100


def test_a_floor_cannot_show_a_ceiling():
    wanted = req("noise", "number", ["85"], "bar", operator="at_most")
    assert verdict(wanted, ev("above 60 bar", "at_least", [60], "bar"), ALIASES).score == 25


def test_a_size_written_as_nb40_is_checked_and_not_another_size_in_mm():
    size = req("nominal_size", "choice", ["Nb40"])
    drain = req("drain_size_nb50_to_100", "number", ["15"], "mm")
    limit = Limit(shape="range", numbers=[50, 300], unit="DN")
    found = verdict(PRESSURE, ev("Upto PN16", "up_to", [16], "PN", condition="DN 50 to 300", limit=limit), ALIASES, [drain, size])
    assert found.score == 0 and "nominal_size" in found.reason and "drain" not in found.reason
    covered = Limit(shape="range", numbers=[40, 600], unit="DN")
    assert verdict(PRESSURE, ev("Upto PN16", "up_to", [16], "PN", condition="DN 40 - 600", limit=covered), ALIASES, [drain, size]).score == 100


def test_gauge_pressure_spellings_are_the_same_unit():
    wanted = req("max_working_pressure", "number", ["2.5"], "BAR(g)")
    assert verdict(wanted, ev("10 bar", "up_to", [10], "bar"), ALIASES).score == 75


def test_a_higher_step_of_an_ordered_scale_exceeds_the_ones_asked_for():
    wanted = req("motor_efficiency_class", "choice", ["IE2", "IE3"], operator="one_of")
    assert verdict(wanted, ev("IE4", items=["IE4"]), ALIASES).score == 75
    assert verdict(wanted, ev("IE3 (Premium)", items=["IE3 (Premium)"]), ALIASES).score == 100
    assert verdict(wanted, ev("IE1", items=["IE1"]), ALIASES).score == 0


def test_a_floor_on_an_ordered_scale_is_met_by_a_higher_step():
    wanted = req("motor_efficiency_class", "choice", ["IE2"], operator="at_least")
    assert verdict(wanted, ev("IE3", items=["IE3"]), ALIASES).score == 100


def test_only_the_kind_of_material_is_a_flagged_partial_when_a_grade_is_asked_for():
    wanted = req("body_material", "choice", ["Grey cast iron IS 210 FG 260"])
    found = verdict(wanted, ev("Grey cast iron", items=["Grey cast iron"]), ALIASES)
    assert (found.score, found.review) == (50, True)
    assert verdict(wanted, ev("Grey cast iron IS 210 FG 260", items=["Grey cast iron IS 210 FG 260"]), ALIASES).score == 100


def test_a_condition_the_tender_itself_states_does_not_cap_the_score():
    wanted = req("rated_power", "number", ["5"], "kW")
    asked = req("motor_frequency", "number", ["50"], "Hz")
    found = verdict(wanted, ev("5 kW", "single", [5], "kW", condition="50 Hz"), ALIASES, [wanted, asked])
    assert (found.score, found.review) == (100, False)


def test_an_equivalent_the_tender_accepts_is_left_to_a_person_not_scored_zero():
    wanted = req("impeller_material", "choice", ["stainless steel as per IS 6911 (X04Cr17Ni12Mo2)"]).model_copy(update={"source_value": "stainless steel as per IS 6911 or equivalent"})
    found = verdict(wanted, ev("SS 304, SS 316", items=["SS 304", "SS 316"]), ALIASES)
    assert (found.score, found.review) == (25, True) and "equivalent" in found.reason


def test_a_number_with_no_unit_in_the_tender_says_so_instead_of_converting_to_none():
    found = verdict(req("viscosity", "number", ["1"]), ev("1 mm2/s", "single", [1], "mm2/s"), ALIASES)
    assert "None" not in found.reason and "no unit" in found.reason


def test_a_flag_says_why_a_person_should_look():
    from app.services.compare import SCANNED, UNITS

    wanted = req("handle_type", "text", ["Lever"])
    scanned = verdict(wanted, ev("Lever", items=["Lever"]).model_copy(update={"ocr": True}), ALIASES)
    assert scanned.flags == [SCANNED]
    assert verdict(wanted, ev("Lever", items=["Lever"]), ALIASES).flags == []
    assert verdict(PRESSURE, ev("16", "single", [16], None), ALIASES).flags == [UNITS]


PUMP_TYPE = req("pump_type", "text", ["vertical multistage, in-line type"])


def test_a_pump_type_that_names_only_one_of_the_words_asked_is_a_flagged_partial_that_says_what_is_missing():
    found = verdict(PUMP_TYPE, ev("MULTISTAGE DIFFUSER PUMP", items=["MULTISTAGE DIFFUSER PUMP"]), ALIASES)
    assert (found.score, found.review) == (50, True)
    assert "vertical" in found.reason and "multistage" not in found.reason.split("not stated:")[1]


def test_a_pump_type_that_names_all_the_words_is_met_even_when_written_differently():
    for said in ("Vertical Multistage Inline pumps", "Vertical, multistage, in-line pump"):
        assert verdict(PUMP_TYPE, ev(said, items=[said]), ALIASES).score == 100


def test_a_pump_type_that_names_none_of_the_words_is_a_miss():
    assert verdict(PUMP_TYPE, ev("pump type ETNE", items=["ETNE"]), ALIASES).score == 0


def test_the_attributes_own_name_and_the_tenders_boilerplate_need_not_be_stated():
    wanted = req("handle_type", "text", ["Operating handle (lever) assembly shall be supplied complete"])
    assert verdict(wanted, ev("Lever, Gear", items=["Lever", "Gear"]), ALIASES).score == 100
    assert verdict(wanted, ev("Wheel", items=["Wheel"]), ALIASES).score == 0


def test_or_better_is_met_by_the_stated_grade_itself():
    wanted = req("ingress_protection_rating", "text", ["IP55 or better"])
    assert verdict(wanted, ev("IP55", items=["IP55"]), ALIASES).score == 100


def test_a_number_written_in_words_is_read_as_that_number():
    wanted = req("phase", "number", ["3"], "phase")
    assert verdict(wanted, ev("Single Phase, Three Phase", "options", items=["Single Phase", "Three Phase"]), ALIASES).score == 100
    assert verdict(wanted, ev("Single Phase", items=["Single Phase"]), ALIASES).score == 0


def test_a_lone_figure_after_max_is_a_limit_that_covers_a_lower_need():
    wanted = req("service_temperature", "number", ["60"], "°C")
    found = verdict(wanted, ev("120 °C", "single", [120], "°C"), ALIASES)
    assert found.score == 0
    stated = ev("120 °C", "single", [120], "°C")
    stated = stated.model_copy(update={"quote": "Max. fluid temperature 120 °C"})
    assert verdict(wanted, stated, ALIASES).score == 75


def test_a_higher_efficiency_class_meets_or_better():
    wanted = req("motor_efficiency_class", "text", ["IE3 or better energy efficient type"])
    assert verdict(wanted, ev("IE4", items=["IE4"]), ALIASES).score == 100
    assert verdict(wanted, ev("IE2", items=["IE2"]), ALIASES).score == 0
