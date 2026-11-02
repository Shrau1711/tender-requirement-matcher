import pytest

from app.llm.retry import retry


class Busy(Exception):
    def __init__(self, code):
        self.code = code


def flaky(failures, code=503):
    state = {"left": failures}

    def call():
        if state["left"]:
            state["left"] -= 1
            raise Busy(code)
        return "ok"

    return call


def test_a_busy_service_is_asked_again_with_growing_waits():
    waits = []
    assert retry(flaky(3), sleep=waits.append) == "ok"
    assert waits == [2.0, 4.0, 8.0]


def test_it_gives_up_after_the_last_attempt():
    with pytest.raises(Busy):
        retry(flaky(10), attempts=3, sleep=lambda s: None)


def test_other_errors_are_not_retried():
    waits = []
    with pytest.raises(Busy):
        retry(flaky(1, code=400), sleep=waits.append)
    assert waits == []


def test_a_spent_budget_is_not_waited_out():
    class OutOfMoney(Exception):
        code = 429

    waits = []

    def call():
        raise OutOfMoney("Your project has exceeded its monthly spending cap.")

    with pytest.raises(OutOfMoney):
        retry(call, sleep=waits.append)
    assert waits == []
