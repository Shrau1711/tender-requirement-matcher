"""Why did reading give no evidence where a person found something? Costs nothing: only answers already saved are used.

For each such requirement it says whether the model was shown the cited page, and whether it answered with nothing or with findings
that were then set aside (a quote that is not word for word in the passage, a statement about another type of product).

Usage: python -m scripts.why_no_evidence <tender folder or pdf> <category_dir> [output file]

The full list goes to the output file (UTF-8, because the pages hold characters a Windows console cannot print); the console gets the summary.
"""
import sys
from collections import Counter
from pathlib import Path

from app.services.corpus import load_chunks
from app.services.evidence import SYSTEM, Found, passages_prompt, question, rejected, retrieve, usable
from app.services.gold import GOLD_DIR, cited, load_gold
from app.services.llm import ask
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views
from app.services.search import Index

SNIPPET = 90
PAGE_SNIPPET = 280


class CacheOnly:
    """Answers only what is already saved, so this script can never spend anything."""

    def __init__(self, cache) -> None:
        self.cache = cache

    def generate(self, system: str, user: str):
        if not self.cache.has(system, user):
            raise LookupError("not in the cache")
        return self.cache.generate(system, user)


def main(tender: str, category_dir: str, out: str = "reports/why_no_evidence.txt") -> None:
    gold = load_gold(GOLD_DIR / f"{Path(tender).stem}.json")
    llm = make_llm()
    read_image = reader_for(llm)
    atoms, _ = read_atoms(llm, tender, read_image)
    index, views = Index(load_chunks(category_dir, read_image)), load_unit_views()
    lead: dict[tuple, object] = {}
    for a in atoms:
        lead.setdefault(question(a), a)  # a requirement that several items share was asked once, with the first item's wording
    reading, tally, lines = CacheOnly(llm), Counter(), []
    for a, key, maker, pages in cited(gold, atoms):
        req = lead[question(a)]
        hits = usable(req, retrieve(index, req, maker, views))
        shown = bool(pages & {h.chunk.pdf_page for h in hits})
        try:
            findings = ask(reading, SYSTEM, passages_prompt(req, hits), Found).findings if hits else []
        except LookupError:
            tally["answer not saved"] += 1
            continue
        reasons = [(f, rejected(f, hits)) for f in findings]
        if any(why is None for _, why in reasons):
            continue
        outcome = ("cited page shown, " if shown else "cited page not shown, ") + ("model answered with nothing" if not findings else "every finding set aside")
        tally[outcome] += 1
        lines.append(f"\n{key} / {maker}  (cited pages {sorted(pages)}, {len(hits)} passages shown)\n  {outcome}")
        for h in (h for h in hits if h.chunk.pdf_page in pages):
            lines.append(f"  shown from the cited page (p{h.chunk.pdf_page}, {h.chunk.kind}): {' '.join(h.chunk.text.split())[:PAGE_SNIPPET]}")
        for f, why in reasons:
            lines.append(f"  - p{hits[f.passage].chunk.pdf_page if 0 <= f.passage < len(hits) else '?'} {why}: {' '.join(f.quote.split())[:SNIPPET]}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for name, n in tally.most_common():
        print(f"  {n:3} {name}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
