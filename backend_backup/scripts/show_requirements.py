"""Print the technical requirements found in a tender PDF.

Usage: python -m scripts.show_requirements <tender.pdf>
"""
import sys

from app.services.pdf_reader import read_pdf
from app.services.tender import read_requirements


def main(path: str) -> None:
    last = None
    for r in read_requirements(read_pdf(path)):
        if r.item != last:
            print(f"\n== {r.item.title}  x{r.item.quantity}")
            last = r.item
        print(f"  p{r.pdf_page}  [{r.group or '-'}]  {r.name}  =>  {r.value}")


if __name__ == "__main__":
    main(sys.argv[1])