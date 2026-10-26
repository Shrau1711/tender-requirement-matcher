"""Show a tender as a graph: its items, the requirement rows they share, and the standards it cites with their links.

Usage: python -m scripts.run.show_graph <tender folder> [mermaid output file]

Uses the saved reading of the tender (no model call) and the standards graph from scripts.run.build_graph.
"""
import sys
from pathlib import Path

from app.graph.standards import standards_graph
from app.graph.tender import build, items_of, shared_rows, unreachable
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for


def main(tender: str, mermaid: str | None = None) -> None:
    sys.stdout.reconfigure(errors="replace")  # a console that cannot show "≥" shows "?" instead of stopping
    llm = make_llm()
    atoms, _ = read_atoms(llm, tender, reader_for(llm))
    graph = build(Path(tender).name, atoms)
    kinds = [n.kind for n in graph.nodes.values()]
    print(f"{kinds.count('item')} items, {kinds.count('row')} requirement rows, {kinds.count('requirement')} atomic requirements")
    print(f"rows shared by several items: {len(shared_rows(graph))}; requirements not reachable from the tender: {len(unreachable(graph))}")
    for row in shared_rows(graph)[:10]:
        print(f"  {graph.nodes[row].label[:80]}  -> {', '.join(items_of(graph, row))}")
    standards = standards_graph()
    for node_id, node in graph.nodes.items():
        if node.kind == "standard":
            known = standards.nodes.get(node_id)
            together = standards.linked(node_id, "named_together")
            print(f"cites {node.label}: also written {', '.join(known.names) if known else '(not in the standards graph)'}"
                  + (f"; named together with {', '.join(sorted(together))}" if together else ""))
    if mermaid:
        Path(mermaid).write_text(f"```mermaid\n{graph.to_mermaid()}\n```\n", encoding="utf-8")
        print(f"wrote {mermaid}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
