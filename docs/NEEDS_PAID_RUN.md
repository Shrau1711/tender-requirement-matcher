# Checks that need paid model calls

Nothing here has been run. Each entry says what it would measure, why it cannot be measured for free, and what it touches. Phase 7 adds cost estimates (from `python -m scripts.cost.estimate_cost`, which is free) so the owner can decide.

## Phase 2: chunking strategies, end to end

**What it would measure.** Whether a strategy other than `table_rows` changes the final answers (match scores against the answer keys in `data/eval/gold`), not just which pages are retrieved.

**Why it costs money.** The model is asked about the passages a strategy produces. A different strategy gives different passages, so the prompts differ from the saved ones and every question is a new model call. Free checks stop at retrieval: `eval_retrieval` and `eval_candidates` (see `docs/CHANGES.md`, phase 2).

**How to run it, once approved.** For each strategy worth testing, first get the free estimate with `CHUNKER=<name> python -m scripts.cost.estimate_cost <tender folder> <category dir>`, then run `CHUNKER=<name> python -m scripts.eval.eval_all ../data/tenders/dev ../data/categories` with `LLM_MAX_CALLS` raised to the number of new questions the estimate reports. The two labelled tenders are 9933225 (valves) and 9935891 (pumps).

## Phase 3: making Chroma the default vector store

**What it would cost.** Measured for free on the five dev tenders whose reading is in the cache, every question the pipeline would ask at both search depths (1,273 questions): 1,270 are identical with Chroma and 3 are not. Those 3 have the same passages in a different order, so their prompts differ and their saved answers no longer match. Asking them again is 3 calls, about 14,800 input tokens, about 2 rupees at the app's own rate (`RUPEES_PER_MILLION_TOKENS` = 100). One of the 3 is in tender 9935891, whose answers ship in the demo cache, so with Chroma that demo would no longer run fully at no cost until it is asked once.

**What it would measure.** Whether the 3 reordered questions get different answers, and so whether the match results change at all.

**How to run it, once approved.** `VECTOR_STORE=chroma python -m scripts.cost.estimate_cost <tender folder> ../data/categories/<category>` shows the new calls for free; then run the tender with `VECTOR_STORE=chroma` and `LLM_MAX_CALLS` set to that number. The tenders are 9840129 (valves, 2 calls) and 9935891 (pumps, 1 call).
