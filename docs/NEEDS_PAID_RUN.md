# Checks that need paid model calls

Checks 1 and 2 in the table were run on 27 October 2026, with the owner's approval, for ≈ ₹59.78 in all (results in the recommended plan below). Check 12 was run on 4 November 2026, also with approval, for ≈ ₹1.19 (results in its section at the end). Check 10 was answered for free. Nothing else here has been run. Each check is priced below from free measurements, and each section after the table says what it would measure, why it cannot be measured for free, and how to run it once approved. Run every paid check one tender at a time with `scripts.eval.score_gold`, never `eval_all`: `eval_all` goes on to the other labelled tender and would spend there too.

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
| 11 | Chunker `semantic` (added after phase 7) | 9933225 | 56 (none of the 56 questions unchanged) | ≈ ₹33 (estimate 219,527 input tokens × 1.36, plus 474 output tokens a question) | whether the strategy that put a right page first most often on the free retrieval checks (6 of 7 valve cases, hybrid) also gives better final answers, given its much shorter passages | medium |
| 12 | The model told to expect Hindi (`OCR_LANGS=en,hi`) on the real bilingual scans | 9918524 (its BHEL specification, the 6 scanned pages with Hindi) | 6 | ≈ ₹1.13 estimated; **run 4 November 2026: 6 calls, ≈ ₹1.19** | whether the language hint changes what the model writes in Hindi on those pages, against today's saved transcriptions. The default reader, the model, reads them now without the hint | done |
| 13 | EasyOCR as the page reader (`OCR=easyocr`), end to end | 9933225 | not priced yet | not priced: the free estimate was stopped before it finished (the computer ran low on memory) | whether a free local reader gives the same final answers as the model's transcriptions; the free check on real bilingual scans (below) says it reads them poorly | low |

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

   **Corrected run, 27 October 2026, with `RESERVED_CALLS=5`.** It ran without errors and under the in-run guard, which would have stopped any call once the spend passed the remaining ₹23.63.

   | | Gemini 3.8 Flash (saved answers, no cost) | Gemini 3.5 Flash-Lite (this run) |
   |---|---|---|
   | Calls | 59 (saved) | 56 new, plus 5 answers from the first attempt |
   | Tokens | 383,829 in / 27,848 out | 393,054 in / 13,602 out |
   | Cost | ≈ ₹41 if asked again | ≈ ₹17.87 ($0.1519) |
   | Labelled rows scored | 35 | 30 |
   | Statuses agreeing with the answer key, all rows | 31 of 35 | 24 of 30 |
   | **On the 30 rows both scored: statuses** | **26 of 30** | **24 of 30** |
   | **On the 30 rows both scored: pages** | **18 of 18** | **14 of 16** |
   | Findings returned by the model | 231 | 100 |
   | Rejected by the verbatim-quote check | 0 | 1 |
   | Rejected as about another type of product | 134 | 6 |
   | Findings kept | 97 | 93 |

   - **All 35 rows, scored later by tender row** (`score_gold` now matches the answer key by the tender row; see `docs/CHANGES.md`): Flash-Lite 28 of 35 statuses and 19 of 21 pages, against 31 of 35 and 23 of 23 for the current model.
   - **The 5 rows Flash-Lite did not score** are one requirement, `valve_end_connection` for five makers. Flash-Lite named it `end_connection` when splitting the tender's rows into requirements, so the answer key, which is keyed by attribute name, had nothing to compare. It read the same 11 rows.
   - **The rows that differ:** Flash-Lite is wrong where the current model is right in 4 (face-to-face for Duncan and Intervalve, handle type for Duncan, nominal pressure for Delval). It is right where the current model is wrong in 2 (nominal pressure for King, nominal size for Intervalve).
   - **Findings:** Flash-Lite returned far fewer findings that were then set aside as another type of product, and one quote that was not word for word.
   - **Total spent on step 1:** smoke test ≈ ₹0.25, first attempt ≈ ₹1.12, this run ≈ ₹17.87: ≈ ₹19.24 ($0.1647). Step 2 was not run. `LLM_MAX_CALLS` is back at 0, in the shell and in `backend/.env`.
   - **What this says, on one tender of 11 requirements:** Flash-Lite costs about 43% of the current model for this tender, and agrees with the answer key slightly less often: 24 against 26 of the same 30 rows, and 14 of 16 pages against 18 of 18. One small tender is not enough to decide; the pump tender (check #3, ≈ ₹73) would be the next evidence.
2. **Temperature 1.0 on the current model, ≈ ₹41.** In a new shell, so the model is the default again:
   ```
   cd backend
   $env:LLM_TEMPERATURE="DEFAULT"; $env:LLM_MAX_CALLS="70"; $env:RESERVED_CALLS="5"
   python -m scripts.eval.score_gold ../data/tenders/dev/GeM-Bidding-9933225 ../data/categories/valves
   ```

   **Run on 27 October 2026, approved by the owner.** It used the current model, `LLM_TEMPERATURE=DEFAULT`, `RESERVED_CALLS=5`, `LLM_MAX_CALLS=70` and an in-run guard at ₹45. It ran without errors.

   | | Temperature 0 (saved answers, no cost) | Temperature 1.0, the model's default (this run) |
   |---|---|---|
   | Calls | 59 (saved) | 58 new |
   | Tokens | 383,829 in / 27,848 out | 380,016 in / 25,349 out |
   | Cost | | ≈ ₹40.54 ($0.38) |
   | **All 35 labelled rows: statuses agree** | **31 of 35** | **29 of 35** |
   | **Pages agree** (where both found something) | **23 of 23** | **21 of 21** |
   | Findings returned by the model | 231 | 222 |
   | Rejected by the verbatim-quote check | 0 | 0 |
   | Rejected as about another type of product | 134 | 114 |
   | Findings kept | 97 | 108 |
   | Retries (a reply sent back as invalid JSON) | 0 | 0 |
   | Empty replies | 0 | 0 |
   | Output tokens per call: median, largest | 236, 2,600 | 192, 2,477 |

   - **No sign of looping.** There were no retries, no empty or truncated replies and no errors, and replies were no longer than at temperature 0. The most repeated line in any reply (8 times) is the field `"operator": "equals",` in a normal list; temperature 0 has one with 9.
   - **Scored by tender row**, as `score_gold` now does with no manual mapping: 29 of 35 statuses and 21 of 21 pages, the same as the figures above.
   - **How all 35 rows were scored.** At temperature 1.0 the model named the IS 13095 requirement `conformity_to_governing_specification` instead of `governing_specification`, so `score_gold` as it stands scores 30 rows (24 of 30 statuses, 20 of 20 pages). The 35-row figures above treat that one name as the answer key's. Its five rows came out the same at both temperatures, and all five agree with the key.
   - **The rows that differ:** temperature 1.0 is wrong where 0 is right in 3: face-to-face and handle type for Duncan, now "no evidence found", and end connection for KSB. It is right where 0 is wrong in 1: nominal size for Intervalve.
   - **What this says, on one tender:** the same cost as temperature 0, 2 fewer statuses agreeing, and no looping. Not enough to change the default, which stays 0.
   - **Total spent on paid checks so far:** step 1 ≈ ₹19.24, step 2 ≈ ₹40.54, ≈ ₹59.78 in all. `LLM_MAX_CALLS` is back at 0 in the shell and in `backend/.env`.

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

## After phase 7: OCR in more languages

**The default page reader uses the model.** Pages that are only a picture are transcribed by Gemini (`OCR=model`, the default), one paid call per page, saved. A free local reader, EasyOCR (`OCR=easyocr`), now exists for English, Hindi and Marathi (`OCR_LANGS`).

**Measured free.** Tender 9918524 includes a BHEL specification whose 6 scanned pages mix Hindi and English, and the model's transcriptions of them are saved. Against them, EasyOCR with `OCR_LANGS=en,hi` found 25 of the 89 Hindi words (28%) and 148 of 254 numbers (58%); with `en` only, 0 Hindi words and 167 numbers (66%). On pictures generated in the tests it reads Hindi, Marathi and English word for word. The model's transcriptions are the reference here, not a checked truth.

**Check 12: the language hint on the model.** With `OCR_LANGS` other than `en`, one sentence is added to the transcription prompt, so the 6 pages are new questions: about ₹1.13. Run each page once and compare the Hindi with the saved transcription (a person judges which is right):
`OCR_LANGS=en,hi LLM_MAX_CALLS=1 PYTHONIOENCODING=utf-8 python -m scripts.show_reading.show_ocr "../data/tenders/dev/GeM-Bidding-9918524/spec-_merge_2026-09-19-15-26-40_dc94d4c4c4cbd6cc2943216292c7b412.pdf" <page>` for pages 1, 3, 4, 5, 6 and 7.

**Check 12 was run on 4 November 2026, with the owner's approval** (cap `LLM_MAX_CALLS=7` for that run only, then back to 0). It was run exactly as written above, one command per page.

**Actual cost:** 6 model calls, no retries. 7,350 input and 4,541 output tokens, ≈ ₹1.19 at the app's rate (estimated ≈ ₹1.13). At Google's listed prices for Gemini 3.8 Flash ($0.75 in, $3.75 out per million) that is about $0.023.

**What changed.** Every page was read differently. The new readings kept the English and the numbers: 90% to 100% of the old reading's English words, and 241 of 254 of its numbers, mostly the same values written another way. The Hindi on these pages is form labels, sign-off blocks, the header and a copyright note. None of it is a requirement, so it does not change matching. Judged against the printed page, by looking at the scans:

| Page | Old reading (no hint) | New reading (with the Hindi hint) | Closer to the printed page |
|---|---|---|---|
| 1 (ST47031, page 1) | only the header: "उत्पाद मानक / PRODUCT STANDARD NO.", and "पृष्ठ / Page: 1 of 2" in place of the printed "पृष्ठ 2 का 1"; the whole Hindi sign-off block left out | the header and "पृष्ठ 2 का 1" as printed, and the whole sign-off block in Hindi: अनुवादक, निर्माणकर्ता, जांचकर्ता, पर्यवेक्षणकर्ता, सहमत विभाग, नाम, दिनांक एवं हस्ताक्षर, स्वीकृति, निर्माण, जारी | **new**, clearly. One slip: "सहमत्त" for the printed "सहमत" |
| 3 (ST47025, page 1) | the header and the full sign-off block, but "सहमल विभाग" for the printed "सहमत विभाग" | the header and the block with "सहमत विभाग" spelled right, but two signatures turned into made-up words ("Hart", "V.kpy") | about even: the new Hindi is spelled better, the old does not invent words |
| 4 (ST47025, page 2) | the header, the side notes and the copyright note in Hindi | the same text, plus the handwritten inventory number (P-5522) and date (26.7.04), which are on the page | **new**, slightly |
| 5 (ST47025, page 3) | "निर्माणकर्ता" and "जांचकर्ता" as printed | "निर्मांणकर्ता", with a dot that is not printed, and two Hindi labels that are not on the page ("हस्ताक्षर SIGN", "दिनांक DATE") | **old** |
| 6 (ST47025, page 4) | "निर्मांणकर्ता", with a dot that is not printed, and English labels the page does not have ("Row 1", "Signature: [Signed]") | "निर्माणकर्ता" and "जांचकर्ता" as printed | **new** |
| 7 (change advice form, printed sideways) | almost nothing: four names (संदीप गुप्ता, मनोज कु.) out of a form full of Hindi | the whole form: "प्रपत्र डीजी ४१ (डी)", "संशोधन प्रपत्र", every numbered field label in Hindi and English, the codes and dates. One name on a faint stamp ("अशोक कुमार गुप्ता") could not be checked at this resolution | **new**, by far |

**In plain words:** with the hint, the model wrote down the Hindi much more fully, and on 4 of the 6 pages it is closer to the print. On page 3 it is about even, and on page 5 the old reading is better. The hint is not perfect. It sometimes adds a label that is not printed, or reads a signature as a word, which the old reading did too.

**Nothing in the app changed.** `OCR_LANGS` stays `en`, so the app still uses the old readings and every saved answer still matches. The new readings are only in this computer's answer cache (`backend/.cache/llm`, not in git). Using them would make this tender's reading new, a paid run of its own. The Hindi is labels, not requirements, so there is no reason to do that for this tender.

**Check 13: EasyOCR end to end.** Every page that is a picture would be read differently, so the passages of the catalogues with such pages (and the reading of any tender with them) change, and those questions are new. To price it for free, run `OCR=easyocr CHROMA_DIR=<a scratch folder> LLM_MAX_CALLS=0 python -m scripts.cost.estimate_cost ../data/tenders/dev/GeM-Bidding-9933225 ../data/categories/valves` on a computer with memory to spare (EasyOCR loads PyTorch). A scratch Chroma folder keeps the main store as it is. Not worth paying for until EasyOCR reads real scans better.
