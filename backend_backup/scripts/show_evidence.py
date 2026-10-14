"""Show what each manufacturer's documents state about each product requirement of a tender's first item.

Usage: python -m scripts.show_evidence <tender.pdf> <category_dir>
"""
import sys
import time

from app.services.atomize import atomize_items
from app.services.corpus import load_chunks, manufacturers
from app.services.evidence import evidence_table
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pdf_reader import read_pdf
from app.services.queries import load_unit_views
from app.services.search import Index
from app.services.tender import read_requirements


def lap(label: str, since: float) -> float:
    now = time.time()
    print(f"[time] {label}: {now - since:.1f}s", file=sys.stderr)
    return now


def main(tender: str, category_dir: str) -> None:
    started = clock = time.time()
    llm, views = make_llm(), load_unit_views()
    chunks = load_chunks(category_dir, reader_for(llm))
    clock = lap(f"read and chunk {len(chunks)} chunks", clock)
    index = Index(chunks)
    clock = lap("build the search indexes", clock)
    _, _, atoms = next(atomize_items(llm, read_requirements(read_pdf(tender))))  # first item only
    clock = lap("read the tender", clock)
    makers = manufacturers(category_dir)
    table = evidence_table(llm, index, atoms, makers, views)
    lap("search and read the passages", clock)
    for i, atom in enumerate(atoms):
        if atom.evidence != "product":
            continue
        print(f"\n### {atom.attribute}: {' | '.join(atom.values)} {atom.unit or ''}")
        for maker in makers:
            if not table[i, maker]:
                print(f"  {maker:11} -- nothing found")
            for e in table[i, maker]:
                print(f"  {maker:11} p{e.pdf_page:<3} [{e.product}] {e.stated}  \"{e.quote[:90]}\"")
                print(f"{'':16}-> {e.shape} {e.numbers} unit={e.unit} items={e.items} when={e.condition} limit={e.condition_limit}")
    print(f"\n{llm.summary()}, {time.time() - started:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])