from app.services.ocr_compare import (
    confident_pages,
    mean,
    number_recall,
    number_hits,
    numbers_in,
    pooled_recall,
    word_recall,
)


def test_numbers_are_counted_and_thousands_commas_ignored():
    assert numbers_in("PN 16, 1,000 mm and 16.5 bar") == {"16": 1, "1000": 1, "16.5": 1}


def test_number_recall_is_the_share_of_the_references_numbers_found():
    assert number_recall("size 40 pressure 16 temp 175", "size 40 pressure 16") == 2 / 3
    assert number_recall("size 40 size 40", "size 40") == 0.5  # a repeated number must be found as often
    assert number_recall("no numbers here", "anything 5") is None


def test_number_hits_count_found_and_total():
    assert number_hits("size 40 pressure 16 page 6", "size 40 pressure 16") == (2, 3)
    assert number_hits("none", "5") == (0, 0)


def test_pooled_recall_weighs_a_page_by_how_many_numbers_it_has():
    assert pooled_recall([(0, 1), (49, 50)]) == 49 / 51  # a missed page number barely matters
    assert pooled_recall([(0, 0)]) is None


def test_word_recall_ignores_short_words_and_case():
    assert word_recall("Maximum Working pressure of 69 Bar", "maximum working PRESSURE") == 0.75
    assert word_recall("1 2 3", "x") is None


def test_mean_skips_missing_values():
    assert mean([1.0, None, 0.5]) == 0.75
    assert mean([None]) is None


def test_confident_pages_say_whether_the_reader_knows_when_it_is_wrong():
    pages = [(0.97, 10, 10), (0.92, 8, 10), (0.70, 1, 10), (0.60, 0, 0)]
    assert confident_pages(pages, 0.90) == (2, 0.9)
    assert confident_pages(pages, 0.99) == (0, None)
