"""Read a tender, split its requirements into single checkable ones with the LLM, and print them.

Usage: python -m scripts.show_results.show_atomic <tender folder or pdf>
"""
import sys

from app.extraction.atomize import atomize_items, uncovered_rows
from app.llm.llm_factory import make_llm
from app.reading.ocr import reader_for
from app.tender.reader import read_tender


def main(path: str) -> None:
    llm = make_llm()
    for item, rows, atoms in atomize_items(llm, read_tender(llm, path, reader_for(llm)).requirements):
        print(f"\n== {item.title}  x{item.quantity if item.quantity is not None else '?'}")
        for a in atoms:
            unit = f" {a.unit}" if a.unit else ""
            print(f"  {a.attribute:24} {a.operator:9} {' | '.join(a.values)}{unit}   [{a.kind}, {a.evidence}]")
        for r in uncovered_rows(rows, atoms):
            print(f"  !! dropped by the model: {r.name} => {r.value}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1])
