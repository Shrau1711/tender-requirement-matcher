"""Show, per manufacturer, the chunks found for each product requirement of a tender.

Usage: python -m scripts.show_candidates <tender folder or pdf> <category_dir> [manufacturer]

Shows the same chunks the model is given to read (evidence.TOP_K of them) for each requirement.
"""
import sys

from app.services.corpus import load_chunks
from app.services.evidence import TOP_K
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views, queries_for
from app.services.search import Index


def main(tender: str, category_dir: str, only: str | None = None) -> None:
    llm, views = make_llm(), load_unit_views()
    read_image = reader_for(llm)
    index = Index(load_chunks(category_dir, read_image))
    atoms, _ = read_atoms(llm, tender, read_image)
    makers = [m for m in sorted({c.manufacturer for c in index.chunks}) if only in (None, m)]
    last = None
    for atom in (a for a in atoms if a.evidence == "product"):
        if atom.item != last:
            print(f"\n==== {atom.item.title}")
            last = atom.item
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
