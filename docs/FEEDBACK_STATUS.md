# Status of the reviewers' feedback

The nine points are from `docs/IMPROVEMENT_PLAN.md` (the verbatim feedback). Each is marked **done**, **partly done** or **not done**, judged strictly:
- a script is not a web tool;
- a setting nobody switches on is not a feature of the app;
- code that has never been run on real data is not proven.

Checked on branch `demo-space`, 4 November 2026, by reading the code and the measurements already recorded in `docs/CHANGES.md` and `docs/NEEDS_PAID_RUN.md`. No model calls were made for this review.

| # | Feedback | Status |
|---|---|---|
| 1 | Dynamic, modular chunking that suits the document, including flowcharts and hierarchies | partly done |
| 2 | Chunking, extraction, embedding and retrieval independently replaceable; at most 6 to 7 files a folder | partly done |
| 3 | `architecture.md` with components, data flow, design decisions and a Mermaid diagram | done |
| 4 | A proper vector database, not embeddings in a plain structured database | partly done |
| 5 | A new category with no code changes; a tender with two categories | done |
| 6 | A real token counter instead of characters / 4 | partly done |
| 7 | Temperature and model as settings; leave Gemini 3 temperature at its default | partly done |
| 8 | Make the model a setting and test a cheaper one | done |
| 9a | Extra: a tool to collect manufacturer documents from the web | partly done |
| 9b | Extra: a knowledge graph | partly done |
| 9c | Extra: OCR that works for more languages | not done |

Done: 3. Partly done: 7. Not done: 1.

## 1. Chunking: partly done

**What is there.**
- `backend/app/chunking/base.py`: the `Chunker` interface.
- `backend/app/chunking/strategies/`: five strategies, one file each, registered by name:
  - `table_rows`, the original;
  - `recursive`, fixed size with overlap;
  - `sections`, layout-based;
  - `parent_child`;
  - `structure`, numbered clauses and flowcharts, which follows the lines between boxes using `backend/app/reading/boxes.py`.
- `backend/app/chunking/router.py` picks a strategy from what a document looks like, with the reason.
- Compared with `eval_retrieval` and `eval_candidates` on the real catalogues, and on two invented documents, a clause specification and a flowchart, in `data/eval/samples/`. Tests are in `backend/tests/chunking/`.

**What is missing.**
- **The dynamic choice is off.** `CHUNKER` defaults to `table_rows`, and nothing in the app, `docker-compose.yml` or the demo sets it to `auto`. As shipped, every document is still chunked by the original table-row rule, which is exactly what the reviewers objected to. The router only runs if someone sets `CHUNKER=auto` by hand. It is kept off because any other strategy changes the questions, so the saved answers stop matching.
- **No semantic strategy.** The reviewers named fixed/recursive, structure/layout-aware, semantic and parent-child. There is no strategy that cuts where the meaning changes, for example by embedding similarity between sentences.
- **Tenders are not chunked.** Chunking applies only to manufacturer documents. A tender, the document the reviewers said "may also have a flowchart or hierarchical structure", is still read page by page by the model. The tender hierarchy exists only as a graph shown by a script (see 9b).
- **Not proven on final answers.** No strategy other than `table_rows` has been run end to end. On the free retrieval checks none was clearly better on the real catalogues. `structure` and `auto` only did clearly better on the invented documents, which were written for them.

## 2. Modularity: partly done

**What is there.**
- `backend/app/` is split into packages: reading, chunking, embedding, vectorstore, retrieval, extraction, judging, llm, categories, cost, graph, collecting, reporting, pipeline, api and others.
- Every folder holds at most 7 files, except `frontend/`, whose 8 files are root config files: `package.json`, `vite.config.js`, the Dockerfile and similar.
- Chunking can be swapped with the `CHUNKER` setting, and the vector store with `VECTOR_STORE`. Both have an interface: `Chunker` in `backend/app/chunking/base.py` and `VectorStore` in `backend/app/vectorstore/base.py`.
- The model is behind the `LLM` interface in `backend/app/llm/llm.py`, and `LLM_MODEL` chooses which Gemini model.

**What is missing.**
- **Embedding cannot be swapped by a setting.** `backend/app/embedding/embedder.py` names one model in the code (`MODEL_NAME = "BAAI/bge-small-en-v1.5"`) and there is no interface or setting. It can only be replaced in code, by passing another function as `embed`. A new model would also make the shipped `data/seed_embeddings.sqlite` useless.
- **Extraction is Gemini only.** `make_llm()` in `backend/app/llm/llm_factory.py` always builds `GeminiLLM`. The `LLM` interface would allow another provider, but there is none and no setting to choose one.
- **Retrieval has no interface.** `Index` in `backend/app/retrieval/search.py` is the only search, with BM25 plus meaning plus RRF fixed. Keyword-only or meaning-only search is available to the eval scripts, not to the app.

## 3. `architecture.md`: done

**What is there.** `docs/architecture.md`:
- an overview diagram and a table of every package (the components);
- Mermaid diagrams of the ingest path and the query path (the data flow);
- a long "Design decisions and their trade-offs" section.

All three diagrams were checked with Mermaid's own parser, and it describes the current defaults (Chroma; the graph off).

**What is missing.** Nothing the feedback asked for. It does not describe the replay-only demo (`backend/app/demo.py`, `Dockerfile.demo`), which exists only on `demo-space`.

## 4. Vector storage: partly done

**What is there.**
- `backend/app/vectorstore/chroma.py`: Chroma, kept on disk, with filters on category, manufacturer, file and page. It is the default (`VECTOR_STORE=chroma`) and is what the app uses.
- `backend/app/vectorstore/memory.py`: the old in-memory store, kept for comparison.
- `backend/app/vectorstore/ingest.py`: each file is embedded once and skipped while its content hash and settings are unchanged.
- Checked: all 1,273 of 1,273 questions the pipeline would ask come out identical with Chroma and with memory.

**What is missing.**
- **Embeddings are still kept in plain SQLite tables.** `backend/app/embedding/embed_cache.py` stores every vector, for chunks and for queries, as a blob in `backend/.cache/embeddings.sqlite`. The shipped `data/seed_embeddings.sqlite` (13 MB) is the same kind of table. Chroma is filled from this cache. This is what the reviewers said not to do. It is kept so that vectors are the same on every machine and the saved questions keep matching.
- **Chroma does not do the search.** It stores and filters, then `Index.meanings` in `backend/app/retrieval/search.py` scores every candidate with NumPy. The candidates are all of a manufacturer's chunks, so Chroma's nearest-neighbour index saves no work. This was done to keep results identical to the last digit, and it is stated in `docs/architecture.md`, but Chroma is used as storage with filters, not as a search engine.

## 5. New categories and mixed tenders: done

**What is there.**
- **A category is a folder** under `data/categories/<name>/`, holding the manufacturers' PDFs and a `category.json` with its product words, type attributes, filler words and extraction rules. No code names a category (`backend/app/categories/config.py`). The tender-reading prompt is built centrally from the shared rules plus every category's rules (`backend/app/extraction/atomize.py`).
- **The category is optional on upload.** The web page defaults to "Find it in the tender".
- **Routing.** Each tender item is sent to a category by product words, or else by which category's documents it resembles most, with no model call (`backend/app/categories/routing.py`).
- **Mixed tenders.** A tender with two categories becomes one run per category, each with its own copy of the tender (`execute_routed` in `backend/app/pipeline/runner.py`). The runs appear side by side in the runs list.
- **Measured:** all 11 labelled items from 7 tenders went to the recorded category.

**What is missing.**
- **Never run on a real mixed tender.** None of the tenders collected has both pumps and valves. The split into several runs is tested only with a fake router (`backend/tests/api/test_api.py`).
- **No real third category.** Adding one has only been tested with temporary folders in `backend/tests/categories/test_categories.py`; no real third category with real documents exists.
- **Rules affect every tender.** Adding extraction rules to any category changes the prompt for every tender, so every saved answer stops matching and every tender costs money again. That is stated in the README, but it means "no code changes" is not "no cost".

## 6. Token counter: partly done

**What is there.**
- `backend/app/cost/tokens.py`: `TOKEN_COUNTER=gemini` uses Gemini's own `count_tokens`. Each text is counted once, it obeys `LLM_MAX_CALLS`, and it falls back to the estimate on any error. It is tested with a fake counter in `backend/tests/cost/test_tokens.py`.
- `scripts.cost.estimate_cost` prints the exact figure when it has one.

**What is missing.**
- **The app still uses characters / 4.** `TOKEN_COUNTER` defaults to `estimate`, and nothing sets it to `gemini`, so every budget and every estimate shown on the web page is still characters / 4.
- **That estimate is known to be low.** Measured on the saved answers, it is 74% of the real input tokens on 9933225 and 69% on 9935891 (`docs/NEEDS_PAID_RUN.md`, row 10). The correction factors (1.36 for valves, 1.45 for pumps) were used only to price the checks in that file. They are not in the code, so the app's own estimate is still about a quarter to a third short.
- **The Gemini counter has never been run.** It has never been called against the real API. In this project's budget it counts as a call, so it was never allowed under `LLM_MAX_CALLS=0`.

## 7. Temperature and model settings: partly done

**What is there.**
- **Settings.** `LLM_TEMPERATURE` (a number, or `DEFAULT` for the model's own 1.0), `LLM_MODEL` and `LLM_THINKING`, in `backend/app/llm/gemini.py` (`temperature_setting`, `model_and_level`). Each value other than the default is added to the cache key. Tests are in `backend/tests/llm/test_gemini_settings.py`.
- **Guidance checked.** Google's current Gemini 3 page was read, and the code comment quotes its advice to keep the default 1.0.
- **Measured once, paid step 2, about ₹40.54, on 9933225.** Temperature 1.0 showed no looping, but 29 of 35 statuses agreed against 31 of 35 at 0.

**What is missing.** The shipped default is still temperature 0, which is the setting the reviewers flagged as against Google's advice. The reason is recorded: every saved answer was made at 0, and on the one tender measured, 1.0 was not better. It rests on one small tender (11 requirements); the larger one (check 4 below) has not been run.

## 8. A lighter model: done

**What is there.**
- `LLM_MODEL` chooses the model, and every model has its own cache keys.
- **Paid step 1:** `gemini-3.5-flash-lite` on 9933225, about ₹17.87 for the run (₹19.24 including the smoke test and the first attempt).
- **Result:** about 43% of the current model's cost for that tender. Scored by tender row, 28 of 35 statuses and 19 of 21 pages agree, against 31 of 35 and 23 of 23 for the current model.
- **Recorded in** `docs/NEEDS_PAID_RUN.md` and `docs/CHANGES.md`.

**What is missing.** It was tested on one small tender only. The pump tender (check 3) has not been run, so the default stays `gemini-3.8-flash` and no cost saving has been taken.

## 9a. Collecting manufacturer documents: partly done

**What is there.**
- `backend/app/collecting/crawl.py` follows links on a manufacturer's site to a set depth, obeying `robots.txt`.
- `backend/app/collecting/download.py` saves PDFs politely, each content once.
- `backend/app/collecting/sources.py` records where each file came from.
- Run from the command line with `backend/scripts/run/crawl_catalogues.py`.
- A test checks that all 27 shipped documents have a recorded source.

**What is missing.**
- **It is a script, not a web tool.** Nothing in the API (`backend/app/api/`) or the web page uses `app/collecting`. A user of the app cannot collect documents.
- **No shipped document came from it.** All 27 shipped documents are recorded by hand in `data/categories/sources.csv`. No `crawl_sources.csv` exists in the repository.

## 9b. Knowledge graph: partly done

**What is there.**
- `backend/app/graph/`:
  - `graph.py`: a small graph saved as JSON and drawable as Mermaid;
  - `standards.py`: equivalent standards, with "same document under another name" kept apart from "named together";
  - `tender.py`: tender → items → rows → requirements.
- Built by `backend/scripts/run/build_graph.py` into `data/graph/standards.json`: 246 standards, 21 with several names, 24 pairs named together.
- Shown by `backend/scripts/run/show_graph.py`. Tests are in `backend/tests/graph/`.

**What is missing.**
- **Off in the app.** Judging uses the standards graph only with `KNOWLEDGE_GRAPH=on`. The default is `off`, and nothing switches it on.
- **No effect yet.** On the two labelled tenders, switching it on changed 0 outcomes. It has never changed a result anywhere.
- **The tender hierarchy is used only by a script.** It is not in the API, the report or the web page.
- **Product → family → attribute links, which the reviewers named, do not exist.**

## 9c. OCR for more languages: not done

**What is there.** Pages without a text layer are read by the model from a picture of the page (`backend/app/reading/ocr.py`). `backend/app/reading/ocr_compare.py` and `backend/scripts/eval/compare_ocr.py` compare one reading with another.

**What is missing.** Everything the point asked for:
- no language setting;
- no OCR engine with language packs;
- no non-English test document;
- no measurement.

The transcription prompt, the vocabulary in `backend/config/` and the word matching in `ocr_compare.py` (`[a-z]{3,}`) all assume English. A model may read other scripts, but nothing in the repository shows or checks that.

## What would need a paid run

Costs are the estimates already recorded in `docs/NEEDS_PAID_RUN.md`, at the app's rate (`RUPEES_PER_MILLION_TOKENS` = 100) and Google's prices as listed there:
- **Whole runs** (new model or temperature) are priced from the tokens the same run really used.
- **Partial runs** (another chunker, the graph) are priced from the estimate, scaled by 1.36 for valves and 1.45 for pumps.

These are expected costs, not limits. Google doubles Gemini 3.8 Flash's price on 1 January 2027, which doubles every cost below that uses the current model (all but check 3).

| # | Check | Feedback point | Tender | New calls | Estimated cost |
|---|---|---|---|---|---|
| 3 | Lighter model on the larger tender | 8 | 9935891 (pumps) | 214 | ≈ ₹73 (3.5 Flash-Lite), ≈ ₹56 (3.1 Flash-Lite) |
| 4 | Temperature 1.0 on the larger tender | 7 | 9935891 | 214 | ≈ ₹163 |
| 5 | Chunker `structure` (`auto` picks the same here) | 1 | 9933225 (valves) | 41 | ≈ ₹27 (`auto` ≈ ₹28) |
| 6 | Chunkers `recursive`, `sections`, `parent_child` | 1 | 9933225 | 55 to 56 each | ≈ ₹45, ₹34, ₹40 |
| 7 | Chunker `structure` | 1 | 9935891 | 141 | ≈ ₹111 |
| 8 | Chunkers `recursive`, `sections`, `parent_child` | 1 | 9935891 | 203 to 204 each | ≈ ₹162, ₹130, ₹161 |
| 9 | Standards graph on a tender that cites linked standards | 9b | 9840129 (no answer key) | 123 | ≈ ₹88 |

The numbers are those in `docs/NEEDS_PAID_RUN.md`. Checks 1 and 2 there were run (≈ ₹19.24 and ≈ ₹40.54, ≈ ₹59.78 in all), and check 10 was answered for free.

**Cheapest checks that would move a point forward.** Check 5 (≈ ₹27) is the only evidence that could justify turning the router on (point 1). Check 3 (≈ ₹73 or ₹56) is the next evidence on the cheaper model (point 8).

**Not priced, because the work does not exist yet:**
- **A semantic chunker (point 1).** It would need building first, then a run like check 6, about ₹35 to ₹45 on 9933225 if it changes most passages, as those strategies did.
- **Exact token counts (point 6).** These are requests to Google, not answers from the model. The pricing in `docs/NEEDS_PAID_RUN.md` does not list them, and nothing here was checked against Google's billing, so confirm the price before running one. It needs `LLM_MAX_CALLS` above 0.
- **OCR in other languages (point 9c).** There is no test document, so the number of pages, and so the cost, is unknown.

## Notes found while checking

- **Stale opening line.** `docs/NEEDS_PAID_RUN.md` still opens with "Nothing here has been run", but checks 1 and 2 were run and are reported further down the same file.
- **Branch.** This file is on `demo-space` only, not on `v3-improvements` (PR #1).
