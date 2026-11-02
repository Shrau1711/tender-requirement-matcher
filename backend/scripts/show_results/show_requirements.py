"""Print the requirements found in a tender, item by item, and the notes on how it was read.

Usage: python -m scripts.show_results.show_requirements <tender folder or pdf>
"""
import sys

from app.llm.llm_factory import make_llm
from app.reading.ocr import reader_for
from app.tender.reader import read_tender


def main(path: str) -> None:
    llm = make_llm()
    read = read_tender(llm, path, reader_for(llm))
    last = None
    for r in read.requirements:
        if r.item != last:
            print(f"\n== {r.item.title}  x{r.item.quantity if r.item.quantity is not None else '?'}")
            last = r.item
        print(f"  {r.file} p{r.pdf_page}  [{r.group or '-'}]  {r.name}  =>  {r.value}")
    print("\nnotes:" if read.notes else "\nno notes")
    for note in read.notes:
        print(f"  - {note}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1])
