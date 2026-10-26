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
- No tender here is mixed, so the split into several runs is tested with a fake router in `tests/api/test_api.py`, not measured on a real tender.

**Tests.** 398 passed (386 before): `tests/categories/test_categories.py` (configs, the optional file, the union, words first and documents for the rest, the documents not read when words decide), three API tests (one-category tender matched whole, two categories give two runs with their own tender copies, a routing failure is reported), `tests/pipeline/test_pipeline.py` (only the given items are kept, with a note), and the prompt test. Frontend: 74 passed (73 before), and `vite build` succeeds. `docker compose build` builds both images, and inside the backend image both categories load and the prompt hash matches.

**In an interview.** "Category knowledge used to be spread through the code: a word table, a filler word, a pump rule inside the prompt. Now each category is a folder with its documents and a small JSON file, and a tender's items are routed to categories by their product words, or by which category's documents they resemble most, so a mixed tender becomes one run per category. I checked that the prompt is byte-identical to before, so every saved answer still matches, and the routing put all 11 labelled items in the right category."

**Files to read.** `data/categories/pumps/category.json`, `backend/app/categories/config.py`, `backend/app/categories/routing.py`, `execute_routed` in `backend/app/pipeline/runner.py`, and the top of `backend/app/extraction/atomize.py`.
