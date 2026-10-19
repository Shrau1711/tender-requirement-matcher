Saved Gemini answers shipped with the code, so the example tenders run with no model calls at all.

Written by `python -m scripts.export_demo_cache <category folder> <tender> ...` (run from `backend`). The system only reads this folder, never writes to it.
An answer is reused only when the request is identical, so a changed prompt, passage count or model asks Gemini again instead of returning a stale answer.
