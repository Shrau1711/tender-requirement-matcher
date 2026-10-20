"""Compare a free, local page reader with the saved model transcriptions of the same scanned catalogue pages. Makes no model calls and changes nothing.

Setup (once, in the backend venv):  pip install rapidocr onnxruntime
Usage:  python -m scripts.compare_ocr <category dir, e.g. ..\\data\\categories\\pumps> [report.csv]

For every scanned page (the same test the pipeline uses) whose model transcription is already saved, the page is read locally and two figures are
shown: how many of the saved transcription's numbers the local reader also found, and how many of its words. The reader's own confidence is
recorded too, so the summary can say whether it knows when it is wrong. A page the model has not transcribed is counted and skipped. Set LLM_MAX_CALLS=0 to be certain nothing can be spent.
"""
import csv
import hashlib
import sys
from pathlib import Path

import pymupdf

from app.services.llm import Reply
from app.services.llm_factory import make_llm
from app.services.ocr import PROMPT, render_page
from app.services.ocr_compare import (
    GOOD_ENOUGH,
    confident_pages,
    mean,
    number_recall,
    word_recall,
)
from app.services.pdf_reader import needs_ocr

CONFIDENCE_STEPS = (0.80, 0.85, 0.90, 0.95)


def scanned_pages(pdf: Path):
    """(page number, picture) of each page the pipeline would send to the model."""
    with pymupdf.open(pdf) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True).strip()
            if needs_ocr(page, text, len(page.get_images(full=True))):
                yield number, render_page(page)


def local_reader():
    from rapidocr import RapidOCR  # imported here so the rest of the app never needs it

    engine = RapidOCR()

    def read(png: bytes) -> tuple[str, float]:
        """The text and the reader's average confidence in it (0 when it found no text)."""
        result = engine(png)
        if not result.txts:
            return "", 0.0
        return "\n".join(result.txts), sum(result.scores) / len(result.scores)

    return read


def main(category_dir: str, out: str = "reports/ocr_comparison.csv") -> None:
    llm, read = make_llm(), local_reader()
    rows, skipped = [], 0
    for pdf in sorted(Path(category_dir).glob("manufacturers/*/*.[pP][dD][fF]")):
        for number, png in scanned_pages(pdf):
            saved = llm.saved(PROMPT, hashlib.sha256(png).hexdigest())
            if not saved:
                skipped += 1
                continue
            model_text = Reply.model_validate_json(saved.read_text(encoding="utf-8")).text
            local_text, confidence = read(png)
            rows.append([pdf.parent.name, pdf.name, number, number_recall(model_text, local_text), word_recall(model_text, local_text), confidence])
            print(f"{pdf.parent.name}/{pdf.name} p{number}: numbers {rows[-1][3]}, words {rows[-1][4]}, confidence {confidence:.2f}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["maker", "file", "page", "number_recall", "word_recall", "confidence"])
        writer.writerows(rows)
    with_numbers = [r[3] for r in rows if r[3] is not None]
    well = sum(v >= GOOD_ENOUGH for v in with_numbers)
    print(f"\n{len(rows)} scanned pages compared, {skipped} skipped (no saved transcription)")
    print(f"numbers found by the local reader: {mean(with_numbers):.0%} on average; {well}/{len(with_numbers)} pages at {GOOD_ENOUGH:.0%} or better")
    print(f"words found: {mean([r[4] for r in rows]):.0%} on average")
    print("\nIf only pages the local reader is sure about stay local (the rest go to the model):")
    for threshold in CONFIDENCE_STEPS:
        kept, recall = confident_pages([(r[5], r[3]) for r in rows], threshold)
        print(f"  confidence >= {threshold:.2f}: {kept}/{len(rows)} pages stay local, numbers found on them: {'-' if recall is None else f'{recall:.0%}'}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
