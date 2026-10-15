"""Show what data was collected and where it is thin: documents per manufacturer, and which requirements each manufacturer's documents answer.

Usage: python -m scripts.show_coverage <tender folder or pdf> <category_dir> [output file]
"""
import sys
from pathlib import Path

from app.services.corpus import load_chunks
from app.services.coverage import inventory, matrix, to_markdown
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import gather


def main(tender: str, category_dir: str, out: str = "reports/coverage.md") -> None:
    llm = make_llm()
    read_image = reader_for(llm)
    found = gather(llm, tender, category_dir, read_image)
    text = to_markdown(inventory(load_chunks(category_dir, read_image)), matrix(found.atoms, found.makers, found.table))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(text, encoding="utf-8")
    print(f"Wrote {out}\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
