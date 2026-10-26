# Checks that need paid model calls

Nothing here has been run. Each entry says what it would measure, why it cannot be measured for free, and what it touches. Phase 7 adds cost estimates (from `python -m scripts.cost.estimate_cost`, which is free) so the owner can decide.

## Phase 2: chunking strategies, end to end

**What it would measure.** Whether a strategy other than `table_rows` changes the final answers (match scores against the answer keys in `data/eval/gold`), not just which pages are retrieved.

**Why it costs money.** The model is asked about the passages a strategy produces. A different strategy gives different passages, so the prompts differ from the saved ones and every question is a new model call. Free checks stop at retrieval: `eval_retrieval` and `eval_candidates` (see `docs/CHANGES.md`, phase 2).

**How to run it, once approved.** For each strategy worth testing, first get the free estimate with `CHUNKER=<name> python -m scripts.cost.estimate_cost <tender folder> <category dir>`, then run `CHUNKER=<name> python -m scripts.eval.eval_all ../data/tenders/dev ../data/categories` with `LLM_MAX_CALLS` raised to the number of new questions the estimate reports. The two labelled tenders are 9933225 (valves) and 9935891 (pumps).

## Phase 5: temperature at the model's default

**What it would measure.** Whether `LLM_TEMPERATURE=DEFAULT` (the model's own 1.0, which Google advises for Gemini 3 models) changes the answers against the answer keys, and whether any reply loops or repeats, compared with today's 0.

**Why it costs money.** The temperature is part of every saved answer's key, so with another value every question is new, including the ones that read the tender itself.

**How to run it, once approved.** `LLM_TEMPERATURE=DEFAULT python -m scripts.eval.eval_all ../data/tenders/dev ../data/categories` with `LLM_MAX_CALLS` raised. The free estimate cannot help here: it reads the tender first, and that reading is new too.

## Phase 5: a lighter, cheaper model

**What it would measure.** Whether a lighter Gemini model (one listed on Google's current pricing page; check it supports the thinking setting in use) keeps the answers good enough against the answer keys, and what it saves.

**Why it costs money.** The model is part of every saved answer's key, so every question is new.

**How to run it, once approved.** `LLM_MODEL=<model> python -m scripts.eval.eval_all ../data/tenders/dev ../data/categories` with `LLM_MAX_CALLS` raised. Compare with the saved results of the current model, tender by tender.

## Phase 5: how far the token estimate is from Gemini's own count

**What it would measure.** For each dev tender, the tokens of its new questions counted as characters / 4 (the default) and by Gemini's `count_tokens` (`TOKEN_COUNTER=gemini`), so the estimate shown before a run can be trusted or corrected.

**Why it is not free to run here.** Counting asks no question of the model, but it is a request to Google that needs the API key, and Google's token page does not say whether it is billed or rate limited. So it obeys `LLM_MAX_CALLS` like a model call, and with the limit at 0 it falls back to the estimate.

**How to run it, once approved.** `TOKEN_COUNTER=gemini LLM_MAX_CALLS=<number of new questions> python -m scripts.cost.estimate_cost <tender folder> ../data/categories/<category>`, then the same without `TOKEN_COUNTER`, and compare the two token figures. The questions themselves are only counted, never asked.
