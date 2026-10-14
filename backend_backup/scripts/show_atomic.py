"""Atomise a tender's requirements with the LLM and print them.

Usage: python -m scripts.show_atomic <tender.pdf>
"""
import sys

from app.services.atomize import atomize_items, uncovered_rows
from app.services.llm_factory import make_llm
from app.services.pdf_reader import read_pdf
from app.services.tender import read_requirements


def main(path: str) -> None:
    llm = make_llm()
    for item, rows, atoms in atomize_items(llm, read_requirements(read_pdf(path))):
        print(f"\n== {item.title}  x{item.quantity}")
        for a in atoms:
            unit = f" {a.unit}" if a.unit else ""
            print(f"  {a.attribute:24} {a.operator:9} {' | '.join(a.values)}{unit}   [{a.kind}, {a.evidence}]")
        for r in uncovered_rows(rows, atoms):
            print(f"  !! dropped by the model: {r.name} => {r.value}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1])