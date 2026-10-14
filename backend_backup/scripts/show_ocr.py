"""Show the text the model read off a picture-only page, as the pipeline sees it.

Usage: python -m scripts.show_ocr <pdf> <page number>
"""
import sys

import pymupdf

from app.services.llm_factory import make_llm
from app.services.ocr import reader_for, render_page


def main(pdf: str, page_number: str) -> None:
    llm = make_llm()
    with pymupdf.open(pdf) as doc:
        print(reader_for(llm)(render_page(doc[int(page_number) - 1])))
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])