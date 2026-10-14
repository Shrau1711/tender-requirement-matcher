"""Show, per manufacturer, the chunks found for each product requirement of a tender's first item.

Usage: python -m scripts.show_candidates <tender.pdf> <category_dir> [manufacturer]

Shows the same chunks the model is given to read (evidence.TOP_K of them) for each requirement.
"""
import sys

from app.services.atomize import atomize_items
from app.services.corpus import load_chunks
from app.services.evidence import TOP_K
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pdf_reader import read_pdf
from app.services.queries import load_unit_views, queries_for
from app.services.search import Index
from app.services.tender import read_requirements


def main(tender: str, category_dir: str, only: str | None = None) -> None:
    llm, views = make_llm(), load_unit_views()
    index = Index(load_chunks(category_dir, reader_for(llm)))
    _, _, atoms = next(atomize_items(llm, read_requirements(read_pdf(tender))))  # first item only
    makers = [m for m in sorted({c.manufacturer for c in index.chunks}) if only in (None, m)]
    for atom in (a for a in atoms if a.evidence == "product"):
        queries = queries_for(atom, views)
        print(f"\n### {atom.attribute}: {' | '.join(atom.values)} {atom.unit or ''}\n    queries: {queries}")
        for maker in makers:
            for rank, hit in enumerate(index.search_many(queries, maker, TOP_K), 1):
                c = hit.chunk
                text = c.text[:110].replace("\n", " | ")
                print(f"  {maker:11} #{rank} p{c.pdf_page:<3} [{c.kind:7}] kw {hit.keyword:5.1f} sim {hit.meaning:.2f}  {text}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(*sys.argv[1:4])