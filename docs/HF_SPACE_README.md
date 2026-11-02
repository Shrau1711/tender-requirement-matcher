---
title: Tender Matcher Demo
emoji: 📑
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Replay-only demo of GeM tender requirement matching
---

# Tender matcher: replay-only demo

Matches a GeM tender's technical requirements against manufacturers' documents and shows the page of evidence behind every answer.

This demo replays saved examples only. The sample tenders' reports were made earlier and are loaded when the image is built. Uploading a new tender is refused, no model is called, and no API key is used.
---

*This file is the README of the Hugging Face Space, not of the project. To publish the Space, its repository needs:*
- *this file as `README.md` (the block at the top is the Space's settings);*
- *`Dockerfile.demo` as `Dockerfile`, and `Dockerfile.demo.dockerignore` as `.dockerignore`;*
- *the folders the Dockerfile copies: `backend`, `frontend`, and from `data` the folders `categories`, `graph`, `demo_cache`, `demo_runs`, `tenders` (with the hold-out tenders' PDFs, which are not in git) and the file `seed_embeddings.sqlite`.*
