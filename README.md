# Tender Requirement Matching

Upload a GeM tender (PDF) and pick a category. The system reads the tender, breaks it into individual requirements, searches each manufacturer's catalogue documents for evidence, compares them, and returns a report: a status and score per requirement per manufacturer, an overall compatibility ranking, and a cited page for every claim.

An LLM (Gemini) only reads text and pulls out structured facts. The comparison and scoring are plain code, and every quoted piece of evidence is checked programmatically against the page it came from.

## Run it (Docker, no build needed)

You need Docker and a Gemini API key. The images are public on Docker Hub:

- `shravani1711/tender-matcher-backend`
- `shravani1711/tender-matcher-frontend`

```
docker run -d --name tm-backend -p 8000:8000 -e GEMINI_API_KEY=YOUR_KEY -v tender-data:/data shravani1711/tender-matcher-backend:latest
docker run -d --name tm-frontend -p 3000:80 -e API_URL=http://localhost:8000 shravani1711/tender-matcher-frontend:latest
```

**How the two images connect:** the frontend is a static site served by nginx. The page you open on port 3000 runs in your browser, and your browser calls the backend directly at `API_URL` (default `http://localhost:8000`). The containers do not talk to each other, so no shared network is needed. Start the backend first and keep both ports published. If you run the images on another machine, set `API_URL` on the frontend to the address your browser should use to reach the backend (for example `http://my-server:8000`).

Open http://localhost:3000, choose a category and upload the tender PDF(s). The system reads the tender, then **stops and shows an estimate before it spends anything**: how many new Gemini questions it needs, roughly what they cost in rupees, and about how long they take, with **Proceed** and **Cancel** buttons. Nothing is charged for matching until you press Proceed; the only Gemini calls made before it are the few that read the tender itself.

- **Answers it already has are free.** The images ship with the answers for five example tenders (GeM 9933225, 9968695 and 10016383 for valves; 9935891 and 9604147 for pumps), so those show "everything is already saved" and finish in under a minute with no Gemini calls. Every answer from your own runs is kept in the `tender-data` volume, so repeating a run is also free.
- **A tender it has not seen** makes live Gemini calls. Expect a few minutes and roughly ₹6 for a small tender up to ₹60-90 for one with 8-16 requirements, and never more than the budget below. On one checked tender the estimate said about ₹26 and AI Studio showed ₹26.
- The estimate is a guess for time (the model's speed varies) and a close figure for money (it prices the input tokens of every question before asking it).
- The manufacturers' documents are already indexed inside the image, so the first run on a fresh container does not spend minutes building a search index.

Or with Docker Compose (from a clone of this repo, with a `.env` file next to `docker-compose.yml`):

```
GEMINI_API_KEY=YOUR_KEY
DOCKERHUB_USER=shravani1711
```

```
docker compose pull
docker compose up
```

To build the images yourself instead, run `docker compose up --build`.

## Ports and settings

| Service  | Port | Notes |
|----------|------|-------|
| Backend  | 8000 | FastAPI; interactive docs at `/docs` |
| Frontend | 3000 (nginx on 80 inside the container) | the browser calls the backend directly, so `API_URL` must be an address your browser can reach |

Backend environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GEMINI_API_KEY` | none (required) | your Gemini key |
| `LLM_MAX_CALLS` | 400 | hard cap on Gemini calls per run, a cost guard |
| `TENDER_TOKEN_BUDGET` | 1500000 | input tokens of new Gemini questions one tender may use (about 150 rupees). A tender over it is read from fewer passages per question, and if still over, only its first items are evaluated; the report's notes say exactly what was cut |
| `SEED_CACHE_DIR` | baked into the image | model answers shipped for the example tenders, so those tenders cost nothing to run |
| `SEED_EMBEDDINGS` | baked into the image | search vectors of the manufacturers' documents and of the example tenders' questions, computed where the shipped answers were saved. Vectors computed on another machine differ in the last digits, which can change the passages a question reads and so miss a saved answer |
| `EVIDENCE_TOP_K` | 16 | passages read per question. 8 is an economy mode at roughly half the cost: the cited page was among the passages read 95% of the time at 16 and 82% at 8, but on my two hand-labelled tenders the accuracy was about the same |
| `LLM_MODEL` | `gemini-3.8-flash` | Gemini model. Saved answers belong to a model and a thinking level, so changing either means asking again |
| `LLM_THINKING` | `LOW` | `MINIMAL`, `LOW`, `MEDIUM`, `HIGH` or `DEFAULT` |
| `RUPEES_PER_MILLION_TOKENS` | 100 | turns tokens into the rupee figure on the estimate; change it if the price changes |
| `APPROVAL_WAIT_MINUTES` | 30 | how long a run waits for Proceed or Cancel before it cancels itself, because a waiting run holds up the runs behind it |
| `LLM_WORKERS` | 4 | parallel Gemini calls; lower it on a free-tier key |
| `MAX_UPLOAD_MB` | 60 | upload size limit |
| `CATEGORIES_DIR` | baked into the image | folder of categories and manufacturer PDFs |
| `RUNS_DIR` | `/data/runs` | where run history (SQLite) is stored |
| `CACHE_DIR` | `/data/cache` | LLM and embedding caches |

Frontend: `API_URL`, the backend address.

## Using it without the UI

```
curl -F "category=pumps" -F "files=@tender.pdf" http://localhost:8000/runs
curl -F "category=pumps" -F "files=@tender.pdf" -F "ask_first=true" http://localhost:8000/runs   # stops at the estimate (status "awaiting")
curl -X POST http://localhost:8000/runs/<id>/proceed     # or /cancel
curl http://localhost:8000/runs/<id>/report        # machine-readable JSON
curl http://localhost:8000/runs/<id>/report.md     # readable report
curl -o report.xlsx http://localhost:8000/runs/<id>/report.xlsx
```

A run started without `ask_first` goes straight through to the report, so scripts do not have to wait for an answer; the web page always asks first. The status of a run is `queued`, `awaiting` (the estimate is waiting for an answer), `running`, `done`, `failed` or `cancelled`.

Other routes: `GET /health`, `/categories`, `/runs`, `PATCH`/`DELETE /runs/{id}`, `GET`/`PUT /runs/{id}/reviews`, and `GET /categories/{cat}/manufacturers/{maker}/documents/{name}` for the cited PDFs.

## Categories

Categories live in `data/categories/<category>/manufacturers/<maker>/` as PDFs plus source notes. Add a folder of PDFs and it appears in the category list; no code changes are needed.

Collecting catalogues by hand does not scale, so there is an optional crawler that lists, and with `--download` saves, the PDFs a manufacturer publishes, recording each file's address, the page it was found on, the date and a hash in `crawl_sources.csv` next to them. It obeys `robots.txt`, waits between requests, stays on the manufacturer's site, and does nothing unless asked:

```
cd backend
python -m scripts.crawl_catalogues --category pumps --maker grundfos --start <page listing the catalogues> --include databooklet --exclude price
```

Included: `pumps` (CRI, Grundfos, Kirloskar, KSB) and `valves` (Delval, Duncan, Intervalve, King, KSB, L&T, Leader).

## Statuses and scores

Per requirement and manufacturer: fully matched (100), partially matched (75 when the product exceeds or only partly meets the ask; 50 for different readings or same family; 25 when it cannot be compared), missing capability (0), or unsupported requirement (paperwork or information items, or requirements the catalogue documents cannot cover). Overall compatibility is the mean over scored items; coverage and a defining-type gate (pump or valve type) break ties and rank the makers. Rows the system is unsure about carry a review flag and appear in the Pages to check and To confirm tabs.

## Example output

Pump tender GeM 9935891, category `pumps`. The summary table from the generated report (`/runs/<id>/report.md`):

| Rank | Manufacturer | Compatibility | Coverage | Fully | Partially | Missing | Unsupported | Need review |
|---|---|---|---|---|---|---|---|---|
| 1 | grundfos | 37.7% | 53.5% | 16 | 12 | 30 | 24 | 12 |
| 2 | cri | 37.1% | 51.8% | 16 | 14 | 28 | 24 | 30 |
| 3 | ksb | 33.0% | 58.6% | 10 | 21 | 27 | 24 | 21 |
| 4 | kirloskar | 9.9% | 18.9% | 3 | 6 | 49 | 24 | 8 |

The top three are close, and the report says so by showing how much of each score rests on rows that need a person to look ("Need review"). Requirement-by-requirement rows for one item, with the page each claim comes from (Grundfos, judged against the CR, CRI and CRN pumps):

| Requirement | Status | Score | Evidence | Why |
|---|---|---|---|---|
| pump_type: vertical multistage, in-line type | partially matched (check: only part stated) | 50 | cr-databooklet-50hz.pdf p1: "Vertical multistage centrifugal pumps" | states Vertical multistage centrifugal: only part of what is asked; not stated: line |
| pumping_efficiency: 70 % | partially matched (check: only under a condition) | 75 | cr-databooklet-50hz.pdf p6: "Max. pump efficiency [%] 35 48 58 66 70" | stated 70 %; only pump size 10 |
| mechanical_seal_type: Cartridge type and balanced | fully matched | 100 | cr-databooklet-50hz.pdf p21: "O-ring (cartridge) (balanced seal)" | states O-ring, cartridge, balanced seal |
| operating_duty_flow: 20 m3/h | missing capability | 0 | | no evidence found in the documents |
| suction_condition: Flooded | unsupported requirement | | | none of the collected documents says anything about it for any manufacturer, so it cannot be judged |

The same report is available as JSON (`/runs/<id>/report`) and Excel (`/runs/<id>/report.xlsx`), and in the UI with each evidence link opening the cited PDF page.

## Development

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
uvicorn app.main:create_app --factory --port 8000
```

```
cd frontend
npm install
npm test
npm run dev
```

Put the key in `backend/.env` as `GEMINI_API_KEY=...`.
