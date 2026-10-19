"""What matching a tender is about to cost and how long it will take, in words for the person who must say yes.

The numbers come from the budget plan, which prices every question before it is asked. The money is an estimate of the model's input tokens
(the output is small next to them); the time is a range, because the model's speed varies.
"""
from __future__ import annotations

import math

from pydantic import BaseModel

from app.config import number_setting
from app.services.parallel import WORKERS

RUPEES_PER_MILLION_TOKENS = number_setting("RUPEES_PER_MILLION_TOKENS", 100)  # input and output together, at the current price
SECONDS_PER_CALL_FAST = number_setting("SECONDS_PER_CALL_FAST", 3)
SECONDS_PER_CALL_SLOW = number_setting("SECONDS_PER_CALL_SLOW", 10)
FIXED_MINUTES = 1  # reading the evidence into verdicts and writing the report


class Estimate(BaseModel):
    requirements: int  # single checkable requirements that will be evaluated
    questions: int  # new questions for the model; answers already saved cost nothing
    tokens: int  # their input tokens
    rupees: int
    minutes_low: int
    minutes_high: int
    notes: list[str]  # what the budget cut, so a smaller job is not mistaken for the whole tender


def make_estimate(requirements: int, questions: int, tokens: int, notes: list[str]) -> Estimate:
    def minutes(seconds_per_call: int) -> int:
        return FIXED_MINUTES + math.ceil(questions * seconds_per_call / WORKERS / 60)

    return Estimate(
        requirements=requirements, questions=questions, tokens=tokens, notes=notes,
        rupees=math.ceil(tokens * RUPEES_PER_MILLION_TOKENS / 1_000_000) if questions else 0,
        minutes_low=minutes(SECONDS_PER_CALL_FAST), minutes_high=minutes(SECONDS_PER_CALL_SLOW),
    )
