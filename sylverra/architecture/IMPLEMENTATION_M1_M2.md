# Sylverra — Modules 1 & 2 implementation (2026-09-26)

Module 3 (investment and land intelligence) is **out of scope** for this build.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| LLM | DeepSeek only: `deepseek-flash` (T1) for extraction, dimension and research agents; `deepseek-v4-pro` (T2) for the adjudicator. Gateway: `services/ai.py` | Owner's choice; cheapest per token. JSON-schema validation with one repair retry; content-addressed cache; every call logged to `agent_runs` |
| Web search | **None.** Agents navigate known official sources instead | Owner's choice (no search API) |
| Company discovery | NSE `EQUITY_L.csv` (resolver) + `/api/annual-reports` + `/api/corporate-bussiness-sustainabilitiy` (BRSR PDF and XBRL) | Official filings; XBRL gives exact values with no LLM |
| Registry data | CarbonPlan **OffsetsDB** (projects + every issuance/retirement across 7 registries) | See the data-source findings below |
| Uploads | **Only** in the Company Carbon Calculator, for a company's own bills and invoices. Research and rating agents never need uploads | Owner's requirement |
| Jobs | Background threads, with progress in Mongo `jobs`; the UI polls `/api/jobs/:id` | Works with the existing Flask/gunicorn setup |

## Data-source findings (checked 2026-09-26)

- **Verra:** `registry.verra.org/uiapi/resource/resource/search`, used by `services/registry.py`, now returns the new Platts-hosted registry app (HTML), not JSON. **The existing `/projects` registry refresh is therefore broken.** Its data API is config-driven and couldn't be found without a browser session.
- **Gold Standard:** `public-api.goldstandard.org/projects/{id}` and `?query=GS{number}` work with a browser user agent. Bulk paging is Cloudflare-protected for plain `curl`. Project documents sit behind the assurance-platform SPA.
- **OffsetsDB:** `carbonplan-offsets-db.s3…/offsets-db.csv.zip` downloads without a key (snapshot 2026-06-01; 11,659 projects). CarbonPlan claims no copyright in the factual data; registry terms may still apply.
- **NSE:** the annual-report and BRSR APIs work with a browser user agent; the quote API is blocked. **Confirm NSE's terms before any bulk crawling.** The current use is on-demand, one company at a time.
- **BSE:** the API returns *Access Denied* to scripted clients.

## How to run locally

```bash
# backend
cd sylithe-backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# .env: MONGO_URI, JWT_SECRET, DEEPSEEK_API_KEY (see .env.example)
.venv/bin/python app.py            # :5001
# load registry data once (admin): POST /api/intel/registry/refresh  (or the button on /sylverra/projects)

# frontend
cd sylithe-frontend && npm install
VITE_API_URL=http://localhost:5001 npm run dev   # open http://localhost:5173/sylverra (log in first)
```

## API

| Area | Endpoints |
|---|---|
| Module 1 | `GET /api/companies?q=` · `POST /api/companies/research {symbol}` · `GET /api/companies/:slug` · `/metrics` · `/ratings` · `POST /:slug/recompute` (admin) · `GET /api/kpi-definitions` |
| Module 2 | `GET /api/intel/projects` · `/facets` · `GET/POST /api/intel/projects/:id[/rate\|/ratings\|/documents]` · `GET /api/intel/compare?ids=` · `POST /api/intel/ratings/:id/review` (admin) · `GET /api/intel/methodology` · `GET /api/intel/registry/meta` · `POST /api/intel/registry/refresh` (admin) |
| Shared | `GET /api/evidence/:id` · `GET /api/jobs/:id` · `GET /api/overview` · `POST /api/research/ask` · `GET /api/research/sessions[/:id]` |
| Calculator | `GET/POST /api/calculator/inventories` · `GET/DELETE /:id` · `POST /:id/lines` · `POST /:id/upload` · `GET /api/calculator/factors` |

## Frontend (`/sylverra`)

Overview · Company Intelligence · Company profile · Carbon Calculator · Project Ratings · Project detail · Compare · AI Research Agent · Methodology. Code is in `sylithe-frontend/src/sylverra/`.

## Measured on real data (local run)

| Run | Result | AI cost |
|---|---|---|
| Reliance (RELIANCE): full Module 1 pipeline | 28 XBRL facts, 3 targets, 13 narrative metrics, financials; grade C (55.7) | ≈ $0.015 |
| GLD12019 cookstove rating (10 agents + adjudicator) | Grade C (rubric B, adjudicator −1); anomaly: issuance 1.27x the registry estimate | ≈ $0.01 |
| Research-agent answer with 5 tool calls | All citations resolved to stored evidence | ≈ $0.0015 |

## Open items

1. Fix or replace the legacy `services/registry.py` Verra fetcher (it's broken because of the registry migration), or point `/projects` at OffsetsDB.
2. Automate project-document retrieval (Verra/GS document endpoints need a browser session); today analysts link public PDF URLs.
3. Confirm NSE and registry terms of use before production; move GEE to a commercial plan (Module 3).
4. Scanned (image-only) PDFs aren't supported yet: no OCR.
