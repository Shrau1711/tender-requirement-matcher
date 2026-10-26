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
