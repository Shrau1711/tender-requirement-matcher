"""Compare a free, local page reader with the saved model transcriptions of the same scanned catalogue pages. Makes no model calls and changes nothing.

Setup (once, in the backend venv; install only the readers you want to try):
  pip install rapidocr onnxruntime      engines: rapidocr, rapidocr-en, rapidocr-medium
  pip install easyocr                   engine: easyocr
  pip install pytesseract               engine: tesseract (also needs the Tesseract program: winget install UB-Mannheim.TesseractOCR)
Usage:  python -m scripts.eval.compare_ocr <category dir, e.g. ..\\data\\categories\\pumps> [report.csv] [engine]

For every scanned page (the same test the pipeline uses) whose model transcription is already saved, the page is read locally and figures are
shown: how many of the saved transcription's numbers the local reader also found (counted over all pages together, so a page number does not weigh as much as a spec table), and how many of its words. The reader's own confidence is
recorded too, so the summary can say whether it knows when it is wrong. A page the model has not transcribed is counted and skipped. Set LLM_MAX_CALLS=0 to be certain nothing can be spent.
"""
import csv
import hashlib
import os
import sys
from pathlib import Path

import pymupdf

from app.llm.llm import Reply
from app.llm.llm_factory import make_llm
from app.reading.ocr import PROMPT, render_page
from app.reading.ocr.compare import (
    confident_pages,
    mean,
    number_hits,
    pooled_recall,
    word_recall,
)
from app.reading.pdf_reader import needs_ocr

CONFIDENCE_STEPS = (0.80, 0.85, 0.90, 0.95)
SPEC_PAGE = 10  # a page with at least this many numbers is a spec page, where a missed number can change a verdict


def scanned_pages(pdf: Path):
    """(page number, picture) of each page the pipeline would send to the model."""
    with pymupdf.open(pdf) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True).strip()
            if needs_ocr(page, text, len(page.get_images(full=True))):
                yield number, render_page(page)


RAPID_SETTINGS = {  # which PaddleOCR model RapidOCR loads for reading text (Rec) and finding it (Det)
    "rapidocr": {},  # the package default: a small model trained mainly for Chinese
    "rapidocr-en": {"Rec.lang_type": "en", "Rec.ocr_version": "PP-OCRv5", "Rec.model_type": "mobile"},
    "rapidocr-medium": {"Rec.model_type": "medium"},
}
ENGINES = (*RAPID_SETTINGS, "easyocr", "tesseract")


def rapid_reader(engine_name: str):
    from rapidocr import (  # imported here so the rest of the app never needs it
        LangRec,
        ModelType,
        OCRVersion,
        RapidOCR,
    )

    kinds = {"Rec.lang_type": LangRec, "Rec.ocr_version": OCRVersion, "Rec.model_type": ModelType}  # RapidOCR wants its own types, not plain text
    engine = RapidOCR(params={key: kinds[key](value) for key, value in RAPID_SETTINGS[engine_name].items()} or None)

    def read(png: bytes) -> tuple[str, float]:
        """The text and the reader's average confidence in it (0 when it found no text)."""
        result = engine(png)
        if not result.txts:
            return "", 0.0
        return "\n".join(result.txts), sum(result.scores) / len(result.scores)

    return read


def easy_reader():
    import easyocr

    engine = easyocr.Reader(["en"], gpu=False)

    def read(png: bytes) -> tuple[str, float]:
        found = engine.readtext(png)  # [(box, text, confidence)]
        return ("\n".join(t for _, t, _ in found), sum(c for _, _, c in found) / len(found)) if found else ("", 0.0)

    return read


def tesseract_reader():
    import io

    import pytesseract
    from PIL import Image

    def read(png: bytes) -> tuple[str, float]:
        data = pytesseract.image_to_data(Image.open(io.BytesIO(png)), lang="eng", config="--psm 6", output_type=pytesseract.Output.DICT)
        words = [(w, float(c) / 100) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0]
        return (" ".join(w for w, _ in words), sum(c for _, c in words) / len(words)) if words else ("", 0.0)

    return read


def local_reader(engine_name: str = "rapidocr"):
    if engine_name in RAPID_SETTINGS:
        return rapid_reader(engine_name)
    return {"easyocr": easy_reader, "tesseract": tesseract_reader}[engine_name]()


def main(category_dir: str, out: str = "reports/ocr_comparison.csv", engine: str = "rapidocr") -> None:
    if engine not in ENGINES:
        sys.exit(f"Unknown engine {engine!r}. Choose one of: {', '.join(ENGINES)}")
    print(f"Reader: {engine}")
    llm, read = make_llm(), local_reader(engine)
    rows, skipped = [], 0
    for pdf in sorted(Path(category_dir).glob("manufacturers/*/*.[pP][dD][fF]")):
        for number, png in scanned_pages(pdf):
            saved = llm.saved(PROMPT, hashlib.sha256(png).hexdigest())
            if not saved:
                skipped += 1
                continue
            model_text = Reply.model_validate_json(saved.read_text(encoding="utf-8")).text
            local_text, confidence = read(png)
            if os.environ.get("OCR_SHOW") == f"{pdf.name}:{number}":  # e.g. process-pump-catalogue.pdf:7 writes both texts to reports/ocr_show_text.txt
                Path("reports").mkdir(exist_ok=True)
                Path("reports/ocr_show_text.txt").write_text(f"=== MODEL ===\n{model_text}\n\n=== LOCAL READER ===\n{local_text}\n", encoding="utf-8")  # a file: the Windows console cannot print every character
            found, total = number_hits(model_text, local_text)
            rows.append([pdf.parent.name, pdf.name, number, found, total, word_recall(model_text, local_text), confidence])
            print(f"{pdf.parent.name}/{pdf.name} p{number}: numbers {found}/{total}, words {rows[-1][5]}, confidence {confidence:.2f}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["maker", "file", "page", "numbers_found", "numbers_total", "word_recall", "confidence"])
        writer.writerows(rows)
    counts = [(r[3], r[4]) for r in rows]
    heavy = [c for c in counts if c[1] >= SPEC_PAGE]
    print(f"\n{len(rows)} scanned pages compared, {skipped} skipped (no saved transcription)")
    print(f"numbers found by the local reader, all pages together: {pooled_recall(counts):.1%} ({sum(f for f, _ in counts)} of {sum(t for _, t in counts)})")
    print(f"on the {len(heavy)} pages with {SPEC_PAGE}+ numbers (the spec tables): {pooled_recall(heavy):.1%}" if heavy else "no page has enough numbers to be a spec page")
    print(f"words found: {mean([r[5] for r in rows]):.0%} on average")
    print("\nIf only pages the local reader is sure about stay local (the rest go to the model):")
    for threshold in CONFIDENCE_STEPS:
        kept, recall = confident_pages([(r[6], r[3], r[4]) for r in rows], threshold)
        print(f"  confidence >= {threshold:.2f}: {kept}/{len(rows)} pages stay local, numbers found on them: {'-' if recall is None else f'{recall:.1%}'}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
