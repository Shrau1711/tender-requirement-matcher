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
- *the folders the Dockerfile copies: `backend`, `frontend`, and from `data` the folders `categories`, `graph`, `demo_cache`, `demo_runs`, `tenders` (only `sources.csv` and the five sample folders listed in `data/demo_runs/runs.json`; three of them are hold-out tenders, whose PDFs are not in git) and the file `seed_embeddings.sqlite`.*

*Building the image, for the Space or with `docker build -f Dockerfile.demo`, needs the three hold-out sample folders: `data/tenders/holdout/GeM-Bidding-9968695`, `GeM-Bidding-9604147` and `GeM-Bidding-10016383`. `.gitignore` keeps them out of git, so copy them in from a working copy that has them. Without them, the build stops at `load_samples` with "These sample tender folders hold no PDF: …", rather than shipping samples whose tender pages and layout cannot open, as `v5` did.*
