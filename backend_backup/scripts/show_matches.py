"""Score every manufacturer against a tender's first item and show why.

Usage: python -m scripts.show_matches <tender.pdf> <category_dir>
"""
import sys

from app.services.llm_factory import make_llm
from app.services.match import Outcome, summarize
from app.services.ocr import reader_for
from app.services.pipeline import gather, score, score_by_product


def line(o: Outcome) -> str:
    page = f"p{o.evidence.pdf_page}" if o.evidence else "  "
    return f"{o.status:25} {o.score:3} {page:4} {'REVIEW ' if o.review else ''}{o.reason}"


def percentages(maker: str, outcomes: list[Outcome]) -> str:
    s = summarize(maker, outcomes)
    if s.compatibility is None:
        return "not assessed (no readable text)"
    return f"compatibility {s.compatibility:5.1f}%   coverage {s.coverage:5.1f}%   ({s.counted} requirements)"


def main(tender: str, category_dir: str) -> None:
    llm = make_llm()
    found = gather(llm, tender, category_dir, reader_for(llm))
    outcomes = score(found)
    for i, atom in enumerate(found.atoms):
        print(f"\n### {atom.attribute}: {' | '.join(atom.values)} {atom.unit or ''}")
        for o in outcomes[i * len(found.makers):(i + 1) * len(found.makers)]:
            print(f"  {o.manufacturer:11} {line(o)}")
    print("\n### overall, taking the best evidence for each requirement on its own")
    for maker in found.makers:
        print(f"  {maker:11} {percentages(maker, [o for o in outcomes if o.manufacturer == maker])}")
    print("\n### overall, scoring one product at a time (the best single product)")
    for maker, (product, product_outcomes) in score_by_product(llm, found).items():
        print(f"  {maker:11} {percentages(maker, product_outcomes)}   product: {product or 'none named'}")
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])