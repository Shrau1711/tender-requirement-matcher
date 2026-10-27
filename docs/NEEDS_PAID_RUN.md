# Checks that need paid model calls

Nothing here has been run. Each check is priced below from free measurements, and each section after the table says what it would measure, why it cannot be measured for free, and how to run it once approved. Run every paid check one tender at a time with `scripts.eval.score_gold`, never `eval_all`: `eval_all` goes on to the other labelled tender and would spend there too.

## Prices and priorities

How the prices were worked out (phase 7, all free, `LLM_MAX_CALLS=0`):

- **Whole runs** (new model, new temperature): every question is new, including the tender's reading. Each saved answer records the input and output tokens Gemini reported, so the cost is what the same run really used at today's settings, read from the saved answers: 9933225 is 59 calls, 383,829 input and 27,848 output tokens for `score_gold` (reading plus evidence questions; a full run adds 5 product-naming calls). 9935891 is 214 calls, 1,568,873 input and 65,297 output tokens. The manufacturers' documents cost nothing: the Chroma store already holds them, so they are not read again.
- **Partial runs** (another chunker, the graph on 9840129): `scripts.cost.estimate_cost` counts the new questions and their input tokens as characters / 4. Measured against Gemini's own counts on the saved questions, characters / 4 is low: 74% of the real input tokens on 9933225 and 69% on 9935891. So the estimate is scaled by 1.36 (valves) or 1.45 (pumps), and the measured output per question (474 tokens on valves, 281 on pumps) is added.
- **Rupees** use the app's own rate, `RUPEES_PER_MILLION_TOKENS` = 100, input and output together. For a lighter model the rupees are scaled by Google's price list on the same mix of input and output tokens, so no exchange rate is assumed. Google's prices per million tokens, standard tier, as listed today: Gemini 3.8 Flash (in use) $0.75 in / $3.75 out until 31 December 2026, then $1.50 / $7.50 from 1 January 2027; Gemini 3.5 Flash-Lite $0.30 / $2.50; Gemini 3.1 Flash-Lite $0.25 / $1.50.
- These are expected costs, not limits. A new model or temperature can read the tender into a different number of requirements, and replies can be longer or shorter. `LLM_MAX_CALLS` is the hard stop.

| # | Check | Tender | New calls | Cost | What it would tell us | Priority |
|---|---|---|---|---|---|---|
| 1 | Lighter model: Gemini 3.5 Flash-Lite | 9933225 (valves, 11 requirements) | 59 | ≈ ₹19 ($0.19); with 3.1 Flash-Lite ≈ ₹15 | whether a model at about 47% of the price per run (35% for 3.1 Flash-Lite) keeps today's 31 of 35 statuses and 23 of 23 pages agreeing with the answer key | **high** |
| 2 | Temperature at the model's default (1.0) | 9933225 | 59 | ≈ ₹41 ($0.39); ≈ ₹82 after 1 January 2027 | whether Google's recommended setting changes any answer, and whether any reply loops or repeats (more calls than 59 means retries) | **high** |
| 3 | Lighter model | 9935891 (pumps, 82 requirements) | 214 | ≈ ₹73 (3.5 Flash-Lite), ≈ ₹56 (3.1 Flash-Lite) | the same on a larger tender with more numbers and units | medium, only if #1 holds up |
| 4 | Temperature 1.0 | 9935891 | 214 | ≈ ₹163 | the same on the larger tender | low, only if #2 shows a difference |
| 5 | Chunker `structure` (or `auto`, which picks the same for these valve catalogues) | 9933225 | 41 (15 of 56 questions unchanged) | ≈ ₹27 (`auto` ≈ ₹28) | whether the strategy that did best on the free retrieval checks also gives better final answers | medium |
| 6 | Chunkers `recursive`, `sections`, `parent_child` | 9933225 | 55 to 56 each | ≈ ₹45, ₹34, ₹40 | the same for strategies that did not beat the default on the free checks | low |
| 7 | Chunker `structure` | 9935891 | 141 (63 of 204 unchanged) | ≈ ₹111 | the same on pumps; `auto` costs nothing here because it keeps `table_rows` for every pump catalogue, so there is nothing to test | low |
| 8 | Chunkers `recursive`, `sections`, `parent_child` | 9935891 | 203 to 204 each | ≈ ₹162, ₹130, ₹161 | as #6, on pumps | low |
| 9 | Standards graph on a tender that cites linked standards | 9840129 (no answer key) | 123 | ≈ ₹88 (the raw estimate said ₹61) | whether `KNOWLEDGE_GRAPH=on` changes any outcome; a person would have to judge the rows that change | low |
| 10 | How far characters / 4 is from Gemini's own count | both labelled tenders | 0 | ₹0, **answered for free** | measured on the saved answers: the estimate is 74% (valves) and 69% (pumps) of the real input tokens, from 45% to 91% per question | done |

## Recommended plan: a lighter model and temperature 1.0 on 9933225, under ₹100

9933225 is the smaller labelled tender. Two runs, one after the other, each scored against the answer key:

1. **The lighter model, ≈ ₹19. Approved by the owner; waiting for the owner to confirm the model id in AI Studio before it runs.** The id is `gemini-3.5-flash-lite`: Google's models page (checked 27 October 2026) lists it as "Stable" with no shutdown date, and its thinking page lists it as supporting "minimal, low, medium, high" with thinking on by default at "minimal". So `LLM_THINKING` stays at the default `LOW`, as in every saved answer, and only the model changes.
   ```
   cd backend
   $env:LLM_MODEL="gemini-3.5-flash-lite"; $env:LLM_MAX_CALLS="70"; $env:RESERVED_CALLS="5"
   python -m scripts.eval.score_gold ../data/tenders/dev/GeM-Bidding-9933225 ../data/categories/valves
   ```
   `RESERVED_CALLS=5` is needed. The budget keeps `RESERVED_CALLS` calls (60 by default) back for reading the tender and naming products, so with `LLM_MAX_CALLS=70` alone only 70 − 2 − 60 = 8 calls are left for evidence questions, and the plan evaluates only the first few requirements. With 5 held back, 63 are left for the 57 questions.

   **First attempt, 27 October 2026, without `RESERVED_CALLS`.** A one-call smoke test first, with one real evidence question (IS 13095 for Intervalve). The model accepted `LOW` thinking and returned a valid answer on the first try: the same reading the current model gives ("API 609, EN593, IS 13095"). It used 3,749 input and 825 output tokens, ≈ ₹0.25 ($0.0032). Then step 1 ran without errors, but with only 8 calls left for evidence, as described above. It made 9 calls (24,308 input and 940 output tokens, ≈ ₹1.12, $0.0096) and scored 5 of the 35 labelled rows: 5 of 5 statuses and 1 of 1 page agree. That slice is not comparable with today's 31 of 35. Flash-Lite read the tender exactly as the current model does: the same 11 rows and 11 requirements. Spent so far: ≈ ₹1.37 ($0.0128).
2. **Temperature 1.0 on the current model, ≈ ₹41.** In a new shell, so the model is the default again:
   ```
   cd backend
   $env:LLM_TEMPERATURE="DEFAULT"; $env:LLM_MAX_CALLS="70"
   python -m scripts.eval.score_gold ../data/tenders/dev/GeM-Bidding-9933225 ../data/categories/valves
   ```

Expected total ≈ ₹60, leaving about ₹40 for retries or longer replies. `LLM_MAX_CALLS=70` stops either run before it can ask more than 11 questions over the 59 it should need. Two conditions:

- **Run before 1 January 2027.** Google doubles Gemini 3.8 Flash's price that day, which makes step 2 about ₹82 and the total over ₹100.
- **Run step 1 first, and decide on step 2 from its result.**

Each run ends with the agreement and a line like `model calls 59, from cache 0, tokens in … / out …`. Compare with today's result: 31 of 35 statuses and 23 of 23 pages agree, from 59 saved answers. Both runs save their answers under their own keys, so the defaults, the saved answers and the shipped demo answers are untouched.

## Phase 2: chunking strategies, end to end

**What it would measure.** Whether a strategy other than `table_rows` changes the final answers (match scores against the answer keys in `data/eval/gold`), not just which pages are retrieved.

**Why it costs money.** The model is asked about the passages a strategy produces. A different strategy gives different passages, so the prompts differ from the saved ones and most questions are new model calls (questions whose passages come out the same are still answered from the cache). Free checks stop at retrieval: `eval_retrieval` and `eval_candidates` (see `docs/CHANGES.md`, phase 2).

**How to run it, once approved.** `CHUNKER=<name> LLM_MAX_CALLS=<new calls from the table, plus about 10%> python -m scripts.eval.score_gold <tender folder> <category dir>`, one tender at a time.

## Phase 5: temperature at the model's default

**What it would measure.** Whether `LLM_TEMPERATURE=DEFAULT` (the model's own 1.0, which Google advises for Gemini 3 models) changes the answers against the answer keys, and whether any reply loops or repeats, compared with today's 0.

**Why it costs money.** The temperature is part of every saved answer's key, so with another value every question is new, including the ones that read the tender itself.

**How to run it, once approved.** See the recommended plan above. The free estimate cannot price this directly, because it reads the tender first and that reading is new too; the table uses the tokens the same run really used at temperature 0.

## Phase 5: a lighter, cheaper model

**What it would measure.** Whether a lighter Gemini model keeps the answers good enough against the answer keys, and what it saves.

**Why it costs money.** The model is part of every saved answer's key, so every question is new.

**How to run it, once approved.** See the recommended plan above. Compare with the saved results of the current model.

## Phase 5: how far the token estimate is from Gemini's own count

**Answered for free in phase 7.** Every saved answer records the input tokens Gemini reported for that question, which is the count `count_tokens` would give. Comparing them with characters / 4 for the same questions: 281,183 against 381,907 on 9933225 (74%), and 1,055,426 against 1,532,623 on 9935891 (69%); per question from 45% to 91%. So the estimate shown before a run is about 30% low on input tokens, and output tokens come on top. `TOKEN_COUNTER=gemini` would still be needed for tenders whose questions are not saved, but no paid check is needed to know how far off the estimate is.

## Phase 6: the standards graph on tenders that cite linked standards

**What it would measure.** Whether `KNOWLEDGE_GRAPH=on` changes any outcome where it could: tender 9840129 asks for API 598, ASME B16.10 and ASME B16.34, which the graph links to other standards that catalogues name with them. On the two labelled tenders it changed nothing (0 of 405 outcomes), because no evidence there states a different standard.

**Why it costs money.** The graph asks no question itself, but 9840129's evidence is not saved yet: 123 new questions, about ₹88 (see the table). The other tender citing linked standards, 9987635, would need 1,406 new questions, about 7.2 million tokens by the raw estimate, over the per-tender budget, and it is a hold-out tender; it is not worth it for this check. There is no answer key for 9840129, so a person would have to judge the rows that change.

**How to run it, once approved.** Run 9840129 once with the default settings and `LLM_MAX_CALLS=135` to save its answers, then score it with `KNOWLEDGE_GRAPH=off` and `KNOWLEDGE_GRAPH=on`; the second scoring costs nothing, because the questions are the same. Compare the rows for the standard requirements.
