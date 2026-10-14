"""Check that the LLM key works and replies in the shape we expect.

Usage: python -m scripts.llm_check
"""
from pydantic import BaseModel

from app.services.llm import ask
from app.services.llm_factory import make_llm


class Answer(BaseModel):
    pressure_bar: float


def main() -> None:
    llm = make_llm()
    print(ask(llm, "Convert units.", "What is PN 16 in bar?", Answer))
    print(llm.summary())


if __name__ == "__main__":
    main()