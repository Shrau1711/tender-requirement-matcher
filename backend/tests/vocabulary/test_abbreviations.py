from app.vocabulary.abbreviations import alternatives, canonical

GROUPS = {"BW": ["butt weld", "buttweld"], "SW": ["socket weld"], "SS": ["stainless steel"]}


def test_a_short_form_is_also_searched_written_out():
    assert alternatives("end connection BW", GROUPS) == ["end connection butt weld", "end connection buttweld"]


def test_a_written_out_form_is_also_searched_short():
    assert "body SS 316" in alternatives("body stainless steel 316", GROUPS)


def test_a_short_form_inside_a_longer_word_is_left_alone():
    assert alternatives("SS304 glass", GROUPS) == []


def test_butt_weld_and_bw_read_the_same_but_socket_weld_does_not():
    assert canonical("Butt-Weld ends", GROUPS) == canonical("BW ends", GROUPS)
    assert canonical("socket weld", GROUPS) != canonical("BW", GROUPS)


def test_the_shipped_list_loads():
    assert "butt weld" in alternatives("BW")[0]
