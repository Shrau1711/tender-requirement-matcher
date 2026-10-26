"""Draft an answer key for a tender by reading each manufacturer document in full, then list the rows a person should check by hand (see review_gold).

This does not use the pipeline's search: the model reads whole documents, so it can find what the search missed. It is a draft,
not the truth: a person must check the rows listed, and mark them "checked": true in the sheet. Never overwrites an existing sheet.

Usage: python -m scripts.gold.draft_gold <tender folder or pdf> <category_dir> [number of agreeing rows to spot-check]
"""
import sys
from pathlib import Path

from app.chunking.corpus import manufacturers
from app.config import number_setting
from app.evaluation.gold import GOLD_DIR, save_gold
from app.extraction.drafting import (
    SYSTEM,
    Drafted,
    check,
    document_prompt,
    merge,
    questions,
    to_gold,
)
from app.extraction.evidence import question
from app.llm.llm import ask
from app.llm.llm_factory import make_llm
from app.llm.parallel import run_parallel
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for
from app.reading.pdf_reader import read_pdf
from scripts.gold import review_gold

MAX_TOKENS = number_setting("DRAFT_MAX_TOKENS", 3_000_000)  # refuse to run if the documents would cost more than this to read


def main(tender: str, category_dir: str, spot_checks: str = "12") -> None:
    path = GOLD_DIR / f"{Path(tender).stem}.json"
    if path.exists():
        sys.exit(f"{path} already exists; not overwriting your labels")
    llm = make_llm()
    read_image = reader_for(llm)
    atoms, _ = read_atoms(llm, tender, read_image)
    asked, makers = questions(atoms), manufacturers(category_dir)
    titles = list(dict.fromkeys(a.item.title for a in atoms))
    docs = [(m, read_pdf(pdf, read_image)) for m in makers for pdf in sorted(Path(category_dir, "manufacturers", m).glob("*.[pP][dD][fF]"))]
    pages = {id(d): [(p.pdf_page, p.text) for p in d.pages] for _, d in docs}
    tokens = sum(len(t) for d in pages.values() for _, t in d) // 4
    print(f"{len(docs)} documents, {len(asked)} distinct questions: about {tokens:,} input tokens in {len(docs)} model calls")
    if tokens > MAX_TOKENS:
        sys.exit(f"over the limit of {MAX_TOKENS:,} (DRAFT_MAX_TOKENS); raise it if you are sure")

    def read(job):
        maker, doc = job
        answers = ask(llm, SYSTEM, document_prompt(titles, asked, pages[id(doc)]), Drafted).answers
        by_page = dict(pages[id(doc)])
        return maker, Path(doc.path).name, [(a.id, *check(a, by_page)) for a in answers if 0 <= a.id < len(asked)]

    found: dict[tuple[tuple, str], list] = {}
    for maker, file, answers in run_parallel(read, docs):
        for i, answer, verified in answers:
            found.setdefault((question(asked[i]), maker), []).append((file, answer, verified))
    drafts = {key: merge(items) for key, items in found.items()}
    gold = to_gold(atoms, makers, drafts)
    save_gold(gold, path)

    print(f"wrote {path}")
    review_gold.main(tender, category_dir, spot_checks)

if __name__ == "__main__":
    main(*sys.argv[1:4])
