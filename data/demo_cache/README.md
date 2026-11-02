Saved Gemini answers shipped with the code, so the example tenders run with no model calls at all.

Written by `python -m scripts.cost.export_demo_cache <category folder> <tender> ...` (run from `backend`). The system only reads this folder, never writes to it.
Each answer is in a subfolder named by the first two characters of its file name (`3f/3f….json`), so no folder holds hundreds of files; `shipped_path` in `backend/app/llm/llm_cache.py` is the one place that knows this.
An answer is reused only when the request is identical, so a changed prompt, passage count or model asks Gemini again instead of returning a stale answer.
