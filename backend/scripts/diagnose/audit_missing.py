"""For every requirement a manufacturer scored 0 on, say whether the documents contradict it, probably say it somewhere the search missed, or say nothing.

This checks the system's own misses without any answer key: a plain scan of every passage of the manufacturer's documents, no model calls.

Usage: python -m scripts.diagnose.audit_missing <tender folder or pdf> <category_dir> [output file]
"""
import sys
from pathlib import Path

from app.chunking.corpus import load_chunks
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import gather, score
from app.reading.ocr import reader_for
from app.reporting.audit import audit, to_markdown


def main(tender: str, category_dir: str, out: str = "reports/audit.md") -> None:
    llm = make_llm()
    read_image = reader_for(llm)
    found = gather(llm, tender, category_dir, read_image)
    text = to_markdown(audit(score(found), load_chunks(category_dir, read_image)))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(text, encoding="utf-8")
    print(f"Wrote {out}\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
