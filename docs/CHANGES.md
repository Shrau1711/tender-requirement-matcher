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
