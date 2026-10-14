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

Open http://localhost:3000, choose a category, upload the tender PDF(s) and start the run. The first run on a new tender makes live Gemini calls and takes several minutes; results are cached in the `tender-data` volume, so repeating a run is fast.

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
| `LLM_MAX_CALLS` | 300 | hard cap on Gemini calls per run, a cost guard |
| `LLM_WORKERS` | 4 | parallel Gemini calls; lower it on a free-tier key |
| `MAX_UPLOAD_MB` | 60 | upload size limit |
| `CATEGORIES_DIR` | baked into the image | folder of categories and manufacturer PDFs |
| `RUNS_DIR` | `/data/runs` | where run history (SQLite) is stored |
| `CACHE_DIR` | `/data/cache` | LLM and embedding caches |

Frontend: `API_URL`, the backend address.

## Using it without the UI

```
curl -F "category=pumps" -F "files=@tender.pdf" http://localhost:8000/runs
curl http://localhost:8000/runs/<id>/report        # machine-readable JSON
curl http://localhost:8000/runs/<id>/report.md     # readable report
curl -o report.xlsx http://localhost:8000/runs/<id>/report.xlsx
```

Other routes: `GET /health`, `/categories`, `/runs`, `PATCH`/`DELETE /runs/{id}`, `GET`/`PUT /runs/{id}/reviews`, and `GET /categories/{cat}/manufacturers/{maker}/documents/{name}` for the cited PDFs.

## Categories

Categories live in `data/categories/<category>/manufacturers/<maker>/` as PDFs plus source notes. Add a folder of PDFs and it appears in the category list; no code changes are needed.

Included: `pumps` (CRI, Grundfos, Kirloskar, KSB) and `valves` (Delval, Duncan, Intervalve, King, KSB, L&T, Leader).

## Statuses and scores

Per requirement and manufacturer: fully matched (100), partially matched (75 when the product exceeds or only partly meets the ask; 50 for different readings or same family; 25 when it cannot be compared), missing capability (0), or unsupported requirement (paperwork or information items, or requirements the catalogue documents cannot cover). Overall compatibility is the mean over scored items; coverage and a defining-type gate (pump or valve type) break ties and rank the makers. Rows the system is unsure about carry a review flag and appear in the Pages to check and To confirm tabs.

## Example output

Pump tender GeM 9935891, category `pumps`. The summary table from the generated report (`/runs/<id>/report.md`):

| Rank | Manufacturer | Compatibility | Coverage | Fully | Partially | Missing | Unsupported | Need review |
|---|---|---|---|---|---|---|---|---|
| 1 | grundfos | 37.5% | 56.7% | 18 | 10 | 32 | 22 | 8 |
| 2 | cri | 33.3% | 48.3% | 17 | 8 | 35 | 22 | 25 |
| 3 | kirloskar | 22.9% | 30.0% | 6 | 11 | 43 | 22 | 15 |
| 4 | ksb | 0.0% | 0.0% | 0 | 0 | 60 | 22 | 0 |

Requirement-by-requirement rows for one item, with the page each claim comes from (Grundfos, judged against the CR, CRI and CRN pumps):

| Requirement | Status | Score | Evidence | Why |
|---|---|---|---|---|
| pump_type: vertical multistage, in-line type | fully matched | 100 | cr-databooklet-50hz.pdf p1: "Vertical multistage centrifugal pumps" | states Vertical multistage centrifugal |
| motor_rated_speed: 2900 RPM | fully matched | 100 | cr-databooklet-50hz.pdf p60: "QH 2900 rpm" | stated 2900 rpm |
| motor_efficiency_class: IE3 | fully matched | 100 | cr-databooklet-50hz.pdf p9: "Efficiency class IE4" | states IE4, which is at least IE3 |
| operating_duty_flow: 20 m3/h | missing capability | 0 | | no evidence found in the documents |

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
