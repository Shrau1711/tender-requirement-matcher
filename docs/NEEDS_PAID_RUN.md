# Checks that need paid model calls

Nothing here has been run. Each entry says what it would measure, why it cannot be measured for free, and what it touches. Phase 7 adds cost estimates (from `python -m scripts.cost.estimate_cost`, which is free) so the owner can decide.

## Phase 2: chunking strategies, end to end

**What it would measure.** Whether a strategy other than `table_rows` changes the final answers (match scores against the answer keys in `data/eval/gold`), not just which pages are retrieved.

**Why it costs money.** The model is asked about the passages a strategy produces. A different strategy gives different passages, so the prompts differ from the saved ones and every question is a new model call. Free checks stop at retrieval: `eval_retrieval` and `eval_candidates` (see `docs/CHANGES.md`, phase 2).

**How to run it, once approved.** For each strategy worth testing, first get the free estimate with `CHUNKER=<name> python -m scripts.cost.estimate_cost <tender folder> <category dir>`, then run `CHUNKER=<name> python -m scripts.eval.eval_all ../data/tenders/dev ../data/categories` with `LLM_MAX_CALLS` raised to the number of new questions the estimate reports. The two labelled tenders are 9933225 (valves) and 9935891 (pumps).
