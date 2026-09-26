# Current Architecture — Sylithe (baseline for Sylithe)

> Phase 1 deliverable of `SYLITHE_CLAUDE_CODE_MASTER_SPEC.md` (§35, §46).
> Inspected: `sylithe-frontend` @ main, `sylithe-backend` @ main (both 2026-09-26).
> Lens for this audit: **AI-first, with cost, latency and performance as primary constraints.**

---

## 1. Stack at a glance

| Layer | Current | Notes |
|---|---|---|
| Frontend | React 19 + Vite 7, React Router 7, Tailwind 3, Radix UI, framer-motion | All pages `lazy()`-loaded; prerender step for SEO |
| Charts | Recharts 3 | |
| Maps | Leaflet + react-leaflet, leaflet-draw, georaster, shpjs, togeojson | Draw / upload KML, SHP, GeoJSON |
| PDF | jspdf, html2pdf.js, pdf-lib (client-side) | Reports rendered in browser |
| Backend | Flask + Gunicorn (2 workers × 4 threads, 180 s timeout) | Sync workers; long AI calls hold a thread |
| Database | MongoDB (pymongo), db `sylithe` | No PostgreSQL / PostGIS |
| Geospatial | Google Earth Engine (service account) | All raster work is server-side in GEE |
| LLM | DeepSeek (`deepseek-chat`, `deepseek-v4-pro`) via raw `requests` | 2 endpoints, no SDK, no caching |
| Auth | Email OTP + password, bcrypt, JWT (7 days), hCaptcha | `utils/auth.py` `require_auth` decorator |
| Email | Resend | |
| Hosting | Vercel (frontend), Render-style env for backend (`GEE_SERVICE_ACCOUNT_JSON`) | |

Size: backend ≈ 4.1 k lines Python (`routes/chm.py` alone 935). Frontend ≈ 12.6 k lines in pages; `src/assets` is 60 MB of media, `src/data/blog` 1.8 MB (60+ SEO articles).

---

## 2. Backend API surface

| Blueprint | Prefix | Endpoints | Purpose |
|---|---|---|---|
| auth | `/api` | `/me`, `/send-otp`, `/verify-otp`, `/signup`, `/login`, `/forgot-password`, `/verify-reset-otp`, `/reset-password` | Accounts |
| projects | `/api` | `GET /projects`, `POST /projects/refresh`, `GET /projects/:id` | India registry projects (Verra + Gold Standard) |
| chm | `/api/chm` | `/predict`, `/land-history`, `/land-summary` 🤖, `/report-analysis` 🤖 | Canopy height, land history, **AI** |
| analytics | `/api/gee` | `/analytics` | GEE analytics |
| free_tier | `/api` | `/free/scan` | Free land scan (quota: per month) |
| reports | `/api` | `/free/lulc-report`, `/quota`, `/free/usage`, `/free/usage/consume` | LULC report images + quota |
| developer_projects | `/api` | `/dev/projects` CRUD, `/dev/stats`, `/dev/activity`, documents | Developer workspace |
| tree_inventory | `/api` | `/dev/tree-inventory/...` | Field plot / tree data |
| admin | `/api` | `/admin/*`, `/request-access` | Admin panel |
| newsletter | `/api` | `/newsletter` | |

🤖 = LLM-backed.

### MongoDB collections
`users`, `newsletter`, `projects_cache`, `otp_tokens`, `free_scans`, `access_requests`, `developer_projects`, `dev_activity`, `tree_inventory`, `lulc_reports`, `feature_usage` (indexes defined in `db.py`).

---

## 3. Frontend surface

- **Marketing / SEO:** Home, `/platform`, `/what-we-offer`, `/for-buyers`, `/about`, `/insights` + `/insights/:slug`, methodology pages (`/methodology/lulc|chm|dcab|agb`), project-type pages (`/project-types/arr|redd|biochar`).
- **App (auth):** `/projects` (registry browser), `/dashboard`, `/chm-verification`, `/dashboard/{corporate,investor,developer,government,project-hub}`, `/admin`.
- **Free tools:** FreeScan, FreeLulcSnapshot, FreeCarbonEstimate, FreeLandEligibility, FreeTreeInventory.
- **Verification views:** VerificationCHM, VerificationBiomass, VerificationBaseline, VerificationLandEligibility.
- **ESG seed:** `components/esg/DataManagement.jsx` + `scopeData.js` (Scope 1/2/3 UI — starting point for Module 1).

---

## 4. Mapping to the Sylithe spec — what already exists

| Sylithe module | Reusable today | Gap |
|---|---|---|
| **M1 Company Carbon Intelligence** | CorporateDashboard, ESG scope UI (static) | No company entity, no document ingestion, no extraction, no evidence model |
| **M2 Carbon Project Rating** | `projects_cache` (Verra + GS India), ProjectsRegistry page, `land-summary` already emits an AAA–D grade | Rating is one LLM call on satellite facts only — no documents (PDD/MR/VR), no dimensions, no evidence, no versioning |
| **M3 Land / Investment** | Strong: GEE land history (Dynamic World LULC, Hansen, MODIS fire, S2 NDVI, CHIRPS, GLO-30, SOC, biomass, WDPA, population), CHM (Meta canopy height), DCAB & AGB methodology pages, AI diligence narrative, PDF report | No async jobs, no result persistence/caching, no portfolio, no developer matching |
| Evidence / citation layer | — | Entirely new |
| Agent orchestration | — | Entirely new |

**Conclusion:** Land intelligence (M3) is the most mature asset; M2 has a data seed; M1 is greenfield.

---

## 5. AI / performance audit (cost · latency · reliability)

### 5.1 Current LLM usage

| Endpoint | Model | max_tokens | Timeout | Called when |
|---|---|---|---|---|
| `/chm/land-summary` | `deepseek-chat` | 900 | 50 s | Land scan → 5-point summary + grade |
| `/chm/report-analysis` | `deepseek-v4-pro` (reasoning) | 8000 | 160 s | PDF report narrative (14 JSON fields) |

### 5.2 Findings

| # | Finding | Impact | Fix (Sylithe design) |
|---|---|---|---|
| A1 | **No caching of LLM output.** Same polygon + same facts re-billed every time; the PDF flow calls both endpoints. | 💰 Cost ×N per repeat view | Cache key = `sha256(model + prompt_version + facts)` in Mongo/Redis; facts are deterministic so hit-rate is high |
| A2 | **Reasoning model for prose.** `report-analysis` uses `deepseek-v4-pro` with 8 k max tokens → gunicorn needed 180 s timeout (see `gunicorn.conf.py`). Task is templated narrative over pre-computed numbers — no deep reasoning needed. | ⏱ 60–90 s latency (per repo comment), 💰 reasoning tokens | Model routing: small/fast model for narrative; reserve reasoning tier for rating adjudication only |
| A3 | **Synchronous LLM calls inside request threads.** 2 workers × 4 threads = 8 concurrent slots; each report call pins one for up to 160 s. | ⏱ Head-of-line blocking; ~8 concurrent reports saturate the server | Async job queue + streaming (SSE) of partial sections |
| A4 | **One monolithic prompt returns 14 sections.** Any JSON failure loses everything; the whole output waits on the slowest part. | ⏱ + reliability | Split into parallel section agents with structured output; stream each as it finishes; partial failures degrade gracefully |
| A5 | **AI endpoints are unauthenticated** (`land-summary`, `report-analysis` have no `require_auth`, no rate limit). | 💰 Open cost-abuse vector | `require_auth` + per-user token budget + rate limit |
| A6 | **Prompt duplicated per endpoint**; system prompt not structured for prefix caching. | 💰 | Stable shared system prefix first, variable facts last → provider prompt caching |
| A7 | **No token/cost telemetry.** Usage is not logged. | Can't optimise what isn't measured | `agent_runs` log: model, in/out tokens, cached tokens, latency, cost, cache hit |
| A8 | **Raw `requests` + no retries/backoff.** Any transient 5xx = user-visible failure. | Reliability | Thin LLM client with retry, timeout budget, fallback model |

### 5.3 Earth Engine latency

| # | Finding | Impact | Fix |
|---|---|---|---|
| G1 | `land_history` performs **~13 sequential `.getInfo()` round-trips** (LULC, Hansen, fire, NDVI, rain, biomass ×2, SOC, DEM, population, water, night lights, WDPA). `run_chm_inference` does ~9 more. | ⏱ Each round-trip is a separate server compute + network hop; total is additive | Merge all reducers into **one `ee.Dictionary({...}).getInfo()`** (single round-trip, GEE parallelises server-side), or fan out with a thread pool |
| G2 | **No result cache for GEE outputs.** Same polygon re-computed on every visit. | ⏱ + GEE quota | Cache by `sha256(normalised geometry + dataset versions + year)`; historical years are immutable → long TTL |
| G3 | GEE init race handled via probe (`_ensure_gee`) in each blueprint | Minor | Single app-level init at startup |

### 5.4 Data-layer

| # | Finding | Fix |
|---|---|---|
| D1 | `/projects` search uses unanchored case-insensitive `$regex` on 4 fields → collection scan | Mongo text index or Atlas Search; later Postgres FTS |
| D2 | Registry refresh deletes then re-inserts all India projects (`delete_many` + `insert_many`) → brief empty window | Upsert by project id |
| D3 | Only India projects cached | Expand as Sylithe scope grows |

---

## 6. Security notes (spec §51)

- Admin emails and "unlimited" emails are **hard-coded in `config.py`**. Move to DB/env with RBAC roles.
- No tenant isolation concept yet.
- Documents are not yet ingested, so prompt-injection surface is small today; it becomes the main risk once PDD / annual-report ingestion starts (Sylithe agents must treat documents as untrusted data).

---

## 7. Keep / change / add

| Keep | Change | Add |
|---|---|---|
| React + Vite frontend, Leaflet map stack, Tailwind/Radix components | LLM calls → shared AI gateway (routing, caching, telemetry, retries) | Agent orchestrator + specialised agents |
| Flask API + GEE pipeline (proven) | GEE multi-getInfo → single batched call + cache | Evidence store (claims ↔ source/page) |
| Mongo for users/app data (for now) | Sync long calls → background jobs + SSE | Document ingestion (PDF parse, chunk, embed) |
| Registry fetchers (Verra, GS) | Auth + quotas on AI endpoints | Postgres + PostGIS + pgvector (decision in Phase 4) |

---

## 8. Next step

Phase 2 — Research (spec §3, §41–43): competitors, registry/data sources and licensing, current LLM pricing/latency (to size the model-routing tiers), and AI-agent architecture patterns for cost/latency. Output goes to `sylithe-docs/research/`.
