"""Show what each manufacturer's documents state about each product requirement of a tender.

Usage: python -m scripts.show_results.show_evidence <tender folder or pdf> <category_dir>
"""
import sys
import time

from app.chunking.corpus import manufacturers
from app.extraction.evidence import evidence_table
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for
from app.retrieval.queries import load_unit_views
from app.vectorstore.ingest import open_index


def lap(label: str, since: float) -> float:
    now = time.time()
    print(f"[time] {label}: {now - since:.1f}s", file=sys.stderr)
    return now


def main(tender: str, category_dir: str) -> None:
    started = clock = time.time()
    llm, views = make_llm(), load_unit_views()
    read_image = reader_for(llm)
    index = open_index(category_dir, read_image)
    chunks = index.chunks
    clock = lap(f"read, chunk and index {len(chunks)} chunks", clock)
    atoms, _ = read_atoms(llm, tender, read_image)
    clock = lap("read the tender", clock)
    makers = manufacturers(category_dir)
    table = evidence_table(llm, index, atoms, makers, views)
    lap("search and read the passages", clock)
    last = None
    for i, atom in enumerate(atoms):
        if atom.evidence != "product":
            continue
        if atom.item != last:
            print(f"\n==== {atom.item.title}")
            last = atom.item
        print(f"\n### {atom.attribute}: {' | '.join(atom.values)} {atom.unit or ''}")
        for maker in makers:
            if not table[i, maker]:
                print(f"  {maker:11} -- nothing found")
            for e in table[i, maker]:
                print(f"  {maker:11} {e.file} p{e.pdf_page:<3} [{e.product}] {e.stated}  \"{e.quote[:90]}\"")
                print(f"{'':16}-> {e.shape} {e.numbers} unit={e.unit} items={e.items} when={e.condition} limit={e.condition_limit}")
    print(f"\n{llm.summary()}, {time.time() - started:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
