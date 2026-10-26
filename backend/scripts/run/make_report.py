"""Run a tender against a category's manufacturers and write the report as JSON (for programs) and Markdown (for the bid manager).

Usage: python -m scripts.run.make_report <tender folder or pdf> <category_dir> [output folder]
"""
import sys
from pathlib import Path

from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import build_report, gather
from app.reading.ocr import reader_for
from app.reporting.report_markdown import to_markdown


def main(tender: str, category_dir: str, out_dir: str = "reports") -> None:
    llm = make_llm()
    name = Path(tender).stem if Path(tender).is_file() else Path(tender).name
    report = build_report(llm, gather(llm, tender, category_dir, reader_for(llm)), name)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / f"{name}.md").write_text(to_markdown(report), encoding="utf-8")
    for m in report.makers:
        print(f"{m.rank or '-':>2}  {m.manufacturer:12} {m.compatibility if m.compatibility is None else round(m.compatibility, 1)}")
    print(f"\nWrote {out / (name + '.json')} and {out / (name + '.md')}\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
