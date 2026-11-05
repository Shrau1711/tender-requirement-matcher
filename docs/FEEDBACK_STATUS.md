# Status of the reviewers' feedback

The nine points are from `docs/IMPROVEMENT_PLAN.md` (the verbatim feedback). Each is marked **done**, **partly done** or **not done**, judged strictly:
- a script is not a web tool;
- a setting nobody switches on is not a feature of the app;
- code that has never been run on real data is not proven.

Checked on branch `demo-space`, 4 November 2026, by reading the code and the measurements already recorded in `docs/CHANGES.md` and `docs/NEEDS_PAID_RUN.md`. No model calls were made for this review.

*Updated after the next batch ("Embedder and retriever behind interfaces, and a semantic chunker" in `docs/CHANGES.md`): points 1 and 2 changed; their status did not.*

*Updated again after "Add documents in the web app, and OCR in more languages": point 9a is now done and point 9c partly done. Point 2 lists the new page-reader setting.*

*Updated after "Product families and the tender layout in the app": point 9b changed and is still partly done. Point 6 records that `countTokens` is not documented as free for the Gemini Developer API.*

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
| 9a | Extra: a tool to collect manufacturer documents from the web | done |
| 9b | Extra: a knowledge graph | partly done |
| 9c | Extra: OCR that works for more languages | partly done |

Done: 4. Partly done: 7. Not done: 0.

## 1. Chunking: partly done

**What is there.**
- `backend/app/chunking/base.py`: the `Chunker` interface.
- `backend/app/chunking/strategies/`: six strategies, one file each, registered by name:
  - `table_rows`, the original;
  - `recursive`, fixed size with overlap;
  - `sections`, layout-based;
  - `parent_child`;
  - `structure`, numbered clauses and flowcharts, which follows the lines between boxes using `backend/app/reading/boxes.py`;
  - `semantic`, which cuts where neighbouring text blocks stop being alike, judged with the embeddings (`semantic.py`).
- `backend/app/chunking/router.py` picks a strategy from what a document looks like, with the reason.
- Compared with `eval_retrieval` and `eval_candidates` on the real catalogues, and on two invented documents, a clause specification and a flowchart, in `data/eval/samples/`. Tests are in `backend/tests/chunking/`.

**What is missing.**
- **The dynamic choice is off.** `CHUNKER` defaults to `table_rows`, and nothing in the app, `docker-compose.yml` or the demo sets it to `auto`. As shipped, every document is still chunked by the original table-row rule, which is exactly what the reviewers objected to. The router only runs if someone sets `CHUNKER=auto` by hand. It is kept off because any other strategy changes the questions, so the saved answers stop matching.
- **Semantic chunking is there but unproven.** `semantic` now exists. On the 7 valve retrieval cases it put a right page first most often (6 of 7, hybrid, against 4 of 7 for the default), but its chunks are tiny (a median of 42 characters against 329), and it has not been run end to end (check 11, ≈ ₹33). It is not the default and the router never picks it.
- **Tenders are not chunked.** Chunking applies only to manufacturer documents. A tender, the document the reviewers said "may also have a flowchart or hierarchical structure", is still read page by page by the model. The tender hierarchy exists only as a graph shown by a script (see 9b).
- **Not proven on final answers.** No strategy other than `table_rows` has been run end to end. On the free retrieval checks none was clearly better on the real catalogues. `structure` and `auto` only did clearly better on the invented documents, which were written for them.

## 2. Modularity: partly done

**What is there.**
- `backend/app/` is split into packages: reading, chunking, embedding, vectorstore, retrieval, extraction, judging, llm, categories, cost, graph, collecting, reporting, pipeline, api and others.
- Every folder holds at most 7 files, except `frontend/`, whose 8 files are root config files: `package.json`, `vite.config.js`, the Dockerfile and similar.
- Chunking (`CHUNKER`), embedding (`EMBEDDER`), the vector store (`VECTOR_STORE`) and retrieval (`RETRIEVER`) can each be swapped by a setting, behind an interface with implementations listed by name: `Embedder` in `backend/app/embedding/base.py`, `Retriever` in `backend/app/retrieval/base.py`, and `Chunker` in `backend/app/chunking/base.py` and `VectorStore` in `backend/app/vectorstore/base.py`.
- The model is behind the `LLM` interface in `backend/app/llm/llm.py`, and `LLM_MODEL` chooses which Gemini model.
- The page reader for scanned pages (`OCR`) is chosen the same way, from a list of readers by name in `backend/app/reading/ocr/readers.py`.

**What is missing.**
- **Only one embedder exists.** `EMBEDDER` has one choice, `bge-small`. A second is a class and one line in `EMBEDDERS`, and gets its own saved vectors and Chroma folder, but none is listed, so the setting has nothing to switch to. A new model would also make the shipped `data/seed_embeddings.sqlite` useless and every question new.
- **Extraction is Gemini only.** `make_llm()` in `backend/app/llm/llm_factory.py` always builds `GeminiLLM`. The `LLM` interface would allow another provider, but there is none and no setting to choose one.
- **The other retrievers are the same search.** `RETRIEVER` offers `hybrid` (the default), `keyword` and `meaning`, but all three are the one `Index` with a fixed mode. No retriever of another kind (for example re-ranking) exists, and neither alternative has been checked against final answers.

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
- **Not documented as free for this API, checked 5 November 2026.** Google's pages for the Gemini Developer API (the one this app uses, with an API key) do not say that `countTokens` is free:
  - the token-counting page (`aistudio.google.com/docs/tokens`) says only "When billing is enabled, the cost of a call to the Gemini API is determined in part by the number of input and output tokens";
  - the billing page (`aistudio.google.com/docs/billing`) says "Requests to the `GetTokens` API are not billed, and they don't count against inference quota", but it does not say that this is `countTokens`;
  - only the Vertex AI documentation, a different product, says "There is no charge or quota restriction for using the `CountTokens` API".

  So, as the owner asked, it was not wired further or tested, and the default stays characters / 4.

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

## 9a. Collecting manufacturer documents: done

**What is there.**
- **A web page, Add documents** (`frontend/src/pages/DocumentsPage.jsx`), and its route, `POST /categories/{category}/documents` (`backend/app/api/documents.py`):
  - choose the category and the manufacturer, or type a new one;
  - upload a PDF, with an optional web address it came from, or give the address of a PDF.
- **The collector's own code does the work** (`backend/app/collecting/add.py`):
  - a download goes through the crawler's polite fetcher, which obeys `robots.txt` and pauses between requests;
  - the file is saved with `save_pdf`, so the same content is never saved twice, even under another name;
  - a line with the source and date goes into `data/categories/sources.csv`.
- **It is made searchable by the one ingest function.** `add_to_search` in `backend/app/pipeline/runner.py` calls `ingest` with the page reader a run uses, so the next run finds the document already stored.
- **The page answers** with the file, the date and how many passages are now searchable. A file that saved but could not be read says so, and the next run tries again.
- **The replay-only demo refuses it** with its plain message.
- **Tests:**
  - 11 collector tests (`backend/tests/collecting/test_add.py`), including a search that finds the added document;
  - 10 API tests (`backend/tests/api/test_add_documents.py`), plus 1 demo test;
  - 5 frontend tests (`frontend/src/documents.test.jsx`).
- **Run on real data, free:**
  - Intervalve's portfolio was downloaded through the route from the address recorded in `sources.csv`. It arrived byte for byte identical to the shipped copy, was recorded, and gave 20 searchable passages. Its pages that are only a picture were read from the shipped saved transcriptions (the scratch cache started empty), so no model call was made.
  - A text PDF uploaded through the route was found by a search. A scanned Hindi page uploaded with `OCR=easyocr` was read and stored without a key or a model call.
- The command-line crawler (`backend/app/collecting/crawl.py`, `backend/scripts/run/crawl_catalogues.py`) is unchanged.

**What is missing.**
- **The page takes one PDF, not a site.** Following a manufacturer's links to find its catalogues is still only the command-line crawler.
- **Adding waits while the document is read.** A long catalogue can take minutes. A scanned one read by the default page reader, the model, is a paid call per picture page, and the page only warns about this in words; it shows no estimate first.
- **No shipped document came through it.** All 27 shipped documents were still recorded by hand.

## 9b. Knowledge graph: partly done

**What is there.**
- `backend/app/graph/`:
  - `graph.py`: a small graph saved as JSON and drawable as Mermaid;
  - `standards.py`: equivalent standards, with "same document under another name" kept apart from "named together";
  - `tender.py`: tender → items → rows → requirements;
  - `products.py`: product → family → attribute, from each category's `category.json` (new `attributes` and `families` fields);
  - `layout.py`: the tender's layout for the web page.
- **The standards graph** is built by `backend/scripts/run/build_graph.py` into `data/graph/standards.json`: 246 standards, 21 with several names, 24 pairs named together.
- **Product → family → attribute links.**
  - Valves: 5 families (butterfly, gate, globe, check, ball). Pumps: 5 (submersible, horizontal centrifugal, vertical multistage, end suction, process).
  - The families are the product ranges of the shipped catalogues.
  - The attributes are names the saved tender readings use: 9 shared by all valves and 18 by all pumps, plus each family's own where a saved tender shows them.
  - An item's family is found from a word in its title, or in its type value.
- **The tender hierarchy is in the app.** The report has a Tender layout tab (`frontend/src/components/report/TenderLayout.jsx`), served by `GET /runs/{id}/layout`. For each item it shows:
  - its family, and how the family was found;
  - its printed rows, with links to the tender page, and which other items share each row;
  - the requirements each row splits into, and the standards cited, with their other names and the standards named with them;
  - the attributes `category.json` lists that the reading does not name.
- **It is built from the saved reading only,** through a stand-in for Gemini with the same cache keys, no key and a call limit of 0. A tender whose reading is not saved gets a plain refusal.
- **Checked free:** all 5 demo samples show their layout using only the shipped saved answers, with an empty local cache. The family found: ball, submersible (both items), gate, vertical multistage (from the type value, both items), butterfly. Tender 9840129's four items are all gate valves: one named in its title, three ("VALVE MOTORISE …") by their type value.
- **Tests:** `backend/tests/graph/test_products.py` (6), `test_tender_layout.py` (4), one API test, and 3 frontend tests.

**What is missing.**
- **Off for judging.** Judging uses the standards graph only with `KNOWLEDGE_GRAPH=on`. The default is `off`, and nothing switches it on.
- **No effect yet.** On the two labelled tenders, switching it on changed 0 outcomes. It has never changed a result anywhere.
- **The product links only inform.** No score uses a family or its attributes.
- **"Not named" compares names exactly.** The model names attributes freely, so on 9933225 it lists `pressure_rating` although the tender asks `nominal_pressure`. It is a prompt for a person to look, not a finding.
- **Family attributes are thin.** Globe and check valves, and three pump families, come from catalogues only. No saved tender has an item of those families, so they have no attributes of their own.
- **Tenders without a saved reading cannot be shown:** 9918524 and 9995708 among the collected ones.

## 9c. OCR for more languages: partly done

**What is there.**
- **The page reader is a setting.** `OCR` chooses what reads pages that are only a picture, and `OCR_LANGS` the languages on them (`backend/app/reading/ocr/readers.py`, with a list of readers by name, like the other parts).
  - `model` is the default and unchanged: Gemini transcribes the page. With `OCR_LANGS` other than `en`, one sentence asks it to expect those languages; with `en` its prompt is byte for byte the same, so every saved transcription still matches.
  - `easyocr` runs EasyOCR on this computer (`backend/app/reading/ocr/local.py`). It reads English, Hindi and Marathi, is free and needs no key, and writes Devanagari digits as 0 to 9.
- **Tested on pictures made in the test** (`backend/tests/ocr/test_ocr_languages.py`): a line each of Hindi, Marathi and English, and a scanned page with all three, are read word for word. `backend/tests/ocr/test_ocr_readers.py` checks the default prompt, the settings and the store key.
- **Measured free on real pages.** Tender 9918524 includes a BHEL specification whose 6 scanned pages mix Hindi and English. The model's saved transcriptions of those pages were the reference:
  - with `OCR_LANGS=en,hi`, EasyOCR found 25 of the 89 Hindi words the model wrote (28%) and 148 of 254 numbers (58%);
  - with `en` alone, it found no Hindi words and 167 of 254 numbers (66%);
  - English words: about 76% either way.

  So on real scans EasyOCR misses most of the Hindi, and asking for Hindi costs numbers. The model's reading is the reference here, not a checked truth.

**What is missing.**
- **It is not used.** `OCR` defaults to `model`, and nothing switches on `easyocr`. EasyOCR is not in `requirements.txt` or the Docker images, because it brings PyTorch (about 1 GB).
- **Not good enough on real pages yet** (the numbers above): it reads the generated pictures perfectly and real scans poorly.
- **The rest of the pipeline is English.** The vocabulary in `backend/config/`, the units, the tender-reading prompts and the word matching in `compare.py` (`[a-z]{3,}`) assume English. Text read in Hindi or Marathi is stored, but keyword search drops Devanagari words (`TOKEN` in `backend/app/retrieval/search.py` keeps Latin letters and digits only), the embedder (`bge-small-en`) is an English model, and nothing judges Hindi text.
- **No real Marathi page, and no document that is mainly Hindi,** is in the repository.
- **The language hint is not used.** Paid check 12 (run, ≈ ₹1.19) found that with `OCR_LANGS=en,hi` the model wrote the Hindi on the 6 real pages much more fully, and closer to the print on 4 of them. But `OCR_LANGS` stays `en`, so the app still uses the readings made without the hint. The Hindi there is form labels, not requirements (`docs/NEEDS_PAID_RUN.md`).

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
| 11 | Chunker `semantic` | 1 | 9933225 (valves) | 56 | ≈ ₹33 (free estimate 219,527 input tokens × 1.36, plus output) |
| 12 | The model told to expect Hindi, on the real bilingual scans | 9c | 9918524 (6 pages) | 6 | **run 4 November 2026: ≈ ₹1.19** (estimated ≈ ₹1.13) |
| 13 | EasyOCR as the page reader, end to end | 9c | 9933225 | not priced | not priced: the free estimate was stopped when the computer ran low on memory |

The numbers are those in `docs/NEEDS_PAID_RUN.md`. Checks 1 and 2 there were run (≈ ₹19.24 and ≈ ₹40.54, ≈ ₹59.78 in all), check 12 was run (≈ ₹1.19), and check 10 was answered for free.

**Cheapest checks that would move a point forward.** Check 5 (≈ ₹27) is the only evidence that could justify turning the router on, and check 11 (≈ ₹33) the only evidence for the semantic chunker (point 1). Check 3 (≈ ₹73 or ₹56) is the next evidence on the cheaper model (point 8).

**Not priced, because the work does not exist yet:**
- **Exact token counts (point 6).** These are requests to Google, not answers from the model. Google's documentation for the Gemini Developer API does not say they are free (see point 6), so confirm with Google before running one. It needs `LLM_MAX_CALLS` above 0.
- **OCR on a real Marathi document or a mainly Hindi one (point 9c).** None is in the repository, so the number of pages, and so the cost, is unknown.

## Notes found while checking

- **Stale opening line, fixed.** `docs/NEEDS_PAID_RUN.md` opened with "Nothing here has been run", although checks 1 and 2 were run. It now says which checks were run.
- **Branch.** This file is on `demo-space` only, not on `v3-improvements` (PR #1).
