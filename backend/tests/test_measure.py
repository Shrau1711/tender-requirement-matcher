from app.services.measure import convert, load_aliases, unit_in

ALIASES = load_aliases()


def test_alternative_reading_exists_for_pn():
    assert convert(1.6, "PN", "bar", "design_pressure", ALIASES, alternative=True) == 16


def test_alternative_reading_is_none_when_alias_has_none():
    # DN has a normal reading (mm) but no second reading; this used to crash.
    assert convert(125, "DN", "mm", "nominal_size", ALIASES, alternative=True) is None


def test_normal_reading_of_dn_still_works():
    assert convert(125, "DN", "mm", "nominal_size", ALIASES) == 125


def test_a_trade_unit_is_found_in_the_statement_when_the_reading_left_it_out():
    assert unit_in("PN 1.0 I PN 1.6", "nominal_pressure", ALIASES) == "PN"
    assert unit_in("PN 16", "nominal_size", ALIASES) is None  # PN is only a pressure unit
    assert unit_in("40mm to 500mm", "nominal_size", ALIASES) is None


def test_gauge_pressures_and_inch_marks_convert_like_their_plain_units():
    assert round(convert(20, "BARG", "MPa", "nominal_pressure", ALIASES), 6) == 2
    assert round(convert(175, "PSIG", "MPa", "nominal_pressure", ALIASES), 2) == 1.21
    assert convert(2, '"', "mm", "nominal_size", ALIASES) == 50
    assert convert(12, "\u201d", "mm", "nominal_size", ALIASES) == 300  # the curly mark an OCR reader prints
    assert convert(2, "BARG", "MPa", "nominal_size", ALIASES) is None  # a pressure unit says nothing about a size


def test_mtrs_is_a_metre_and_lps_a_flow():
    assert convert(160, "meters", "mtrs", "head", ALIASES) == 160
    assert round(convert(38, "LPS", "m3/h", "discharge", ALIASES), 1) == 136.8


def test_a_head_asked_for_in_metres_of_water_column_is_compared_in_metres():
    assert convert(160, "m", "m of water column (MWC)", "operating_duty_head", load_aliases()) == 160


def test_a_unit_that_is_not_a_unit_cannot_be_converted_instead_of_failing():
    assert convert(5, "10 mm", "mm", "nominal_size", ALIASES) is None
    assert convert(5, "x 10^3 rpm", "rpm", "speed", ALIASES) is None
