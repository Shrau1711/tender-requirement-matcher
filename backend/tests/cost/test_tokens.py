import pytest

from app.cost.tokens import LimitedCounter, counter, estimate


def test_the_default_is_the_original_estimate_of_four_characters_a_token():
    assert counter("estimate") is estimate
    assert estimate("a" * 400, "b" * 41) == 110


def test_an_exact_counter_is_used_up_to_the_call_limit_and_then_estimates():
    asked = []
    count = LimitedCounter(lambda system, user: asked.append(user) or 7, limit=2)
    assert [count("s", "one"), count("s", "two"), count("s", "x" * 40)] == [7, 7, estimate("s", "x" * 40)]
    assert asked == ["one", "two"] and count.exact == 2


def test_the_same_question_is_counted_once():
    asked = []
    count = LimitedCounter(lambda system, user: asked.append(user) or 7, limit=5)
    assert count("s", "one") == count("s", "one") == 7 and asked == ["one"]


def test_with_no_calls_allowed_nothing_is_sent():
    count = LimitedCounter(lambda system, user: pytest.fail("must not count"), limit=0)
    assert count("s" * 8, "u" * 8) == 4


def test_a_failed_count_falls_back_to_the_estimate():
    def broken(system, user):
        raise ConnectionError("offline")

    assert LimitedCounter(broken, limit=3)("s" * 8, "u" * 8) == 4


def test_an_unknown_counter_is_refused():
    with pytest.raises(ValueError, match="estimate or gemini"):
        counter("tiktoken")
