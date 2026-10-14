"""Score every manufacturer against every item of a tender and show why.

Usage: python -m scripts.show_matches <tender folder or pdf> <category_dir>
"""
import sys

from app.services.llm_factory import make_llm
from app.services.match import ItemSummary, Outcome, Summary, overall, summarize_items
from app.services.ocr import reader_for
from app.services.pipeline import gather, score, score_by_product


def line(o: Outcome) -> str:
    page = f"p{o.evidence.pdf_page}" if o.evidence else "  "
    return f"{o.status:25} {o.score:3} {page:4} {'REVIEW ' if o.review else ''}{o.reason}"


def percentages(s: Summary) -> str:
    if s.compatibility is None:
        return "not assessed (no readable text)"
    return f"compatibility {s.compatibility:5.1f}%   coverage {s.coverage:5.1f}%   ({s.counted} requirements)"


def title(item) -> str:
    return f"{item.title}  x{item.quantity if item.quantity is not None else '?'}"


def show_summaries(label: str, per_maker: dict[str, list[ItemSummary]], products: dict[str, dict[str, str | None]] | None = None) -> None:
    print(f"\n### {label}")
    for maker, per_item in per_maker.items():
        print(f"  {maker:11} overall {percentages(overall(maker, per_item))}")
        for s in per_item:
            product = f"   product: {products[maker][s.item.title] or 'none named'}" if products else ""
            print(f"      {title(s.item)[:60]:60} {percentages(s.summary)}{product}")


def main(tender: str, category_dir: str) -> None:
    llm = make_llm()
    found = gather(llm, tender, category_dir, reader_for(llm))
    for note in found.notes:
        print(f"NOTE: {note}")
    outcomes = score(found)
    last = None
    for i, atom in enumerate(found.atoms):
        if atom.item != last:
            print(f"\n==== {title(atom.item)}")
            last = atom.item
        print(f"\n### {atom.attribute}: {' | '.join(atom.values)} {atom.unit or ''}   [{atom.file} p{atom.pdf_page}]")
        for o in outcomes[i * len(found.makers):(i + 1) * len(found.makers)]:
            print(f"  {o.manufacturer:11} {line(o)}")
    show_summaries(
        "overall, taking the best evidence for each requirement on its own",
        {m: summarize_items(m, [o for o in outcomes if o.manufacturer == m]) for m in found.makers},
    )
    by_product = score_by_product(llm, found)
    show_summaries(
        "overall, scoring one product at a time (the best single product for each item)",
        {m: summarize_items(m, [o for _, _, outs in rows for o in outs]) for m, rows in by_product.items()},
        {m: {item.title: product for item, product, _ in rows} for m, rows in by_product.items()},
    )
    print(f"\n{llm.summary()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
