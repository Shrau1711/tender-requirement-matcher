# Improvement plan: tender-matcher v3

Read this whole file before doing anything. It is the full brief.

## Context
The tender-matcher (FastAPI backend, React frontend) was submitted for the Parallel Minds / Datasmith AI intern assignment. The reviewers said it works but is too hardcoded and not modular enough. The owner (Shravani) now has about two months to improve it, and it will go on her resume. She must be able to explain and defend every part in an interview, so clarity beats cleverness.

The submitted version must stay intact. Work on a new branch called `v3-improvements`. Never touch `main`, never force-push.

## Reviewer feedback (verbatim points)
1. Chunking is manually designed around table structure. It should be dynamic and modular, applying the appropriate strategy for the document (fixed/recursive, structure/layout-aware, semantic, parent-child). A tender may also have a flowchart or hierarchical structure, not only tables.
2. Modularity: chunking, extraction, embedding and retrieval must be independently replaceable. No more than 6 to 7 files in one folder.
3. Add `architecture.md`: architecture, components, data flow, design decisions, and a Mermaid flow diagram.
4. Vector storage: do not keep embeddings in a plain structured database. Use a proper vector database or vector storage approach, structured properly.
5. A new product category should work with a centralized extractor (no code changes). A tender can contain two categories (for example pumps and valves), so selecting one category on upload is not enough.
6. Use a token counter for the budget estimate (currently characters / 4). Gemini's own count_tokens is the accurate option; tiktoken is only approximate for Gemini.
7. Temperature is hardcoded to 0 in `gemini.py`. Make temperature (and model) settings. Google's guidance for Gemini 3 models is to leave temperature at its default, because lower values can cause looping. Verify in the current docs.
8. A lighter model could cut cost. Make the model a setting and test a cheaper one.
9. Optional extras: tool to collect manufacturer documents from the web, a knowledge graph (for equivalent standards, product to family to attribute links, tender hierarchy), and an OCR path that works for more languages.

## Hard rules (never break these)
- NEVER run anything that spends money. Always set `LLM_MAX_CALLS=0` in every shell before running tests or the app. Never pass `--go`, never run a paid tender, never remove the call cap. If something would need a real model call, stop and write it down in `docs/NEEDS_PAID_RUN.md` instead.
- Cached model answers are keyed on the exact prompt text and settings. The default behaviour must reproduce today's chunks, passages, order and settings exactly, so the shipped demo cache keeps working. New strategies, a new temperature or a new model are OPTIONS that default to the current behaviour.
- Run the full test suite after every phase. All tests must pass before moving on. Compare `eval_retrieval` before and after every retrieval change and record the numbers.
- One commit per phase, with a clear message. Do not push unless asked.
- Code style: small files, small reusable functions, shared logic in one place, no leftover unused code, no more than 7 files in any folder. Plain names. Short comments that explain why.
- After each phase, add a short section to `docs/CHANGES.md` in plain language: what changed, why, how to explain it in an interview in three sentences, and which files to read.
- Do not invent accuracy numbers. Only report what was measured.

## Phases
1. **Restructure.** Split `app/services` into packages: reading (PDF and OCR), chunking, embedding, vectorstore, retrieval, extraction (model calls), judging (measure, compare, match), and the API. At most 7 files per folder. Behaviour must not change. Update imports and tests.
2. **Chunking strategies.** Define a `Chunker` interface and a small registry. The current table-row logic becomes one strategy and stays the default. Add: recursive/fixed-size with overlap, section/layout-based, parent-child (small chunks for search, parent text for the model), and a structure-following strategy for hierarchical or flowchart-like tenders. Add a router that picks a strategy from what the document looks like, overridable by config. Compare strategies with `eval_retrieval`.
3. **Vector store.** Define a `VectorStore` interface. Implement it with Chroma (persistent, metadata filters on manufacturer, category, file, page). Embed once at ingest, query many times. Keep BM25 and the rank fusion for hybrid search. Keep the old in-memory index as a second implementation so the two can be compared.
4. **Categories and extraction.** Make the category optional on upload. Route each tender item to a category automatically (using product names and the categories' own documents), so a mixed tender works. Drive extraction rules from per-category config files so a new category is a new folder plus a config file.
5. **Smaller items.** `architecture.md` with Mermaid (overview, data flow, and the ingest and query paths). Token counting through Gemini's count_tokens with the old estimate as a fallback. Temperature and model as environment settings with the current values as defaults. A script to collect manufacturer documents from given URLs, recording the source of each. Update the README.
6. **Stretch.** A small knowledge graph for equivalent standards and tender hierarchy. Only if the earlier phases are solid.
7. **Re-measure.** List exactly which end-to-end checks need paid runs in `docs/NEEDS_PAID_RUN.md`, with the estimated cost of each, and let the owner decide.

## Definition of done for each phase
Tests pass, `eval_retrieval` numbers recorded, `docs/CHANGES.md` updated, one commit made, and a three-line summary given to the owner.
