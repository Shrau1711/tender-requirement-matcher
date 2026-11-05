# Changes in v3

One section per phase of `docs/IMPROVEMENT_PLAN.md`.

## Phase 1: Restructure

**What changed.** The 51 modules that were all in `backend/app/services` now live in 14 packages under `backend/app`, one per job:

| Package | What it does |
|---|---|
| `reading` | PDF pages: text, layout, tables, pictures read by a page reader |
| `tender` | what a tender asks for: its files, item headings and tables, bid details (`tender.py` became `items.py`, `tender_files.py` became `files.py`, `tender_reader.py` became `reader.py`) |
| `chunking` | cutting manufacturer documents into searchable passages |
| `embedding` | passages to vectors, cached on disk |
| `retrieval` | keyword, meaning and hybrid search |
| `vocabulary` | words, abbreviations, attribute roles |
| `extraction` | model calls that turn text into structured data |
| `judging` | plain-code scoring: units, comparisons, the match |
| `llm` | the model interface, Gemini, the answer cache, retries, parallel calls |
| `cost` | estimate, budget, approval |
| `reporting` | the report and its Markdown/Excel forms, audit, coverage |
| `evaluation` | answer keys and scoring against them |
| `collecting` | finding and downloading manufacturer documents |
| `pipeline` | the whole job for one tender |

The tests mirror these packages (`backend/tests/<package>/`). The scripts are grouped by purpose (`eval`, `gold`, `cost`, `run`, `show_reading`, `show_results`, `diagnose`), so a command such as `python -m scripts.eval_retrieval` is now `python -m scripts.eval.eval_retrieval`. No folder holds more than 7 files.

The frontend components are grouped the same way: `components/common` (pieces used on many pages), `components/shell` (the frame around every page), `components/report` (the report tabs) and `components/review` (where a person checks answers). The root config files stay where they are.

Two leftovers were deleted: 15 debug dumps in `backend/` (`matches_*.txt`, `blocks_*.txt` and the like, output of the `show_*` scripts that nothing reads) and `backend_backup/`, an old copy of the backend. Both remain in git history, and `main` keeps the submitted version.

Two small test changes came with the move:
- Five helpers used by tests in more than one folder (`run`, `ALIASES`, `SIZE`, `BIG`, `picture_only_pdf`) moved into `tests/builders.py`. Before, tests imported them from each other, which only worked while every test sat in one folder.
- Tests that wrap a fake model in the real answer cache now set their own call limit (`CALLS` in `tests/builders.py`). Before, they read `LLM_MAX_CALLS` from the shell, so 13 of them failed whenever the safety cap was set to 0. The cap itself is unchanged.

**Why.** Reviewers said the code was not modular enough and that one folder held too much. Each stage of the pipeline is now a package that can be read, tested and replaced on its own.

**Behaviour did not change.** Only import lines, package docstrings and script usage lines changed in the code. Checked by:
- the backend test suite, 330 passed with `LLM_MAX_CALLS=0` (13 of these failed before the call-limit fix above, for that reason only). That is 328 tests from `main` plus 2 added to `test_ocr_compare.py` just before this phase;
- the frontend test suite, 73 passed, and `vite build` succeeds;
- `docker compose build` builds both images, and the backend image imports every module and creates the app;
- a fingerprint of every chunk and every ranked search result (top 10, all retrieval cases, all three modes, both categories), identical before and after;
- `eval_retrieval` on valves (the cases only cover valves), found in top 5:

| | keyword | meaning | hybrid |
|---|---|---|---|
| before | 6/7 | 4/7 | 6/7 |
| after | 6/7 | 4/7 | 6/7 |

Prompt text did not change, so the cached model answers and the shipped demo cache still match.

**In an interview.** "The first version had one services folder with fifty files, so the stages of the pipeline were mixed together. I split it into packages that follow the data: reading, chunking, embedding, retrieval, extraction, judging, reporting. That made each stage replaceable, and I proved the move changed nothing by fingerprinting every chunk and search result before and after."

**Files to read.** The `__init__.py` docstring of each package under `backend/app/`; `backend/app/pipeline/pipeline.py` for how the packages connect; `backend/tests/builders.py`.

## Phase 2: Chunking strategies

**What changed.** How manufacturer documents are cut into passages is now a choice, not one hardcoded function.
- `app/chunking/base.py` holds what every strategy shares: the `Chunk`, the `Chunker` interface (a `name` and a `chunk(pages, make)` method), heading detection, packing, and `maker`, which stamps each chunk with its manufacturer, file, page and headings.
- `app/chunking/strategies/` holds five strategies, one file each, registered by name in `strategies/__init__.py`:

| name | how it cuts | made for |
|---|---|---|
| `table_rows` (default) | one chunk per table row, the rest by layout block (the original code, unchanged) | catalogues full of tables |
| `recursive` | fixed size (800 characters) with 150 characters of overlap, cut at paragraph, then line, sentence, word | any text; the baseline |
| `sections` | a heading with the lines under it; a table kept whole with its caption | brochures with headings and few tables |
| `parent_child` | small chunks (300 characters) are searched, the bigger chunk they came from is what the model reads | long running text |
| `structure` | numbered clauses ("3. Pumps > 3.2 Casing") as a tree carried across pages; a flowchart page as each box with its neighbours | specifications and hierarchical or flowchart-like documents |

- `app/chunking/router.py` looks at a document (numbered clauses, flowchart pages, table pages, headings, words per line) and picks a strategy, with the reason. The `CHUNKER` setting decides: `table_rows` (the default), any strategy name, or `auto` for the router.
- For parent-child, a chunk has an optional `parent`. Search uses the chunk text; the prompt and the check that a quote really appears use the parent (`Chunk.for_model()`). Two children of one parent take one place in the search results, so the model does not read the same text twice.
- To spot a flowchart, the PDF reader now counts text that sits inside a drawn rectangle (`n_boxes`). Short texts alone were not enough: by that test 50 catalogue pages in 15 documents looked like flowcharts, including 27 of the 108 Grundfos pages and 1 of the 2 KSB BOA-X pages. With the drawn-box test, 2 pages do (1 Grundfos, 1 L&T). None of the catalogues is a flowchart document, so a lower number is better here; it only matters when `structure` is chosen.
- `eval_retrieval`, `eval_candidates` and `show_chunks` take a strategy name as an optional last argument.

Chunking applies to manufacturer documents. Tenders are still read page by page by the model, as before.

**Why.** Reviewers said the chunking was hardcoded for one kind of document. Real manufacturer documents also include brochures, specifications and process diagrams, so the cut should follow the document.

**The default did not change.** With `CHUNKER` unset, the fingerprint of every chunk and every ranked search result is identical to phase 1, so the prompts and the shipped demo cache still match.

**Measured, free (cache and local embeddings only).** `eval_retrieval` on valves (found in top 5) and `eval_candidates` (share of answer-key items where a cited page is among the passages the model reads, without / with the term scan):

| strategy | keyword | meaning | hybrid | valves 9933225 | pumps 9935891 |
|---|---|---|---|---|---|
| `table_rows` (default) | 6/7 | 4/7 | 6/7 | 25/25 / 25/25 | 142/158 (90%) / 146/158 (92%) |
| `recursive` | 7/7 | 5/7 | 5/7 | 25/25 / 25/25 | 138/158 (87%) / 144/158 (91%) |
| `sections` | 6/7 | 3/7 | 3/7 | 25/25 / 25/25 | 140/158 (89%) / 144/158 (91%) |
| `parent_child` | 7/7 | 5/7 | 6/7 | 25/25 / 25/25 | 142/158 (90%) / 142/158 (90%) |
| `structure` | 6/7 | 4/7 | 6/7 | 25/25 / 25/25 | 144/158 (91%) / 148/158 (94%) |
| `auto` | 7/7 | 5/7 | 6/7 | 25/25 / 25/25 | 142/158 (90%) / 146/158 (92%) |

How to read this: the samples are small (7 retrieval cases, 25 and 158 items), so a difference of one or two is not proof. No strategy is clearly better than the default. `structure` reaches 2 more pump items than the default and `auto` matches or beats the default on every number, but whether that improves the final answers needs new model calls, which this phase did not make (listed in `docs/NEEDS_PAID_RUN.md`). So the default stays `table_rows`.

**Tests.** 351 passed with `LLM_MAX_CALLS=0` (330 before). New: `tests/chunking/test_strategies.py`, `tests/chunking/test_router.py`, one search test (children of one parent) and one evidence test (the model reads the parent, and a quote from the parent stands). `test_chunker.py` became `test_table_rows.py`.

**In an interview.** "Chunking used to be one function tuned to table-heavy catalogues. I put an interface in front of it, kept the original as the default, and added four strategies plus a router that picks one from what the document looks like, such as numbered clauses, drawn boxes or tables. I compared them on the retrieval checks I could run for free, and since none was clearly better on these small samples, I kept the default and wrote down the paid check that would settle it."

**Files to read.** `backend/app/chunking/base.py`, `backend/app/chunking/strategies/__init__.py`, `backend/app/chunking/router.py`, then any one strategy (`structure.py` is the most interesting); `backend/tests/chunking/test_strategies.py`.

## Phase 2, follow-up: test documents that are not tables, and a flowchart check that holds

**(a) Retrieval cases for documents that are not tables.** There were none: the 7 retrieval cases all point at valve catalogues, which are mostly tables. `scripts/eval/make_samples.py` now writes two small invented documents, committed under `data/eval/samples/`:
- `clausemaker/pump-specification.pdf`, 6 pages of numbered clauses with no tables. Clause 2.2 starts on page 2 and runs onto page 3, where nothing on the page says it is about the booster pump.
- `flowmaker/valve-selection-guide.pdf`, 3 pages, the middle one a real flowchart: separate boxes joined by lines.

`data/eval/retrieval_cases_samples.json` holds 10 cases for them. On documents this short almost any search finds the right page somewhere in the top 5, so `eval_retrieval` now also counts how often the first result is on a right page. The top-5 line is printed as before.

| strategy | top 5 (keyword, meaning, hybrid) | first result (keyword, meaning, hybrid) |
|---|---|---|
| `table_rows` (default) | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `recursive` | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `sections` | 10/10, 10/10, 10/10 | 9/10, 8/10, 9/10 |
| `parent_child` | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `structure` | 10/10, 10/10, 10/10 | 9/10, 9/10, 10/10 |
| `auto` (picks `structure` for both) | 10/10, 10/10, 10/10 | 9/10, 9/10, 10/10 |

The gain is where expected: "booster pump impeller material" and "booster pump motor efficiency class" are answered on page 3, which only `structure` labels with "2. Booster pump > 2.2 Construction". These documents and cases were written knowing what each strategy does, so they show that the strategies work as designed, not how they do on real documents. On the valve catalogues, the default's first-result count is keyword 4/7, meaning 3/7, hybrid 4/7 (not counted before).

**(b) The flowchart check.** The 2 catalogue pages it accepted were not flowcharts: Grundfos CR data booklet page 18 is a type-key code table, and L&T API 600 page 17 is an ordering-information grid. Tightening the box test (a box must stand apart from other rectangles, since table cells share their edges) turned up a third, L&T trunnion ball valves page 24, another ordering-code grid. All three are tables whose cells are drawn as separate boxes, which the table finder missed. What none of them has is a line drawn from one box to another. So:
- `app/reading/boxes.py` (new) finds the boxes on a page, and the lines that join two boxes. The reader stores both on each page (`PageRecord.boxes`, `PageRecord.links`).
- A page is a flowchart when it has no table, at least 6 boxes with text, at least 70% of them short, and at least half of them joined to another box by a line.
- Result on the real catalogues: 0 of 562 pages are flowcharts (it was 50 pages with the first version of the test in phase 2, then 2). On the invented guide, the flowchart page is found.
- Flowchart chunks now follow the lines, not the reading order. Reading order put "Slurry" next to "Steam"; following the lines, the chunk for the "Slurry" box is `What does the line carry? -> / Slurry / -> Knife gate valve`.
- Lines are matched to boxes by position, because PDF readers often merge a row of boxes into one text block (the invented flowchart's three boxes in a row came out as one block).

`tests/chunking/test_flowchart_pdf.py` builds the two PDFs, reads them with the real reader and checks the boxes, the 10 lines, the router's choice and the chunks.

**The default did not change.** The fingerprint of every chunk and every ranked search result is identical to phase 2.

**In an interview.** "My first flowchart test also accepted three catalogue pages, and when I looked, all three were tables whose cells are drawn as separate boxes. The thing a flowchart has and a table does not is lines between the boxes, so the reader now records them, and the chunks follow them: each box comes with the box before and after it. I also made a small specification and a selection guide to test on, because all my real documents were tables."

**Files to read.** `backend/app/reading/boxes.py`, `is_flowchart` and `flow_chunks` in `backend/app/chunking/strategies/structure.py`, `backend/scripts/eval/make_samples.py`, `backend/tests/chunking/test_flowchart_pdf.py`.

## Phase 3: Vector store

**What changed.** Where the chunk vectors live is now a choice behind one interface, in a new package `app/vectorstore/`:
- `base.py`: the `VectorStore` interface. A store can say whether it already holds a file (`stored`), give back that file's chunks (`chunks`), store a file's chunks with their vectors (`put`, replacing the old ones), and find the nearest chunks to a query (`nearest`), narrowed by any of category, manufacturer, file and page.
- `memory.py`: `MemoryStore`, the original behaviour as an implementation: one NumPy matrix, every vector compared exactly, nothing kept on disk.
- `chroma.py`: `ChromaStore`, kept on disk with Chroma in `backend/.cache/chroma` (inside the cache folder git already ignores; `CHROMA_DIR` moves it). It keeps one row per chunk (vector, the fields to filter on, and the whole chunk as JSON) and one row per document (content hash and settings).
- `ingest.py`: puts a category's documents into a store and builds the index. Each file is fingerprinted first (SHA-256 of its bytes); if the store holds it with the same fingerprint and the same settings, it is not read, chunked or embedded again. The settings are the chunking strategy, whether pictures are read, and a fingerprint of the reading and chunking code, so a code change re-reads every file instead of serving stale chunks.
- `VECTOR_STORE` chooses: `memory` (the default) or `chroma`.

The search itself keeps BM25 for keywords and RRF to merge the rankings; only the meaning ranking now comes from the store. Ties are broken by the chunks' order in both stores, so they rank the same when their numbers are the same. `Index(chunks)` with no store still works as before (it makes its own memory store), and the pipeline and scripts now call `open_index(category_dir, ...)`. The vectors are the same as before: they come from the same embedding cache. `app/chunking/corpus.py` now reads one file at a time (`pdf_files`, `chunk_file`), so ingest can skip a file without reading it.

**Measured, free.**
- Default (`memory`): the fingerprint of every chunk and every ranked result is identical to phase 2, and `eval_retrieval` on valves is unchanged (top 5: keyword 6/7, meaning 4/7, hybrid 6/7).
- Ingest once: with Chroma, building the valves index took 83 s the first time and under 1 s the second (pumps: 259 s, then under 1 s). The memory store reads every file each time (86 s and 235 s).
- Chroma against memory, same chunks (1,714 valves, 2,099 pumps; Chroma rebuilt every chunk exactly from the store): the top 10 results were identical for all 225 test queries in all three modes (the 7 retrieval cases plus 218 headings and section titles taken from the catalogues). Chroma returned every chunk asked for. But the order of the whole meaning ranking differed below the top 10 for 32 of 141 valves queries and 41 of 84 pumps queries.
- What matters is whether the questions sent to the model stay the same. For the five dev tenders whose reading is in the cache, every question the pipeline would ask, at both search depths the budget uses: 1,273 questions, 1,270 identical, 3 different. In all 3, the passages are the same, but two of them change places (place 2 for Duncan "nominal size" in 9840129, at depth 16 and at depth 8; place 9 of 16 for KSB "service" in 9935891). The prompt lists passages in order, so each of those 3 is a new question for the cache.
- Why: Chroma computes distances in its own float32 code, so passages with almost the same similarity can come out in the other order deep in the ranking. The RRF merge adds a tiny score for every place in every ranking, so that can tip two passages whose merged scores were nearly equal.
- `eval_retrieval` with Chroma gives the same numbers as with memory: valves top 5 keyword 6/7, meaning 4/7, hybrid 6/7, first result 4/7, 3/7, 4/7; the invented samples 10/10 in every mode, first result 9/10, 7/10, 8/10.

**So the default stays `memory`.** Chroma did not give identical results, and the rule for this phase was to switch only if it did. Switching would cost 3 new model calls, about 14,800 input tokens, about 2 rupees at the app's own rate (`RUPEES_PER_MILLION_TOKENS` = 100), entered in `docs/NEEDS_PAID_RUN.md`. A way to make Chroma exact, not done here: let Chroma pick the candidates and score them again exactly with NumPy.

**One process at a time.** Chroma kept in a folder is for one process. The app is one process (its tenders run as threads, and writes to a store go one at a time). While measuring, I ran three scripts on the same folder at once and Chroma's index broke ("Error loading hnsw index"); deleting the folder, which is only a cache, fixed it.

**Docker.** `chromadb==1.5.9` is added to `requirements.txt` (released in May 2026; installed with `--uploaded-prior-to` so no package newer than two weeks came with it). `docker compose build` succeeds, the image is 1.52 GB, and a Chroma store works inside it. In the container the store lives in `/data/cache/chroma`, on the same volume as the other caches.

**Tests.** 384 passed (355 after the follow-up) with `LLM_MAX_CALLS=0`. New: `tests/vectorstore/test_stores.py` (both stores, the same tests: nearest first, every filter, an unknown filter refused, a file kept until its content or settings change, storing again replaces, a chunk comes back exactly, Chroma survives a restart) and `tests/vectorstore/test_ingest.py` (ingest gives the same chunks as reading the files, a file is read once and again only after it changes, another chunker reads again, the index over a store finds what the index over the chunks finds).

**In an interview.** "The vectors used to be rebuilt in memory on every run, so I put a vector store interface in front of them, with the old exact NumPy search as one implementation and Chroma as the other. With Chroma, each file is read and embedded once and skipped while its content hash is unchanged, and search can be narrowed by category, manufacturer, file and page. Before making it the default I checked every question the pipeline would ask, and 3 in 1,273 changed order because Chroma's approximate search ranks near-ties differently, so I kept the exact store as the default and wrote down the cost of switching."

**Files to read.** `backend/app/vectorstore/base.py`, then `memory.py` and `chroma.py` side by side, `ingest.py`, and `Index.meanings` in `backend/app/retrieval/search.py`.

## Phase 3, follow-up: exact scores with Chroma, and Chroma as the default

**What changed.** The store now only picks the candidates; the index scores them itself. Each store's `nearest` returns candidate chunks (the index asks for 20 more than it needs, so a chunk an approximate search ranks too low is still scored), a new `vectors(ids)` gives back the stored vectors, and `Index.meanings` multiplies the category's vectors, in the index's chunk order, by the queries: the same product as the first version. Chroma's collection uses inner product instead of cosine (the vectors are unit length, so the two are the same).

**Why it had to be this exact.** Measured with NumPy: the last digits of a dot product depend on how many rows are multiplied together and in what order (with one query, reordering the same 2,099 rows changed 35 of the results). So scoring only the candidates, or scoring in Chroma's order, would not reproduce the saved questions. Chroma in cosine mode also gave the vectors back with some last digits changed (on a test of 40 vectors, 180 values changed even when the vectors were already unit length); in inner-product mode they come back unchanged. A test now checks that stored vectors come back exactly, and fails in cosine mode.

**One limit.** The rank merge (RRF) uses the whole meaning ranking of a manufacturer's chunks, and the 3 differences in phase 3 came from places far down it. So the candidates are all of that manufacturer's chunks, and Chroma's approximate search saves no work at this size. What Chroma gives is storage between starts, filters and reading each document once.

**Measured, free.**
- The fingerprint of every chunk and every ranked result is identical to phase 2 with both stores.
- The 225 queries: the top 10 identical in all three modes, and the whole meaning ranking identical, scores included to the last digit, for all 225 (before: 109 of 141 and 43 of 84).
- Every question the pipeline would ask for the five dev tenders in the cache, at both search depths: 1,273 of 1,273 identical (before: 1,270).

**So Chroma is now the default** (`VECTOR_STORE=chroma`), and `memory` remains as the option. Switching costs nothing: no question changes. The entry in `docs/NEEDS_PAID_RUN.md` is removed. A Chroma folder made before this change used cosine mode; it is only a cache, so delete `backend/.cache/chroma` once.

**Tests.** 386 passed.

**In an interview.** "Chroma first changed the order of two passages in 3 of 1,273 questions, because its arithmetic differs from NumPy's in the last digits. So I let Chroma propose the candidates and score them myself with the same matrix product as before; I also found that Chroma's cosine mode changes stored vectors slightly, so I store them in inner-product mode. After that every question was identical, so Chroma became the default."

**Files to read.** `Index.meanings` in `backend/app/retrieval/search.py`, `vectors` and the collection setup in `backend/app/vectorstore/chroma.py`.

## Phase 4: Categories and extraction

**What changed.**
- **Per-category config.** Each category folder now has a `category.json` beside its `manufacturers/` folder, with the category's own `product_words`, `type_attributes`, `filler_words` and `extraction_rules` (described in the README). What used to be written into the code or into shared files moved there:
  - the word-to-category table (`backend/config/product_categories.json`, now deleted);
  - `pump_type` and `valve_type` from the shared "defining" names;
  - "valve" from the filler words in `app/vocabulary/words.py`;
  - the pump duty-point rule from the tender-reading prompt in `app/extraction/atomize.py`.

  A new category is a new folder with its PDFs and a `category.json`; nothing in the code names a category. Units, abbreviations and other shared vocabulary stay in `backend/config/`.
- **One vocabulary for all.** The vocabulary is the union over all categories, and the prompt for reading a tender's rows is the shared rules with every category's rules in place. So a mixed tender is read with everything, and the prompt does not depend on which items a tender has. A test pins the prompt to the exact text the saved answers were made with (SHA-256 `49cee02f…`). The flip side: adding a rule to any category changes the questions for every tender, so their saved answers no longer match. A category without rules changes nothing.
- **Category optional on upload.** `POST /runs` no longer needs a category, and the upload page now defaults to "Find it in the tender". Such a run reads the tender's items and sends each to a category (`app/categories/routing.py`):
  - first by product words: a title that names exactly one category's word goes there;
  - otherwise by the categories' own documents: the title is compared in meaning with every category's chunks, and the category whose 5 closest chunks are most alike wins.

  No model is asked. A tender of one category is then matched whole, exactly as if the category had been chosen.
- **Mixed tenders.** A tender with items of several categories gets one run per category. The run started takes the first category, and the others are created next to it, each with its own copy of the tender so its links to tender pages work. Each run matches only its own items and says in its notes which items were matched elsewhere. Each report stays a normal one-category report, so the scoring, ranking and report code did not change. Runs waiting for approval of their estimate pass that on to the runs made from them.

**Why.** Reviewers said a new product category should need no code changes, and that one category per upload is not enough because a tender can buy pumps and valves together.

**The default did not change.**
- The tender-reading prompt is byte-identical (the test above).
- The defining names (`product_type`, `pump_type`, `valve_type`) and the filler words (`body`, `connection`, `end`, `ends`, `type`, `valve`) are the same sets as before.
- Chunking and search are untouched: `eval_retrieval` on valves is unchanged (top 5: keyword 6/7, meaning 4/7, hybrid 6/7; first result 4/7, 3/7, 4/7).

**Measured, free (cached tender readings, local embeddings).** I routed every item of every tender whose reading is in the cache (5 dev, 4 hold-out; nothing was tuned on the hold-out tenders).
- `data/tenders/sources.csv` records a category for 7 of these tenders, with 11 items between them. All 11 went to the recorded category: 10 by words, and 1 ("SITE VISIT FOR SUPERVISION", in a pump tender) by documents.
- Routed by the documents alone, as if no word had matched, the same 11 items also all went to the recorded category.
- Two hold-out tenders are not in `sources.csv`. Their 3 items went to valves ("PFA lined ball valves") and pumps ("Submersible pumpsets", "Submersible pump starters") by words; there is no recorded label to score them against.
  - *Follow-up, after v3:* both are now in `sources.csv` (9604147 pumps, 10016383 valves, read from their bid pages), and these categories agree with where their 3 items were routed above. The routing was not re-run. The row for 9604147 notes that it exposed a heading bug that was then fixed, so it is not a pure unseen test.
- No tender here is mixed, so the split into several runs is tested with a fake router in `tests/api/test_api.py`, not measured on a real tender.

**Tests.** 398 passed (386 before): `tests/categories/test_categories.py` (configs, the optional file, the union, words first and documents for the rest, the documents not read when words decide), three API tests (one-category tender matched whole, two categories give two runs with their own tender copies, a routing failure is reported), `tests/pipeline/test_pipeline.py` (only the given items are kept, with a note), and the prompt test. Frontend: 74 passed (73 before), and `vite build` succeeds. `docker compose build` builds both images, and inside the backend image both categories load and the prompt hash matches.

**In an interview.** "Category knowledge used to be spread through the code: a word table, a filler word, a pump rule inside the prompt. Now each category is a folder with its documents and a small JSON file, and a tender's items are routed to categories by their product words, or by which category's documents they resemble most, so a mixed tender becomes one run per category. I checked that the prompt is byte-identical to before, so every saved answer still matches, and the routing put all 11 labelled items in the right category."

**Files to read.** `data/categories/pumps/category.json`, `backend/app/categories/config.py`, `backend/app/categories/routing.py`, `execute_routed` in `backend/app/pipeline/runner.py`, and the top of `backend/app/extraction/atomize.py`.

## Phase 5: Architecture document, token counting, model settings, document sources

**What changed.**
- **`docs/architecture.md`** (new): what each package does; three Mermaid diagrams (overall structure, the ingest path, the query path); and a design-decisions section with the trade-offs stated plainly: the model reads and code judges, answers keyed by the exact prompt, the default chunker kept for cache reasons, exact scoring instead of approximate search, one process per Chroma folder, the shared tender-reading prompt, one run per category, routing without the model, approval before spending, settings that default to what the saved answers were made with, and what needs paid runs. All three diagrams parse with Mermaid's own parser (checked with `mermaid` 11.4.1 outside the project).
- **Token counting** (`app/cost/tokens.py`, new). `TOKEN_COUNTER` chooses how a question's tokens are counted for the budget and the estimate:
  - `estimate` (the default): characters / 4, as before.
  - `gemini`: Gemini's own `count_tokens`, which is exact. Counting is a request to Google, so it stays under `LLM_MAX_CALLS`: once that many counts have been made in a process, or if a count fails, it falls back to the estimate. With the limit at 0 nothing is sent. Each text is counted once.

  The budget keeps giving the estimate the instructions without the answer format added to them (about 440 tokens a question less than is sent), as it always has, so default estimates do not change; the exact counter is given what is really sent. The Gemini API refuses a system instruction in `count_tokens` (the installed SDK raises for it), so the instructions are counted as the first part of the message. `estimate_cost` also prints the exact figure, and says how many counts really were exact. The two copies of "4 characters a token" in the cost scripts now come from `app/cost/tokens.py`.
- **Temperature as a setting.** `LLM_TEMPERATURE` (a number, or `DEFAULT` for the model's own) replaces the 0 written into `gemini.py`, and the model was already a setting (`LLM_MODEL`). The default stays 0: Google's Gemini 3 page currently says "we strongly recommend keeping the temperature parameter at its default value of 1.0" and that lower values "may lead to unexpected behavior, such as looping or degraded performance", but every saved answer was made at 0, so changing it is a paid check (`docs/NEEDS_PAID_RUN.md`). At the default the cache-key settings stay exactly `thinking=LOW` (checked on the real client), and any other value adds itself to the key. `0` and `0.0` give the same key.
- **Collecting: no new tool, the existing one made accountable.** `app/collecting` already found catalogue PDFs on a manufacturer's site (`crawl.py`: links followed to a depth, staying on the site, obeying `robots.txt`) and saved them politely (`download.py`: a pause between requests, each content saved once by its hash). But the record of where a saved file came from was written by the script, untested, and nothing checked that the shipped documents had one. Now:
  - `app/collecting/sources.py` keeps the records: address, the page it was found on, date, size and SHA-256 in the maker's `crawl_sources.csv`. Hand-collected documents keep their row in `data/categories/sources.csv`.
  - `unrecorded()` lists any PDF with neither, and a test runs it over the shipped documents: all 27 have a source.

**Why.** Reviewers asked for an architecture document with diagrams, a real token counter instead of characters / 4, temperature and model as settings, and a way to collect documents with their sources.

**Defaults did not change.**
- The model client's cache-key settings are `thinking=LOW` and the temperature sent is 0, as before.
- The tender-reading prompt test still passes, and the budget's estimate uses the same rule on the same text.
- `estimate_cost` gives the same output as the previous commit's code (see below).

**Measured, free (cached answers only, `LLM_MAX_CALLS=0`).**
- `estimate_cost` on the two labelled tenders: 9933225 has 56 of 56 questions already answered in the cache, and 9935891 has 204 of 204. So the saved answers still match.
- On 9840129, which has uncached questions, I ran the previous commit's code and this phase's code side by side on the same caches. The output is identical: 133 questions, 10 already answered, 123 new, about 606,094 input tokens.
- The budget's own pricing is unchanged by construction: the same rule on the same text, with `tests/cost/test_budget.py` unchanged and passing.

**Tests.** 413 passed (398 before): `tests/cost/test_tokens.py` (the default is the original estimate; an exact counter is used up to the call limit, once per text, nothing is sent at a limit of 0, a failed count falls back; unknown counters refused), `tests/llm/test_gemini_settings.py` (temperature values and their cache keys), `tests/collecting/test_sources.py` (a saved file's record, unrecorded files found, every shipped document recorded).

**In an interview.** "Phase 5 was about honesty and settings: an architecture document whose design decisions say what each choice costs, a token counter that can ask Gemini for the exact count but never spends past the call limit, and model, thinking and temperature as settings. Every default stays what the saved answers were made with, which is why the temperature is still 0 even though Google now recommends 1.0 for Gemini 3; testing that is listed as a paid check. For collecting I did not add a new tool: I moved the source records into the package and added a test that every document has one."

**Files to read.** `docs/architecture.md`, `backend/app/cost/tokens.py`, `temperature_setting` in `backend/app/llm/gemini.py`, `backend/app/collecting/sources.py`.

## Phase 6: A small knowledge graph for equivalent standards and tender hierarchy

**What changed.** A new package, `app/graph/`, built only from data the project already has, with no model calls:
- `graph.py`: a minimal graph. Nodes have a kind, a label and the spellings seen for them; links have a relation and a list of where each was seen. It saves as plain JSON and draws as Mermaid. There is no graph library: it is about 70 lines.
- `standards.py`: standards as a graph, with two kinds of knowledge kept apart because they are not equally sure.
  - **The same standard under another name.** An adopting body keeps the number: "BS EN ISO 5208", "DIN EN ISO 5208", "EN ISO 5208" and "ISO 5208" are one document, and "BS EN 593" is "EN 593". This follows from the names, so each standard is one node and its spellings are its names.
  - **Named together.** "API 600 / BS 1873" in a catalogue, or "ISO 21049/API 682" in a tender, is a link that records where it was seen. I first checked what such pairs mean in our documents, and they are often not equivalent: a gate-valve standard next to a globe-valve standard (API 600 / BS 1873), two materials (ASTM A105 / A216), two parts of one standard (EN 1092-1 / -2). Some are the same document (API 607 / ISO 10497, API 682 / ISO 21049). So these links never count as a match.

  Standard names are found in capitals only, so "pressure is 16 bar" is not the standard IS 16. Steel grades and material numbers written with "EN" ("EN 8", "EN 1.4408") are not taken as standards.
- `tender.py`: a tender as a graph: tender → items → requirement rows → atomic requirements, with rows citing standards. A row printed once for several items is one node shared by them, so "which items does this row apply to" and "what does this item require" are each one lookup.
- `scripts/run/build_graph.py` builds the standards graph from every catalogue chunk and every saved tender reading, and writes `data/graph/standards.json`, which a person can read and correct. `scripts/run/show_graph.py <tender>` shows a tender's hierarchy, its shared rows and the standards it cites with their links, and can write the hierarchy as a Mermaid diagram.
- **Use in judging, only with `KNOWLEDGE_GRAPH=on`** (default `off`). When a standard is asked for and the evidence does not state it by that name:
  - a stated standard that is the same document under another name counts as met;
  - a stated standard that documents only name together with it goes to a person (`equivalent grade` flag), and only when the tender says it accepts an equivalent.

  With the setting off, the new code is never reached.

**Why.** The plan's stretch goal, limited as asked to equivalent standards and the tender hierarchy.

**Measured, free (saved answers only, `LLM_MAX_CALLS=0`).**
- **Standards graph:** built from 2 categories' catalogues and the 9 tenders whose reading is saved (2 were skipped, not saved). It has 246 standards, 21 of them seen under more than one name, and 24 pairs named together (22 from catalogues, 2 from a tender: API 682 / ISO 21049 and API 614 / ISO 10438-3). A few nodes are still part numbers read as EN names; judging only looks up names that appear in a requirement and its evidence, so they cannot change a result.
- **Tender hierarchy:** on all 9 tenders, every requirement is reachable from its tender. Rows shared by several items: 15 of 20 in 9840129 (4 items), 29 of 33 in 9935891 (2 items), 21 of 384 in 9987635; none in the one-item tenders.
- **Effect on judging,** on the two labelled tenders (every answer from the cache: 269 read, 0 model calls). Scored with the graph off and on in separate processes, **no outcome changed**: 0 of 77 for 9933225, 0 of 328 for 9935891, and no row of either answer key comparison. The reason: their 31 standard outcomes are exact matches, "no evidence found", or test standards that need a certificate; none states a different standard for the graph to link.
- The tenders whose cited standards do have links (9840129: API 598, ASME B16.10, B16.34; 9987635: API 682 / ISO 21049) do not have their evidence saved, so measuring them costs money; see `docs/NEEDS_PAID_RUN.md`.

**The default did not change.** `KNOWLEDGE_GRAPH` is off, and judging only reaches the new code when it is on. No prompt, chunk or search changed; the test suite and the earlier checks pass as before.

**Tests.** 432 passed (413 before): `tests/graph/test_standards.py` (names found and written one way, including the cases above that must not be standards; spellings as one node; links with where seen; "same" and "together" kept apart; the saved graph loads), `tests/graph/test_tender_graph.py` (a shared row is one node, every requirement reachable, cited standards, Mermaid), `tests/graph/test_judging_with_graph.py` (off changes nothing; the same standard under another name is met; named together goes to a person only with "or equivalent"; named together is never a match).

**In an interview.** "The knowledge graph is deliberately small: standards and a tender's structure, built by a script from data I already had, saved as JSON a person can check. Before trusting 'A / B' in a catalogue as equivalence I looked at the pairs, and many were not, so only the naming rule for adopted standards can count as a match, and everything else only sends a requirement to a person. It is off by default, and on the labelled tenders it changed nothing, which I report as it is rather than claiming an improvement."

**Files to read.** `backend/app/graph/standards.py`, `backend/app/graph/tender.py`, `standards_verdict` in `backend/app/judging/compare.py`, `data/graph/standards.json`.

## Phase 7: Re-measure and price the paid checks, and finish v3

**What changed.**
- **Every paid check is priced** in a table at the top of `docs/NEEDS_PAID_RUN.md`, with what each would tell us and a priority, and a recommended plan follows it. Nothing paid was run.
  - Whole runs (a new model or temperature) are priced from the tokens the same run really used at today's settings. Every saved answer records them, so this is measured, not estimated.
  - Partial runs (another chunker, the graph on 9840129) are priced from the free estimate, corrected by the measurement below.
  - Rupees use the app's own rate. Lighter models are priced with Google's current price list on the same token mix, so no exchange rate was assumed.
- **The token estimate was checked for free.** For every saved question of the two labelled tenders, characters / 4 was compared with the input tokens Gemini reported: 74% (valves) and 69% (pumps) of the real count, from 45% to 91% per question. So the estimate shown before a run is about 30% low on input tokens, and output tokens come on top. This answers the phase 5 paid check without paying. The default counter is unchanged, as agreed; the README now says how rough the estimate is.
- **Recommended plan, under ₹100**, on the smaller labelled tender 9933225, scored against its answer key with `score_gold` and `LLM_MAX_CALLS=70`:
  1. Gemini 3.5 Flash-Lite, ≈ ₹19.
  2. Temperature 1.0 on the current model, ≈ ₹41, before 1 January 2027, when Google doubles its price.

  Expected total ≈ ₹60. Today's result to compare with: 31 of 35 statuses and 23 of 23 pages agree, from 59 saved answers.
- **Script fixes found while pricing:**
  - `score_gold` now prints the calls and tokens a run used, so a paid run's real cost can be compared with its price.
  - The paid-run instructions now use `score_gold` on one tender, because `eval_all` would also spend on the other labelled tender.
- **README for v3:** what is new, how to switch the settings (which ones change the questions and so cost money, and which do not), Docker Compose commands, the free checks, and corrected statements about the estimate and about reading documents once.
- **Docker:**
  - `docker-compose.yml` now passes the model, thinking, temperature, chunker, passages, store, counter and graph settings through, each defaulting to today's value.
  - The backend image now includes `data/graph/standards.json`, which phase 6 had left out: inside the image the graph had 0 standards, and now it has 246 and 24 links.

**Measured, free (`LLM_MAX_CALLS=0`).**
- **Cost of whole runs at today's settings** (read from the saved answers):

  | Tender | Calls | Input tokens | Output tokens | At ₹100 per million |
  |---|---|---|---|---|
  | 9933225 | 64 (59 for `score_gold`) | 385,355 | 28,109 | ≈ ₹41 |
  | 9935891 | 214 | 1,568,873 | 65,297 | ≈ ₹163 |

  Reading the manufacturers' documents cost 0 calls, because the store holds them.
- **New questions per chunker** (`estimate_cost` with the memory store, so the Chroma store was not disturbed):

  | Tender | `recursive` | `sections` | `parent_child` | `structure` | `auto` |
  |---|---|---|---|---|---|
  | 9933225 | 56 | 56 | 55 | 41 | 41 |
  | 9935891 | 204 | 204 | 203 | 141 | 0 |

  `auto` costs nothing on the pump tender because it keeps `table_rows` for every pump catalogue.
- **Today's baseline on 9933225:** 31 of 35 statuses and 23 of 23 pages agree with the answer key.

**Checks.**
- Backend: 432 tests passed. ruff shows only the 5 findings that were there before v3.
- Frontend: 74 tests passed, and `vite build` succeeds.
- `docker compose build` builds both images. Inside the backend image the defaults are unchanged (store `chroma`, graph `off`, counter `estimate`, temperature 0 with the old cache key), both categories load, and the graph has 246 standards.
- **Folders:** no tracked folder holds more than 7 files, except three.
  - `frontend/` holds the root config files (8), kept there as agreed in phase 1.
  - `data/demo_cache/` holds the shipped answers (611 files).
  - `data/categories/valves/manufacturers/ksb/` holds KSB's 8 valve catalogues.

  The last two are data, not code. Their file and folder names are part of the saved answers' prompts and the chunk names, so moving them would make saved answers miss; they are left as they are, for the owner to decide.

**In an interview.** "Before spending anything on the open questions, I priced each one from data I already had. The saved answers record the real tokens of every call, so a re-run under another model or temperature could be priced from what the same run used, and comparing those counts with my characters-divided-by-four estimate showed the estimate is about 30% low, which answered one of the paid questions for free. The recommended plan tests a lighter model and Google's recommended temperature on the smaller labelled tender for about ₹60, and waits for approval."

**Files to read.** `docs/NEEDS_PAID_RUN.md` (the table and the plan), the "Switching the settings" section of `README.md`, `docker-compose.yml`.

## Phase 7, follow-up: shipped answers in subfolders, data folders documented, model id checked

**What changed.**
- **Shipped answers in subfolders.** The 610 shipped answers in `data/demo_cache/` moved into subfolders named by the first two characters of each file's name (`3f/3f….json`), 236 subfolders in all. Only the folder's README stays at the top; the README was the 611th tracked file there. One function, `shipped_path` in `app/llm/llm_cache.py`, says where an answer lives. The cache lookup and the export script both use it, and two cache tests now ship their answer the way the export script does.
- **Exemptions documented.** `docs/architecture.md` now states which folders are exempt from the 7-file rule and why: `frontend/`'s root config files; the manufacturers' documents (KSB's 8 valve catalogues), whose folder and file names are part of every chunk and question; and the shipped answers.
- **Model id checked for the approved paid step 1.** Google's models page lists `gemini-3.5-flash-lite` as "Stable", and its thinking page lists it as supporting "minimal, low, medium, high", so `LLM_THINKING` stays at `LOW` and only the model changes. Nothing was run; the owner confirms the id in AI Studio first.

**Measured, free (`LLM_MAX_CALLS=0`).**
- **Every answer is still found.** All 610 file names from the last commit are found by `CachedLLM.saved` in their new place, and git records all 610 moves as unchanged (R100).
- **Fresh-install runs, before and after the move.** The five example tenders were run end to end as a fresh install would: an empty cache folder, so no store and no live answers, with only the shipped answers and vectors.
  - Before and after, the runs used the same answers: 84, 97, 121, 254 and 50. That is 606 answers in all, with 0 model calls and 0 misses.
  - The other 4 shipped answers were not used before the move either. They are evidence answers exported on 19 October for questions that later changes to tender reading no longer ask. They are left in place; deleting them is the owner's choice.
- **Inside the rebuilt backend image** all 610 answers are found by the same rule.

**Checks.** Backend 432 passed, frontend 74 passed, and `docker compose build` succeeds; ruff shows only the 5 old findings.

**Still over 7 files.** Two subfolders hold 8 and 9 answers (`84/`, `c5/`), because 610 names spread over 236 two-character subfolders are not even. Three characters, or two levels of two, would keep every subfolder well under 7; that is a one-line change to `shipped_path` plus moving the files again.

**Files to read.** `shipped_path` and `saved` in `backend/app/llm/llm_cache.py`, `copy_answers` in `backend/scripts/cost/export_demo_cache.py`, and the 7-file rule in `docs/architecture.md`.

## Phase 7, paid step 1: a lighter model on the smaller labelled tender

The owner approved step 1 only: `gemini-3.5-flash-lite` on tender 9933225. The model id was confirmed on Google's model list.

**What happened, in order.**
1. **A one-call smoke test.** One real evidence question was sent with `LLM_MAX_CALLS=1`. The model accepted `LOW` thinking and returned a valid answer on the first try, for ≈ ₹0.25.
2. **A first attempt.** It ran with `LLM_MAX_CALLS=70` alone. The budget's 60 reserved calls left 8 for evidence, so only part of the tender was evaluated (9 calls, ≈ ₹1.12). That was a mistake in the plan, not in the code: the reserve was not accounted for.
3. **The corrected run, with `RESERVED_CALLS=5`.** 56 calls, ≈ ₹17.87, inside an in-run guard that stops before any call once the spend passes the approved amount.

Total ≈ ₹19.24. Step 2 was not run. `LLM_MAX_CALLS` is 0 again, and `backend/.env` was changed from 400 to 0 so that 0 is also the default.

**Result.** The full table is in `docs/NEEDS_PAID_RUN.md`. On the 30 labelled rows both models scored:

| | Statuses agree | Pages agree | Cost for this tender |
|---|---|---|---|
| Gemini 3.8 Flash | 26 | 18 of 18 | ≈ ₹41 |
| Gemini 3.5 Flash-Lite | 24 | 14 of 16 | ≈ ₹18 |

The other 5 labelled rows were not scored for Flash-Lite because it named one requirement `end_connection` instead of `valve_end_connection`. The tender reading itself was identical. Verbatim-quote rejections: 1 of Flash-Lite's 100 findings, and 0 of the current model's 231. One tender of 11 requirements is not enough to choose a model; the default stays `gemini-3.8-flash`.

## Phase 7, paid step 2: temperature at the model's default on the smaller labelled tender

The owner approved step 2: `LLM_TEMPERATURE=DEFAULT` (1.0, as Google advises for Gemini 3) with the current model on tender 9933225. It ran under an in-run guard at ₹45 and cost ≈ ₹40.54, with no errors.

**Result, all 35 labelled rows** (the full table is in `docs/NEEDS_PAID_RUN.md`):

| | Statuses agree | Pages agree |
|---|---|---|
| Temperature 0 | 31 of 35 | 23 of 23 |
| Temperature 1.0 | 29 of 35 | 21 of 21 |

- **No looping:** no retries, no empty or truncated replies, and no longer outputs than at temperature 0. No quote failed the verbatim check at either temperature.
- **Naming again:** as with Flash-Lite, the model named one requirement differently (`conformity_to_governing_specification`), so the answer key, which matches by attribute name, needed that one name mapped to score all 35 rows.
- **Default unchanged:** on one tender, temperature 1.0 is no better and no cheaper, so the default stays 0.

**Something to fix later, free:** two of two paid runs lost labelled rows only because the model chose another attribute name. Matching the answer key by the tender row (file, page, row name) instead of by attribute name would make such runs comparable without a manual mapping.

## Scoring against the answer key by tender row

**What changed.** `score_gold` and `eval_all` now find each requirement's answer-key entry by the tender row it was read from, not by the attribute name the model gave it.
- The answer keys are keyed by the names the current model chose when the labels were made. In both paid runs, the model named one requirement differently (`end_connection`, `conformity_to_governing_specification`), so 5 labelled rows had nothing to compare with.
- **The anchors files.** Each labelled tender now has `data/eval/gold/<tender>.rows.json` beside its answer key. It lists, for every tender row (item, file, page, row name and value), the answer-key entries that row produced, in order. `scripts/gold/make_row_anchors.py` makes it, free, from the saved reading the labels were made from, and checks that every answer-key entry is covered (7 of 7 for 9933225, 74 of 74 for 9935891).
- **Scoring** (`app/evaluation/rows.py`):
  - a row that produced one entry gives it to every requirement read from that row;
  - a row that produced several (12 rows of 9935891 did) pairs them in order;
  - only otherwise does it fall back to the attribute name. The script says how many were found each way.
- `compare` takes the entry rule as a parameter, so the code that builds scoring rows is not duplicated.
- `eval_all` no longer takes every `.json` in the gold folder for an answer key; `answer_keys()` skips the anchors files.

**Proof that nothing else changed** (saved answers only, no model call):
- On the current model's saved answers, row matching gives exactly the same rows as name matching, every field in the same order, for both labelled tenders.
- 9933225: 31 of 35 statuses, 23 of 23 pages. 9935891: 203 of 296 statuses, 69 of 113 pages. Every entry was found by row.

**The paid runs on all 35 rows of 9933225**, now with no manual mapping:

| | Statuses agree | Pages agree |
|---|---|---|
| Current model, temperature 0 | 31 of 35 | 23 of 23 |
| Temperature 1.0 | 29 of 35 | 21 of 21 |
| Gemini 3.5 Flash-Lite | 28 of 35 | 19 of 21 |

The temperature result equals the one from the manual mapping earlier, which cross-checks the row matching.

**Tests.** 438 passed (432 before). The new tests are in `tests/evaluation/test_rows.py`:
- with the original names, rows and names give the same result;
- a renamed requirement is found by its row;
- a split row is paired in order even when both names change;
- a row split differently, or unknown to the anchors, falls back to the name;
- anchors survive saving and are not taken for answer keys;
- every shipped answer key's entries are covered by its anchors.

One run of the full suite had one failing test, which I did not see; it did not come back in 8 more runs. It is not explained yet.

**Files to read.** `backend/app/evaluation/rows.py`, `backend/scripts/gold/make_row_anchors.py`, `data/eval/gold/GeM-Bidding-9933225.rows.json`.

## The flaky test: Chroma on Windows, and reopening a stuck client

**What went wrong.** One store test failed now and then, about once in 20 to 47 runs of the store tests. The result was never wrong; Chroma raised `InternalError: Error executing plan: Internal error: Error creating hnsw segment reader: Nothing found on disk`. At first it appeared in a nearest-neighbour query; later also when only the stored vectors were read, which the app does every time it builds an index.

**What was measured** (free, with `scripts/diagnose/chroma_repro.py`, a standalone script that uses Chroma alone: it writes a few vectors the way the store does, reads them back three ways, and at the first error checks whether the store recovers):
- **Windows only, so far.** With Chroma 1.5.9 on Windows 11 it failed at attempts 5, 41 and 175 (and 87 earlier), in every folder tried: the temp folder, the home folder and the project folder. On Linux it never failed: 600 attempts in the app's Docker image on the same machine, and the owner's 600 attempts on a Linux machine.
- **Not OneDrive.** A OneDrive work folder exists, but none of the folders tried is inside it or carries cloud-file attributes. Defender's real-time scanning is on; that was only read, not changed.
- **The data is on disk, the open client is stuck.** After the error the same client kept failing, at once and 1, 6 and 36 seconds later. A newly opened client in the same process, and a separate process, read the same store without error, 3 times out of 3 (the failure at attempt 87 came before these checks were added).
- **Not established:** the cause inside Chroma, and whether an older version behaves better. 1.5.9 is the newest release. 1.4.1 could not be installed in a scratch environment: the download timed out repeatedly and then the file was "being used by another process".

**What changed.**
- **The store filters, the index scores.** The store interface's `nearest(queries, n, where)` became `candidates(where)`, the ids of the chunks that match a filter. Chroma answers it with a filtered fetch and the memory store with a plain filter. Similarity is worked out exactly by the index from the stored vectors, as it already was.

  Removed, because no longer used: the memory store's own scoring, Chroma's `query` call, the index's `EXTRA_CANDIDATES`, the `allowed` argument of `Index.meanings`, and the store test for "nearest first with its similarity".
- **Reopening a stuck client.** When reading the stored vectors or the matching chunks fails with exactly this error, `ChromaStore.reading` logs a warning, closes the client, opens a new one and reads once more. Any other error is raised unchanged, and so is this one if the new client fails too. A first attempt that only waited and tried again (3 tries over 0.6 seconds) was tested and removed: all three tries failed in the same run.
- **One limit, stated in the code.** Closing gives a fresh state only when no other client has the folder open. In the app there is one client per folder.

**Checked, free (`LLM_MAX_CALLS=0`).**
- **Stress loops** (the loop now stops at the first failure): the store tests passed 100 runs out of 100 and the full suite 30 out of 30 (441 tests each).
- **The reopen in action:** in 40 further runs of the store tests, a stuck client was reopened 2 times, not counting the 2 reopens per run that the tests cause on purpose, and both reads then succeeded.
- **Identical results:** the fingerprint of every chunk and every ranked result is unchanged from phase 2 with both stores. The 225 queries are identical to the last digit. Every question for the five dev tenders in the cache, at both depths, is byte-identical: 1,273 of 1,273, with the same counts of questions not in the cache as before.

**Tests.** 441 passed (438 before).
- The store tests now check `candidates` with every filter.
- New tests:
  - a stuck client is closed and a new one reads the store;
  - any other Chroma error is raised without reopening;
  - a store still stuck after reopening raises.

**Files to read.** `ChromaStore.reading` and `candidates` in `backend/app/vectorstore/chroma.py`, `backend/scripts/diagnose/chroma_repro.py`, and the Chroma paragraphs in `docs/architecture.md`.

## Upload screen and CI

**What changed.**
- **Upload screen.**
  - The manual category choice moved into a collapsed "Advanced" section, below the run name, labelled "Product category (optional)". It still defaults to "Find it in the tender".
  - When the model call limit is 0, the cost note is replaced by "This demo replays saved examples only." With any other limit the note is as before (answers found before cost nothing, at most N calls per run, an estimate before anything is spent).
- **CI** (`.github/workflows/ci.yml`, on every push and pull request):
  - Three jobs: backend (pytest on Linux), frontend (vitest and `vite build`), images (both Docker builds, after the other two pass).
  - `LLM_MAX_CALLS: "0"` is set for the whole workflow, so no job can call the model. The tests need no embedding model download, checked offline, so nothing is cached for it.
  - A CI badge is at the top of the README.
  - The actions are pinned to exact releases at least two weeks old, all on Node 24: `actions/checkout@v7.0.1` (20 July 2026), `actions/setup-python@v7.0.0` (20 July 2026; v7.1.0 came out on 22 October, too new) and `actions/setup-node@v7.1.0` (8 October 2026). Only the version numbers changed. Exact tags, so a moving `@v7` tag cannot pull in a newer release.

**Why.**
- Most people should let the system find the category in the tender, so the manual choice is kept out of the way but still there.
- The demo runs with the limit at 0, where the old note promised a cost estimate that never comes. The new note says what the demo actually does.
- CI proves on every change that the tests pass on Linux without spending anything. The old action versions ran on Node 20, which GitHub has deprecated and was forcing onto Node 24.

**In an interview.** "The upload screen now leaves the category to the system by default and keeps the manual choice under Advanced, and when the call limit is 0 it says plainly that the demo replays saved examples. Every push and pull request runs the backend tests, the frontend tests and both Docker builds on GitHub, with the model call limit at 0 so CI can never spend money. The actions are pinned to exact releases that have been out at least two weeks, which removed GitHub's Node 20 warning without changing anything else."

**Checks.** Free, with `LLM_MAX_CALLS=0`.
- Frontend: 76 passed (74 before).
  - The upload test now checks that the category choice is inside a closed Advanced section, under the new label, defaulting to "Find it in the tender".
  - New: with the limit at 0, only the replay note shows.
  - New: a category chosen under Advanced is sent with the run.
  - The accessibility check of the upload page still finds no violations.
- `vite build` succeeds.
- CI after the version change: backend, frontend and images all passed on the push run and the pull request run. The only warning left is GitHub's general notice that `ubuntu-latest` is moving to Ubuntu 26.

**Files to read.** `frontend/src/pages/UploadPage.jsx`, the upload tests in `frontend/src/app.test.jsx`, `.github/workflows/ci.yml`.

## Replay-only demo for a Hugging Face Space (branch `demo-space`)

**What changed.**
- **`Dockerfile.demo`** at the repository root builds one image that serves the backend and the built frontend on port 7860.
  - It holds no API key and sets `LLM_MAX_CALLS=0`.
  - Its own ignore file, `Dockerfile.demo.dockerignore`, lets in only the five sample tenders' folders (and `sources.csv`), which the other images leave out, and keeps every `.env` out. A test checks that these folders are exactly the samples in `data/demo_runs/runs.json`.
  - The build fails if any file in the image has an email address in its name. One tender attachment does (in 9789486, not a sample, so not in the image). It is not renamed in the repository: tender file names are part of the model prompts, so renaming it would make that tender's saved answers miss.
- **`app/demo.py`** wraps the usual service:
  - an upload (`POST /runs`) is refused with 403 and "This demo replays saved examples only." before anything is read, so no run starts;
  - deleting or renaming a run is refused with 403 and "The saved examples cannot be deleted or renamed in this demo.", because every visitor shares the samples. Reports, downloads and documents open as usual, and review decisions can still be saved;
  - the built page is served from `/`, after every API route, and calls the API at relative addresses.
- **Sample runs.** `scripts/demo/replay_samples.py` replays each tender in `data/tenders/sources.csv` from the shipped answers alone (an empty `CACHE_DIR`, a model that refuses every call, `LLM_MAX_CALLS=0`) and saves the reports in `data/demo_runs`. When the image is built, `scripts/demo/load_samples.py` stores them as finished runs, with the tender PDFs beside them.
- **Permissions.** Everything the service writes is in `/srv/demo`, owned by user 1000 (the user Hugging Face runs) and writable by any user. It is not under `/data`, where a Space mounts its persistent storage.
- **`docs/HF_SPACE_README.md`** is the Space's README, with its settings block (`sdk: docker`, `app_port: 7860`) and what the Space repository needs. The main README is unchanged.

**Why.** A free demo that anyone can open, which can never spend money and needs no key.

**In an interview.** "The demo is one container that serves the interface and the API together, with the model call limit at 0, no key, and uploads refused with a plain message. Its sample reports were replayed beforehand from the answers shipped in the repository, with a model that refuses every call, so they are exactly what the real pipeline produces and cost nothing. Five of the eleven recorded tenders replay completely; the other six need answers that were never saved, so they are left out rather than shown half done."

**Measured, free.**
- **Replay:** 5 of the 11 tenders in `sources.csv` replay with 0 model calls: 9933225 (64 saved answers), 9935891 (214), 9968695 (97), 9604147 (50), 10016383 (121). The other 6 (10010349, 9789486, 9840129, 9918524, 9995708, 9987635) each need at least one answer that is not shipped, so they are left out. No report has a budget note.
- **The six, with the local saved answers** (a copy of this machine's cache, still no model call): only 10010349 completes, needing 3 answers that are not shipped, and in its report neither of its two items has requirements, so nothing is scored. It is left out. The other five stop at an answer that was never saved: 9789486 after 306 saved answers, 9840129 after 141, 9918524 after 12, 9995708 after none, 9987635 after 88.
- **Image:** 1.27 GB. It runs as user 1000, with `LLM_MAX_CALLS=0`, no `.env` file and no key variable. Its tenders are the 9 PDFs of the 5 samples (1.1 MB), and no file name in it contains `@`.
- **In the running container (`docker run -p 7860:7860`):**
  - The page, its `config.js` and its assets load.
  - `/config` gives `max_model_calls: 0`. `/runs` lists the 5 sample runs, all done with 0 model calls.
  - Each report's JSON is identical to the saved one. Its Markdown and Excel downloads work.
  - Each run's tender PDFs open, and all 27 manufacturer documents open.
  - An upload gets 403 with the plain message, and no run is added. The log has no traceback.
- **In a browser** (headless Edge): the runs list, the report of 9933225 (7 manufacturers ranked) and the upload page with the replay-only note render.
- **Chroma and permissions:** as user 1000 and as an unrelated user (1234), a Chroma store opens and creates its collections in the cache folder, the runs database is writable, and saving review decisions works. With a read-only filesystem the app does not start, because it writes its runs database at start; Hugging Face's filesystem is writable.
- **Delete and rename, in the container:** for each of the 5 runs, delete and rename get 403 with the plain message, and the run list is unchanged afterwards. The report, its Markdown and Excel downloads and the review decisions still answer 200, and saving decisions works.
- **Upload screen, later change:** with the call limit at 0 the upload screen shows no note at all (it used to say "This demo replays saved examples only."). A visitor who tries an upload still gets the server's plain refusal, "This demo replays saved examples only.", shown as the error. With any other limit the cost note is unchanged.
- **Frontend:** the report page's Delete button now shows a refusal as a notice ("Could not delete: ..."), as the runs list already did, instead of doing nothing.
- **Tests:** backend 446 passed (441 before; `tests/api/test_demo.py` checks the upload refusal, the delete and rename refusal, that the normal app still deletes and renames, the page sharing the port with the API, and the sample folders let into the image). Frontend 78 passed (76 before; refusals show as plain text, on the upload page, the runs list and the report).

**Files to read.** `Dockerfile.demo`, `Dockerfile.demo.dockerignore`, `backend/app/demo.py`, `backend/scripts/demo/replay_samples.py`, `backend/scripts/demo/load_samples.py`, `docs/HF_SPACE_README.md`.

## Demo image on Docker Hub: `shravani1711/tender-matcher-demo:v6`

**What changed.**
- The replay-only demo image is published on Docker Hub as `shravani1711/tender-matcher-demo:v6`. Anyone can run it with `docker run -p 7860:7860 shravani1711/tender-matcher-demo:v6` and open http://localhost:7860.
- **How it was built.** From `Dockerfile.demo` at `main`'s commit `e1790a2` (the merge of PR #3), plus the three hold-out sample tender folders (`GeM-Bidding-9968695`, `GeM-Bidding-9604147` and `GeM-Bidding-10016383`) copied in from a working copy. Digest `sha256:13408dd8208f3e434c80f1c70b8d3c36d8036568fb45db32372cf2bfa8f437b1`, 1.27 GB. The image carries the commit as its `org.opencontainers.image.revision` label.
- **v5 is broken; do not use it.** `v5` (built from `main`'s `fc652f3`, digest `sha256:0664b310b69d6b8ce4175d70c586ee43ae2f43c71d9c746d613b4baf7ddbb72f`) was built from a clean checkout. The three hold-out tenders are not in git, so their PDFs are missing from it. For those three samples:
  - the tender page links answer 404;
  - the Tender layout tab answered 500, with a traceback.

  The reports themselves are fine. PR #3 fixed both sides: the layout now refuses plainly when a tender folder holds no PDF, and the build stops with a clear message when a sample folder is empty, so a build like v5's can no longer finish.
- **v4 is superseded.** `v4` (commit `985bdf4` on `demo-space`, digest `sha256:af3ccbec2fa850f1a72e2a83768cf8e107081d8657ce00d22d31ee1a25b263f7`) works, but it predates the Tender layout tab, the Add documents page and the other changes merged in PR #2.
- **v3** (commit `697ac5f`, digest `sha256:ee9955eb8b797d805985ae28b116f0569d7a07eaa4451319f56be921e30107e1`) was already superseded by v4, because it shows the old note on the upload screen.
- **Tags.** v3, v4 and v5 stay on Docker Hub unchanged. There is no `latest` tag for the demo, so a pull always names the exact version. The backend and frontend images are unchanged.

**Building it.** The three hold-out sample folders must be copied into `data/tenders/holdout/` before building, because `.gitignore` keeps them out of git (see `docs/HF_SPACE_README.md`).
- **Without them,** the build now fails at `load_samples`: "These sample tender folders hold no PDF: holdout/GeM-Bidding-9968695, holdout/GeM-Bidding-9604147, holdout/GeM-Bidding-10016383. …". This was checked by building `e1790a2` from a clean checkout.
- **With them copied in,** it builds and loads all 5 samples.

**Why.** The demo can be tried with one command, without building it or cloning the repository, and still never calls the model or needs a key.

**Checked, free.** All checks ran on the `v6` copy pulled back from Docker Hub, after deleting the local tag; the pulled digest matches the pushed one. All 29 checks passed:
- **Page and settings:** `/health` is ok, the page loads and calls the API on the same origin, and `/config` gives `max_model_calls: 0`.
- **The 5 samples:** `/runs` lists them all, done. For each of the 5:
  - the report's JSON is identical to its saved copy in `data/demo_runs`;
  - the Excel download works;
  - every cited tender page link answers 200;
  - the Tender layout tab answers. Families found: ball valve (10016383), submersible pump (9604147), butterfly valve (9933225), vertical multistage pump (9935891, 29 shared rows) and gate valve (9968695).
- **Refusals:** an upload, and adding a document, get 403 with "This demo replays saved examples only.". Deleting or renaming a sample gets 403 with "The saved examples cannot be deleted or renamed in this demo.", and the 5 runs are unchanged afterwards.
- **Logs:** no traceback, and no line from the model client. The only 4xx answers are those four refusals.

**In an interview.** "The demo is a public Docker image with exact version tags and no latest. v5 taught me something: I built it from a clean checkout, and three sample tenders that are deliberately kept out of git went missing. My check of the pulled image caught it before anyone relied on it. I fixed the app to refuse plainly, and made the build fail loudly when a sample has no PDF. Then I shipped v6 and re-ran every check on the pulled copy."

**Files to read.** `Dockerfile.demo`, `backend/scripts/demo/load_samples.py`, `docs/HF_SPACE_README.md`.

## Embedder and retriever behind interfaces, and a semantic chunker

**What changed.**
- **Embedding** (`backend/app/embedding/`):
  - `base.py` (new) holds the `Embedder` interface: a `name` and an `embed(texts)` method.
  - `embedder.py` now lists the embedders by name (`EMBEDDERS`) and picks one with the `EMBEDDER` setting. The default is `bge-small`, the same fastembed model as before (`BAAI/bge-small-en-v1.5`), loaded only on first use.
  - `embed_cache.py` keys each saved vector by the chosen embedder's name and the text. For the default this is the key every vector was always saved under, so the shipped `data/seed_embeddings.sqlite` still matches.
  - Another embedder's Chroma store goes in its own folder (`chroma-<name>`), because its vectors can have another length. The embedder's name is also part of the settings a stored file is checked against.
- **Retrieval** (`backend/app/retrieval/`):
  - `base.py` (new) holds the `Retriever` interface (`name`, `chunks`, `vectors`, `search`, `search_many`), with `Hit` and `Mode` moved there.
  - `retrievers.py` (new) lists the retrievers by name and picks one with the `RETRIEVER` setting: `hybrid` (the default, the search as before), `keyword` or `meaning`. All three are the existing `Index` with a fixed way of searching. A search can still ask for another mode, as `eval_retrieval` does.
  - `open_index` returns the chosen retriever. The pipeline, the budget, evidence and routing are typed against the interface, not the class.
- **A semantic chunker**, `backend/app/chunking/strategies/semantic.py`, is a sixth strategy, chosen only with `CHUNKER=semantic`:
  - Each page is split into its text blocks, or into paragraphs for a page read from a picture. Every block of a document is embedded in one go, through the embedding cache.
  - Neighbouring blocks on a page stay in one chunk while they are alike. A cut is made at the document's least alike quarter of neighbours, and before a chunk passes 1,000 characters.
  - A chunk never spans two pages, so it always has one page to cite. The router (`auto`) never picks it.
- The README settings table and `docker-compose.yml` list `EMBEDDER` and `RETRIEVER`. `docs/architecture.md` describes the interfaces.
- `docs/NEEDS_PAID_RUN.md` no longer opens with "Nothing here has been run": it says checks 1 and 2 were run (≈ ₹59.78) and check 10 was answered for free.

**Why.** The review found two gaps (`docs/FEEDBACK_STATUS.md`):
- embedding and retrieval could not be swapped the way chunking and the vector store could;
- the reviewers' list of chunking approaches included semantic chunking, which did not exist.

**The defaults did not change, measured free.** These were taken before the change and again after it, with `LLM_MAX_CALLS=0`:
- **Fingerprint:** every chunk, every vector and every ranked result through `open_index`, the app's own path, for both categories (1,714 valve and 2,099 pump chunks). That is 127 queries (the 7 retrieval cases and 120 catalogue headings), for every manufacturer, in each search mode and with the mode left to the default. Every hash is identical.
- **`estimate_cost` output, byte for byte identical:**
  - 9933225: 56 of 56 questions already answered.
  - 9935891: 204 of 204.
  - 9840129: 133 questions, 10 answered, 123 new, about 606,094 input tokens, the same as in phase 5.
- **A one-time re-read.** The chunking code changed, so a Chroma store made before re-reads every catalogue once, as designed. It is only a cache, the chunks come out the same, and nothing is asked of the model.

**Measured, free: `eval_retrieval` for every strategy.** All were run again after the change, one after another on the same Chroma folder. The six older ones give the same top-5 figures as recorded in phase 2 and its follow-up.

Valve catalogues, 7 cases:

| strategy | top 5 (keyword, meaning, hybrid) | first result (keyword, meaning, hybrid) |
|---|---|---|
| `table_rows` (default) | 6/7, 4/7, 6/7 | 4/7, 3/7, 4/7 |
| `recursive` | 7/7, 5/7, 5/7 | 5/7, 3/7, 5/7 |
| `sections` | 6/7, 3/7, 3/7 | 4/7, 2/7, 3/7 |
| `parent_child` | 7/7, 5/7, 6/7 | 5/7, 4/7, 3/7 |
| `structure` | 6/7, 4/7, 6/7 | 4/7, 3/7, 4/7 |
| `auto` | 7/7, 5/7, 6/7 | 4/7, 3/7, 4/7 |
| `semantic` (new) | 7/7, 6/7, 6/7 | 6/7, 5/7, 6/7 |

The invented documents (`data/eval/samples`), 10 cases:

| strategy | top 5 (keyword, meaning, hybrid) | first result (keyword, meaning, hybrid) |
|---|---|---|
| `table_rows` (default) | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `recursive` | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `sections` | 10/10, 10/10, 10/10 | 9/10, 8/10, 9/10 |
| `parent_child` | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| `structure` | 10/10, 10/10, 10/10 | 9/10, 9/10, 10/10 |
| `auto` | 10/10, 10/10, 10/10 | 9/10, 9/10, 10/10 |
| `semantic` (new) | 10/10, 9/10, 10/10 | 9/10, 7/10, 9/10 |

How to read this:
- **The valve gain is real but small.** On the valve catalogues, `semantic` puts a right page first more often than any other strategy: hybrid 6 of 7 against 4 of 7 for the default. It finds "nominal pressure PN 16" at KSB first instead of fourth, and Duncan's "pressure rating PN 16" first where the default's hybrid search missed it. But it loses KSB's "can the valve be used at 16 bar", which the default found in fifth place. Seven cases are too few to call one strategy better.
- **Its chunks are very short:** the valve catalogues give 2,361 chunks with a median of 42 characters, against 1,714 with a median of 329 for the default. Short chunks match a short query sharply, which helps these checks, but the model would read 16 short passages per question, far less text around each fact. Whether that gives better or worse final answers is what a paid run would show.
- **It was not tuned.** The one setting, cutting a quarter of the neighbours, was chosen once before measuring.
- **On the invented documents it does no better than `structure`.** Those documents were written for `structure`.

**What did not change.** No default, prompt, chunk, search result or saved answer. `CHUNKER` is still `table_rows`, `EMBEDDER` is `bge-small` and `RETRIEVER` is `hybrid`.

**Not measured.** Final answers with `semantic`, another embedder or another retriever: every question would be new, so these need paid runs. The free estimate for `semantic` on 9933225 is 56 new questions of 56, about 219,527 input tokens by characters / 4, so ≈ ₹33 with the scaling used in `docs/NEEDS_PAID_RUN.md` (added there as check 11). No second embedder is listed, because adding one means downloading a model and making every saved vector and question new.

**Tests.** 465 passed (446 before):
- `tests/chunking/test_semantic.py`, 8 tests: blocks on one topic kept together and a change of topic cut, never across pages, the cut judged against the document, the size limit, pages read from a picture, one embedding call per document, an empty document, and never the default nor picked by the router.
- `tests/embedding/test_embedders.py`, 6 tests:
  - the default's name and the old key of a vector;
  - a shipped vector found under the default embedder;
  - the model not loaded when an embedder is chosen;
  - an unknown embedder refused;
  - a new embedder as one line, with vectors of its own;
  - its own Chroma folder.
- `tests/retrieval/test_retrievers.py`, 5 tests: the default is the hybrid search with the same ranking, the one-ranking retrievers, an unknown one refused, and a new retriever as one line.
- `tests/embedding/test_embed_cache.py` now passes an embedder object instead of a function, and the strategy registry test lists `semantic`.

**In an interview.** "Chunking and the vector store already sat behind interfaces, so I gave embedding and retrieval the same shape: an interface, a list of implementations by name, and a setting whose default is the original. I proved nothing moved by hashing every chunk, vector and ranked result, and the cost estimates, before and after, and all were identical. I also added a semantic chunker that cuts where neighbouring blocks stop being alike. It ranked a right page first more often on my seven valve cases, but its chunks are tiny, so I kept the default and wrote down the paid check that would settle it."

**Files to read.** `backend/app/embedding/base.py` and `embedder.py`, `backend/app/retrieval/base.py` and `retrievers.py`, `backend/app/chunking/strategies/semantic.py`, `backend/tests/chunking/test_semantic.py`.

## Add documents in the web app, and OCR in more languages

**What changed.**
- **The page reader is a setting** (`backend/app/reading/ocr/`, which replaces `ocr.py` and `ocr_compare.py`):
  - `model.py` is the old reader: the model transcribes the page, with the same prompt. `prompt_for` adds one sentence ("The page may be printed in Hindi or Marathi: write that text in its own script.") only when other languages are asked for.
  - `local.py` is new: EasyOCR on this computer, loaded on the first page, one page at a time. Devanagari digits (१६) are written as 0 to 9.
  - `readers.py` lists the readers by name and picks one with `OCR` (`model`, the default, or `easyocr`), in the languages of `OCR_LANGS` (`en`, the default; `hi` Hindi; `mr` Marathi; codes separated by commas). Every script and job still calls `reader_for(llm)`, so the setting reaches them all.
  - A reader other than the default is added to the settings a stored file is checked against (`;ocr=easyocr:en,hi`), so a store never mixes two readers' chunks. For the default nothing is added.
  - `compare.py` is the old `ocr_compare.py`.
- **Add documents, a page in the web app** (`frontend/src/pages/DocumentsPage.jsx`, in the side bar):
  - choose the category and the manufacturer (from the list, or a new name), then upload a PDF, with the web address it came from if known, or give the address of a PDF;
  - the page says what was added, the date recorded and how many passages are now searchable.
- **Its route**, `POST /categories/{category}/documents` (`backend/app/api/documents.py`), uses the collector's own code (`backend/app/collecting/add.py`):
  - a download goes through the crawler's polite fetcher (`robots.txt`, a pause);
  - the file is saved by `save_pdf`, which now takes a name, so the same content is never saved twice, even under another name;
  - a line goes into `data/categories/sources.csv` (`record_by_hand` in `sources.py`) with the source and date, or "source not given".
  - Refused, with nothing saved: an unknown category (404); a manufacturer name that is not lower-case letters, digits, `-` and `_` (400); not a PDF (400); both or neither of a file and an address (400); a source that is not a web address (400); a site that does not answer or forbids it (502); the same content again (409).
- **One ingest.** After saving, the route calls `add_to_search` (`backend/app/pipeline/runner.py`), which runs the existing `ingest` with the page reader a run uses. So the store already holds the file, under the same settings, when the next run opens the category. The model is only made if a page is a picture and `OCR=model`. If reading fails, the file stays saved and recorded, the page says why, and the next run tries again.
- **The replay-only demo refuses it** with the same plain message as an upload (`backend/app/demo.py`).
- README: two settings rows, a paragraph on adding documents, two lines in "What's new". `docs/architecture.md`: the overview, the ingest path, the package table and two design decisions.

**Why.** The reviewers' point 9 asked for a tool to collect manufacturer documents from the web, and an OCR path that works for more languages. `docs/FEEDBACK_STATUS.md` had marked the first partly done (it was only a script) and the second not done.

**Does the current OCR use the model?** Yes. Pages that are only a picture were, and by default still are, transcribed by Gemini, one paid call per page, with the transcription saved. It stays the default because every saved answer was made from those transcriptions.

**The defaults did not change, measured free.** These were taken with `LLM_MAX_CALLS=0` against the files saved before this batch:
- **Fingerprint:** every chunk, vector and ranked result through `open_index` for both categories. Every hash is identical.
- **`estimate_cost` output, byte for byte identical:** 9933225, 56 of 56 answered; 9935891, 204 of 204; 9840129, 133 questions, 123 new, about 606,094 input tokens. These estimates read the scanned pages through `reader_for` and the saved transcriptions, so the model's prompt is unchanged.
- **A one-time re-read.** The reading code moved into `reading/ocr/`, so a Chroma store made before re-reads every catalogue once. The chunks come out the same, and no model is asked.

**Measured, free.**
- **Generated pictures** (in `backend/tests/ocr/test_ocr_languages.py`): EasyOCR reads one line each of Hindi ("दबाव रेटिंग 16 बार"), Marathi ("पाण्याचा पंप 50 मिमी") and English word for word, and a scanned PDF page with all three through `read_pdf`.
- **Real bilingual scans.** Tender 9918524 has a BHEL specification whose 6 scanned pages mix Hindi and English. Against the model's saved transcriptions of those pages:

  | EasyOCR languages | Hindi words found | numbers found | English words found (mean) |
  |---|---|---|---|
  | `en,hi` | 25 of 89 (28%) | 148 of 254 (58%) | 76% |
  | `en` | 0 of 89 | 167 of 254 (66%) | 76% |

  EasyOCR misses most of the Hindi on real scans, and asking for Hindi loses numbers. The model's transcription is the reference, not a checked truth. 70 other scanned tender pages have no Devanagari in their saved reading.
- **A real download through the route.** Intervalve's portfolio, from the address recorded in `sources.csv`, was fetched into a scratch folder with the real fetcher, ingest, embedder and an empty scratch cache. It arrived byte for byte identical to the shipped copy (1,919,055 bytes), was recorded with its source and date, and gave 20 searchable passages. Its pages that are only a picture were read from the shipped saved transcriptions, so no model call was made.
- **Uploads through the route,** with the real ingest: a text PDF was the first result of a search for its words, and a scanned Hindi page with `OCR=easyocr` was read and stored with no key and no model call.

**Not measured.**
- **EasyOCR end to end.** The free estimate of what `OCR=easyocr` would make new on 9933225 was stopped by Claude Code before it finished, because the computer ran low on memory. It was not run again. The command to price it is in `docs/NEEDS_PAID_RUN.md` (check 13).
- **The language hint on the model.** It needs new transcriptions: check 12, 6 calls, about ₹1.13.
- **Hindi or Marathi beyond reading.** Keyword search drops Devanagari words, the embedder is English, and judging knows only English words and units.

**What did not change.** No default, prompt, chunk, search result or saved answer. `OCR` is `model` and `OCR_LANGS` is `en`. EasyOCR is optional and not in `requirements.txt` or the Docker images, because it brings PyTorch (about 1 GB). No Docker image was rebuilt.

**Tests.** Backend 498 passed (465 before); frontend 83 passed (78 before).
- `backend/tests/ocr/test_ocr_readers.py`, 7 tests:
  - the default prompt unchanged;
  - the language sentence;
  - unknown readers and languages refused;
  - EasyOCR not loaded before a page, with plain digits;
  - a clear message when EasyOCR is missing;
  - the store key;
  - a new reader as one line.
- `backend/tests/ocr/test_ocr_languages.py`, 4 tests: real EasyOCR on generated Hindi, Marathi and English pictures and a scanned page. These are skipped unless EasyOCR and its Devanagari model are installed.
- `backend/tests/collecting/test_add.py`, 11 tests:
  - saved and recorded with source and date;
  - no source;
  - a new manufacturer;
  - the same content twice;
  - what is refused;
  - downloads through the fetcher;
  - names ending in `.pdf`;
  - found by a search after the one ingest;
  - a scanned page read by the run's reader.
- `backend/tests/api/test_add_documents.py`, 10 tests (upload, address, six refusals, a second copy, a reading that fails), and one more in `test_demo.py`.
- `frontend/src/documents.test.jsx`, 5 tests: the side-bar link, upload with source, an address for a new manufacturer, the server's refusal and a failed reading, and no axe violations.
- `test_ocr_compare.py` moved to `backend/tests/ocr/`.

**In an interview.** "The scanned-page reader was the model, so I made it a setting and added EasyOCR as a free local reader that reads Hindi and Marathi. It passes on pictures I generated, but on six real bilingual scans it found only 28% of the Hindi words the model did, so the model stays the default. I also added a page that adds a manufacturer document by upload or address. It uses the crawler's own fetcher and saver, records the source in `sources.csv`, and calls the same ingest as everything else. A real download came out byte for byte identical to the shipped copy."

**Files to read.** `backend/app/reading/ocr/readers.py` and `local.py`, `backend/app/collecting/add.py`, the add route at the end of `backend/app/api/documents.py`, `add_to_search` in `backend/app/pipeline/runner.py`, `frontend/src/pages/DocumentsPage.jsx`.

## Paid check 12: the model told to expect Hindi, and the optional OCR packages

**OCR packages are optional, checked.**
- `backend/requirements.txt`, used by `backend/Dockerfile` and `Dockerfile.demo`, names no OCR package.
- A dry-run install of it in a fresh scratch venv resolves 106 packages, with no PyTorch, EasyOCR, RapidOCR or OpenCV among them.
- With those imports blocked, the app and the demo app start and answer, and `OCR=model` reads a picture page with the prompt unchanged. `OCR=easyocr` only fails, on first use, with "OCR=easyocr needs EasyOCR: pip install easyocr".
- Nothing had to move. No image was rebuilt.

**Check 12 was run, with the owner's approval.**
- The six commands written in `docs/NEEDS_PAID_RUN.md` were run for pages 1, 3, 4, 5, 6 and 7 of tender 9918524's BHEL specification, with `OCR_LANGS=en,hi` and the call cap at 7 for that run only. The cap in effect afterwards is 0.
- **Actual cost:** 6 calls, no retries. 7,350 input and 4,541 output tokens, ≈ ₹1.19 at the app's rate (estimated ≈ ₹1.13), about $0.023 at Google's listed prices.

**Result.**
- With the hint, the model wrote the Hindi much more fully: on page 7, a sideways form, the whole form instead of four names.
- Judged against the scans, the new reading is closer to the print on 4 of 6 pages, about even on 1, and worse on 1, where it added labels that are not printed.
- The English and numbers stayed: 241 of 254 numbers.
- The page-by-page table is in `docs/NEEDS_PAID_RUN.md`.

**Nothing in the app changed.** `OCR_LANGS` stays `en`, and the new readings sit only in the local answer cache. The Hindi on these pages is labels and sign-offs, not requirements.

**In an interview.** "I spent about one rupee to check one thing: does telling the model to expect Hindi change its reading of real bilingual scans? It did. The Hindi came out far more complete and closer to the print on four of six pages, with the English and numbers kept. It also showed the model sometimes adds labels that are not printed. Since that Hindi was form labels, not requirements, I kept the default."

## Product families and the tender layout in the app; the token counter checked against Google's documentation

**The token counter: stopped, as asked.** Before wiring anything, Google's documentation was checked for whether `countTokens` is free on the Gemini Developer API, the one this app uses with an API key. It does not say so:
- **The token-counting page** (`aistudio.google.com/docs/tokens`, where `ai.google.dev/gemini-api/docs/tokens` now leads) has only "When billing is enabled, the cost of a call to the Gemini API is determined in part by the number of input and output tokens".
- **The billing page** (`aistudio.google.com/docs/billing`) has "Requests to the `GetTokens` API are not billed, and they don't count against inference quota". It does not say that `GetTokens` is `countTokens`.
- **The pricing page** does not mention token counting.
- **Only the Vertex AI documentation**, a different product with other keys and endpoints, says "There is no charge or quota restriction for using the `CountTokens` API".

So nothing was wired or tested, no request was sent, and `TOKEN_COUNTER` stays `estimate` (characters / 4). The known gap stays as measured before: the estimate is 74% (valves) and 69% (pumps) of the real input tokens in the saved answers.

**What changed.**
- **Product → family → attribute links** (`backend/app/graph/products.py`):
  - **New fields.** Each `category.json` has two new optional fields: `attributes`, what any product of the category is described by, and `families`, each with the words that name it and its own attributes.
  - **Valves:** butterfly, gate (also "sluice"), globe, check ("non return", "NRV") and ball.
  - **Pumps:** submersible, horizontal centrifugal, vertical multistage, end suction and process.
  - **Where they came from.** The families are the shipped catalogues' product ranges, as listed in `sources.csv`. The attributes are names the saved tender readings use: a scan of the 9 saved readings, made with `LLM_MAX_CALLS=0`, answered 142 from the cache and made 0 calls.
  - **Finding an item's family:** from a whole word in its title, or else in the value of its type attribute ("valve_type: gate").
- **The tender layout in the app** (`backend/app/graph/layout.py`, `GET /runs/{id}/layout`, and the report's new **Tender layout** tab, `frontend/src/components/report/TenderLayout.jsx`):
  - it shows each item, its family and how it was found, its printed rows with links to the tender page, the other items that share each row, the requirements each row splits into, and the standards cited, with their other names and the standards named with them;
  - it lists, folded away, the attributes `category.json` lists for that kind of product that the reading does not name;
  - the tab loads only when opened.
- **It cannot ask the model.** The layout is built from the run's tender files and saved answers only, through `saved_answers_only()` (`backend/app/llm/llm_factory.py`):
  - it stands in for Gemini with the same model and settings, so the same cache keys, but with no key and a call limit of 0;
  - Gemini and the stand-in now take those settings from one function, `cache_settings()` in `gemini.py`, and the key text is unchanged;
  - a tender whose reading is not saved gets "This tender's reading is not saved yet, so its layout cannot be shown without asking the model."
- README: the two new fields, the tab and "What's new". `docs/architecture.md`: the graph row, the overview diagram, a design decision, and the token-counter finding.

**Why.** The reviewers' point 9 named "product to family to attribute links" and the "tender hierarchy". `docs/FEEDBACK_STATUS.md` had recorded that the first did not exist and the second was only a script.

**Defaults and saved answers did not change, measured free.**
- **No prompt reads the new fields.** Only `extraction_rules` reaches a prompt, and the pump rule is byte for byte the same; a test checks that no family name or attribute list reaches the prompt.
- **`estimate_cost` output is byte for byte identical** for 9933225, 9935891 and 9840129, against the files saved before.
- **No reading or chunking code changed,** so no store is re-read.
- **`KNOWLEDGE_GRAPH` is still `off`, and judging is untouched.**

**Measured, free.**
- **Every demo sample has a layout.** All 5 were loaded as the demo image loads them, with an empty local cache, so only the shipped saved answers were used, and each answered 200:

  | Sample | Items | Requirements | Shared rows | Family (found by) |
  |---|---|---|---|---|
  | 9933225 | 1 | 11 | 0 | butterfly valve (title) |
  | 9935891 | 2 | 82 | 29 | vertical multistage pump (type value), both items |
  | 9604147 | 2 | 13 | 0 | submersible pump (title), both items |
  | 9968695 | 1 | 15 | 0 | gate valve (title) |
  | 10016383 | 1 | 21 | 0 | ball valve (title) |

- **9840129:** 4 gate valves, one named in its title and three ("VALVE MOTORISE …") by their type value. 15 rows are shared, and 4 standards are cited, with their other names (API 598 also written "API-598").
- **9918524** has no saved reading, so it gets the refusal, with no call.

**Not done, honestly.**
- **"Not named" compares names exactly,** and the model names attributes freely. On 9933225 it lists `pressure_rating` while the tender asks `nominal_pressure`, so it is a pointer for a person, not a finding.
- **Families seen only in catalogues have no attributes of their own:** globe, check, vertical multistage, end suction and process.
- **No score uses families or attributes.**

**Tests.** Backend 509 passed (498 before); frontend 86 passed (83 before).
- `backend/tests/graph/test_products.py`, 6 tests:
  - links and where they were seen;
  - title first, then type value;
  - whole words only;
  - the shipped categories;
  - no prompt reads the new fields;
  - a tender with no saved reading is refused, and the stand-in is never called.
- `backend/tests/graph/test_tender_layout.py`, 4 tests: items and shared rows, each item showing only its own requirements; families and names not used; standards; the stand-in's cache key equals Gemini's.
- `backend/tests/api/test_api.py`: the layout route, its refusal (409) and an unknown run (404).
- `frontend/src/app.test.jsx`, 3 tests: the tab's content and links, fetched only when opened with the refusal shown plainly, and no axe violations.

**In an interview.** "I checked Google's documentation before touching the token counter. It says counting is free only for Vertex AI, not for the API key this app uses, so I stopped there, as agreed. For the knowledge graph, I put product families and their attributes in each category's config and linked them. The tender's structure is now a report tab, built from saved answers through a stand-in that has Gemini's cache keys but cannot call it. It even works in the replay-only demo."

**Files to read.** `backend/app/graph/products.py` and `layout.py`, `saved_answers_only` in `backend/app/llm/llm_factory.py`, `data/categories/*/category.json`, `frontend/src/components/report/TenderLayout.jsx`.

## Chroma as the only store of vectors, and Chroma's own ranking as an option

**What changed.**
- **Chroma is the only store of vectors.** The store gained two collections (`backend/app/vectorstore/chroma.py`):
  - `vectors`: every text's vector, chunks and search queries alike, keyed by `key_for(text, model)` as before, and looked up by key, never searched;
  - `imports`: which files were imported into it.

  `backend/app/embedding/embed_cache.py` no longer opens SQLite; it reads and writes through a cache object, the Chroma one (`backend/app/vectorstore/vector_cache.py`) unless a test gives another.
- **The seed is a one-time import.** The first time anything is embedded, the shipped `data/seed_embeddings.sqlite` is copied into Chroma and recorded by its SHA-256, and so is this machine's older `backend/.cache/embeddings.sqlite` if it exists. After that, no vector is read from either; a changed seed would be imported again. On this machine: 6,126 seed vectors and 23,603 local ones, which already held all 6,126 seed vectors, byte for byte the same. The old file is left on disk, unused, and can be deleted.
- **Chroma can rank: `VECTOR_SEARCH=chroma`** (`backend/app/retrieval/search.py`).
  - The meaning ranking comes from Chroma's own nearest-neighbour search, in Chroma's order, through a new `nearest()` that both stores have.
  - BM25 and rank fusion are unchanged.
  - The chunk collection is built for near-exact search: inner product, `ef_construction` 512, `max_neighbors` 64, `ef_search` 10,000, so the search can look at every chunk at these sizes.
  - A store made before with Chroma's defaults (`ef_construction` 100, `max_neighbors` 16) is rebuilt once. It is a cache, and the documents are read again for free.
  - The default stays `exact`.
- **`backend/scripts/diagnose/compare_vector_search.py`** compares the two rankings. `VECTOR_SEARCH` is in `docker-compose.yml` and the README settings table.

**Why.** The reviewers asked for a proper vector database instead of embeddings in a plain structured database. Vectors were kept in SQLite, and Chroma was filled from that and used only to store and filter (`docs/FEEDBACK_STATUS.md`, point 4).

**Measured, free (`LLM_MAX_CALLS=0`): is Chroma's ranking identical to the exact one? No.**
- **A first probe, on the store made before:** even with `ef_search` raised to 10,000, Chroma never returned one of KSB's 1,621 pump chunks, so the old graph could not reach it. With the dense graph above, no chunk is missing.
- **The fingerprint's index** (the catalogues read without their scanned pages, as the default-results fingerprint reads them): 127 queries, for each of the 8 manufacturers with chunks there, in keyword, meaning and hybrid modes.
  - **The 16 passages a question reads** differ in 3 of 3,048 comparisons: "Dimensional sketch" (meaning), and "Example: WS_25_LS" (meaning and hybrid), all for Grundfos. Each time, `cr-databooklet-50hz.pdf` prints the same table row on pages 75 and 79, so the two chunks have identical text and vectors and tie exactly. The exact search keeps the chunks' order and cites page 79; Chroma cites page 75.
  - **The whole meaning ranking** of the manufacturer's chunks differs in 203 of 1,016.
- **The app's own index** (scanned pages read from the saved transcriptions, with no model allowed): 127 queries, for each of the 11 manufacturers, in the same 3 modes.
  - **The 16 passages** are the same in all 4,191 comparisons.
  - **The whole meaning ranking** differs in 161 of 1,397. These are near-ties: the probe found score gaps of 6e-8 to 1.5e-7, a float rounding apart. Chroma's arithmetic differs from NumPy's in the last digits, up to 3e-7 here.
- **`eval_retrieval`:** the output is byte-identical with `exact` and `chroma`, on the 7 valve cases (top 5: keyword 6/7, meaning 4/7, hybrid 6/7) and on the 10 invented-document cases (10/10 each).
- **So it stays an option.** A different cited page changes the question and misses its saved answer, so `exact` stays the default. In the 3 cases that differ, the cited pages hold the same text, so for a reader nothing differs.

**The defaults did not change, measured free.**
- **Fingerprint:** every chunk, vector and ranked result through `open_index`, for both categories, is identical, with every vector now read from Chroma.
- **`estimate_cost` output is byte for byte identical** for 9933225, 9935891 and 9840129. 9935891 is also identical with the old SQLite file moved away, and no new SQLite file was written.
- **No test touches this machine's store.** A guard that fails any test using the real vector cache passed the whole suite; every test uses its own folder.

**Tests.** Backend 520 passed (513 before).
- `backend/tests/vectorstore/test_vector_cache.py`, 6 tests:
  - the seed and the old cache imported once, with last digits read back exactly;
  - a changed seed imported again;
  - new text kept in Chroma, with no SQLite file written;
  - both stores rank for the index;
  - native scoring with BM25 and fusion kept, and an unknown setting refused;
  - the HNSW settings, and an older store rebuilt empty.
- `backend/tests/embedding/test_embed_cache.py` now uses a cache object (5 tests), and the embedder tests read the seed directly.

**In an interview.** "I made Chroma the only place vectors live: the shipped seed is imported once, and the old SQLite cache is gone. I proved nothing moved by hashing every chunk, vector and ranking, and the cost estimates, before and after. I also let Chroma do the ranking, tuned to look at every chunk. It agreed on 4,191 of 4,191 top-16 results on the app's index, but on another set two chunks with identical text tied and Chroma cited the other page, and the full rankings differ in near-ties. So it is an option, and exact scoring stays the default."

**Files to read.** `backend/app/vectorstore/vector_cache.py` and `chroma.py`, `backend/app/embedding/embed_cache.py`, `meanings` in `backend/app/retrieval/search.py`, `backend/scripts/diagnose/compare_vector_search.py`.

## A shared tie-break, and a reranker stage

**What changed.**
- **A shared tie-break.** `by_score` (`backend/app/retrieval/search.py`) orders the meaning ranking, best score first, an exact tie by the chunks' original order. Both `VECTOR_SEARCH=exact` and `VECTOR_SEARCH=chroma` use it. Before, the Chroma path kept Chroma's own order.
- **A reranker stage, `RERANKER`, default `none`** (`backend/app/retrieval/rerankers.py`, behind `Reranker` in `backend/app/retrieval/base.py`).
  - `minilm` has fastembed's `Xenova/ms-marco-MiniLM-L-6-v2` cross-encoder (about 80 MB, Apache-2.0) score the top `RERANK_TOP` passages (40) after the fusion, against each phrasing of the query, keeping the best score.
  - Those passages are put in its order, ties keeping the search's; then each file gets its share of the places as before.
  - fastembed was already installed for the embedder, so nothing new is installed. The model file downloads on first use, and is in no requirements file, Dockerfile or image (a test checks).
  - Of the cross-encoders fastembed offers (MiniLM-L-6 0.08 GB, MiniLM-L-12 0.12 GB, Jina tiny 0.13 GB, Jina turbo 0.15 GB, BGE base 1.04 GB, Jina v2 multilingual 1.11 GB), the smallest was chosen.
- `scripts/diagnose/compare_vector_search.py` can compare without the pictures of pages (the fingerprint's index) as well as with them.
- `RERANKER` is in the README settings table and `docker-compose.yml`.

**Measured, free: the tie-break does not make `chroma` identical, so `exact` stays the default.**
- **The 127 queries × every manufacturer × keyword, meaning and hybrid:**
  - **The app's own index:** the 16 passages a question reads are the same in all 4,191 comparisons, and 161 of 1,397 whole rankings differ.
  - **The fingerprint's index:** the same 3 of 3,048 still differ, all Grundfos: "Dimensional sketch" (meaning), and "Example: WS_25_LS" (meaning and hybrid). 203 of 1,016 whole rankings differ.
- **Why the tie-break cannot help there.** The two chunks (`cr-databooklet-50hz.pdf` pages 75 and 79, the same table row) have byte-identical vectors, and Chroma scores them identically, so the tie-break now puts page 75 first. But the exact path never sees a tie. NumPy's matrix product gives the two rows different last digits, 0.58814674 against 0.58814680 for "Dimensional sketch", depending on where each row sits in the matrix, so page 79 wins by one rounding step. Making the two agree would mean changing the exact path's arithmetic, and that path made every saved question.
- **The free cost estimates:**
  - **The default, `exact`:** byte-identical to before for 9933225, 9935891 and 9840129.
  - **`chroma`:** byte-identical for 9933225 and 9840129. On 9935891, 1 of the 204 questions is new: "Service: Continuous Duty" for Type-1 pump reads the same 16 passages, but two passages from the same catalogue page 10 swap places 9 and 10, so the question's text changes and its saved answer is missed.
- **`eval_retrieval`** gives the same output both ways, and the same as before, on both case sets.

**Measured, free: the reranker, `eval_retrieval` only.**

| | Right page in top 5 (keyword, meaning, hybrid) | Right page first (keyword, meaning, hybrid) |
|---|---|---|
| Valves, 7 cases, default | 6/7, 4/7, 6/7 | 4/7, 3/7, 4/7 |
| Valves, `RERANKER=minilm` | 7/7, 7/7, 7/7 | 7/7, 7/7, 7/7 |
| Invented documents, 10 cases, default | 10/10, 10/10, 10/10 | 9/10, 7/10, 8/10 |
| Invented documents, `RERANKER=minilm` | 10/10, 10/10, 10/10 | 8/10, 8/10, 8/10 |

- **Valves:** every case that changed moved the right page to first place. KSB "can the valve be used at 16 bar" went from not in the top 5 in any mode to first in all three. Duncan "pressure rating PN 16" (hybrid) went from not in the top 5 to first.
- **Invented documents, mixed:** "performance test standard ISO 9906" (meaning 2 → 1) got better. "booster pump impeller material" (hybrid 3 → 4) and "booster pump motor efficiency class" (keyword 1 → 3) got worse.
- **With the default, `none`,** the output is byte-identical to before.
- **Seven valve cases are few.** Whether final answers improve needs paid check 14 in `docs/NEEDS_PAID_RUN.md`: on 9933225, 55 of 56 questions would be new, about ₹38. The estimate for 9935891 was stopped by Claude Code when the computer ran low on memory, so it is not priced.

**What did not change.** No default, prompt, chunk, search result or saved answer. `VECTOR_SEARCH` stays `exact`, `RERANKER` is `none`.

**Tests.** Backend 526 passed (520 before). `backend/tests/retrieval/test_rerankers.py`, 6 tests:
- the default is none, and an unknown reranker is refused;
- choosing the cross-encoder does not load it;
- only the top passages are rescored, with the best phrasing, ties keeping the search's order;
- the index takes the reranker's order;
- exact ties are ordered by the chunks' original order in both paths;
- the model is in no requirements file or image.

**In an interview.** "I added a shared tie-break hoping Chroma's ranking would then match exactly. It didn't, and the reason was in NumPy: two identical vectors get scores a rounding apart in a matrix product, so the exact path never sees a tie. On real questions one of 204 changed order, so exact stays. I also added a cross-encoder reranker as an optional stage. It found the right page first in all seven valve checks against four, but only a paid run can say whether answers improve, and that is priced at about ₹38."

**Files to read.** `backend/app/retrieval/rerankers.py`, `by_score` and `search_many` in `backend/app/retrieval/search.py`, `backend/tests/retrieval/test_rerankers.py`.
