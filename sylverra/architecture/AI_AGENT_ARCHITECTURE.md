# Sylverra AI Agent Architecture

> Phases 3–4 (spec §15, §28–32, §51–53). Built for **cost ↓, latency ↓, accuracy ↑**.
> Inputs: `CURRENT_ARCHITECTURE.md`, `research/AI_COST_LATENCY_RESEARCH.md`.

---

## 1. Principles

1. **Tools compute, LLMs interpret.** Every number comes from a deterministic tool (registry API, XBRL parser, GEE, PDF table parser). Agents never invent numbers.
2. **Workflow, not free-roaming agent.** The orchestrator is code-controlled (fixed DAG); LLMs are called at defined nodes. Predictable cost, latency and debuggability. Open-ended tool loops only in the Research Workspace (§38–39).
3. **Small agents, small contexts.** Each agent receives only the evidence it needs (retrieved chunks + facts), never whole documents.
4. **Everything cached, everything logged.**
5. **Evidence or it didn't happen.** Agent claims must cite evidence ids that exist; validated in code.

---

## 2. Topology — Project Rating (MVP)

```text
                          ┌──────────────────────────────┐
  POST /api/rate/:id ───▶ │   ORCHESTRATOR (code, async)  │ ──SSE──▶ UI (streams each node)
                          └──────────────┬───────────────┘
        Stage 1: GATHER (T0 — no LLM, run in parallel)
        ┌───────────────┬────────────────┼─────────────────┬────────────────┐
        ▼               ▼                ▼                 ▼                ▼
  Registry tool    Document tool    Satellite tool     Methodology      Evidence store
  (projects_cache) (fetch PDD/MR,   (GEE land history, cache (per       (facts + chunks,
                    parse, chunk,    batched + cached)  methodology,     each with id,
                    hash, cache)                        computed once)   source, page)
        Stage 2: EXTRACT (T1 — fast/cheap model, 1 call)
                          ▼
                 Claims Extractor Agent ── pulls PDD claims into schema:
                 {area_ha, baseline_deforestation, start_year, forest_cover_claim, ...} + page cites
        Stage 3: ASSESS (T1 — fan-out, all in parallel)
   ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼          ▼          ▼          ▼
Additional- Baseline  Permanence  Leakage   Monitoring Developer Co-benefits ANOMALY
 ity                                                                         (claims vs
                                                                              satellite facts)
        Stage 4: ADJUDICATE (T2 — reasoning model, 1 call)
                          ▼
            Rating Adjudicator → overall AAA–D + confidence, using ONLY dimension outputs
        Stage 5: VALIDATE (code)
                          ▼
            Evidence validator → drop uncited claims, compute confidence, attach versions → store
```

**Latency:** Stage 1 parallel (~slowest tool) → Stage 2 one fast call → Stage 3 parallel (~one fast call) → Stage 4 one reasoning call. Four serial LLM hops max; UI streams from Stage 1.

**Cost:** ~8 T1 calls × ~6k input + 1 T2 call ≈ **$0.03** (DeepSeek) / **$0.13** (Claude) per fresh rating; **$0** on cache hit (see research §3).

---

## 3. Agent contracts

Every agent = `(name, tier, prompt_version, input_schema, output_schema, retriever)`.

### Common output schema (dimension agents)
```json
{
  "dimension": "additionality",
  "score": 0-100,
  "risk": "low|medium|high|unknown",
  "reason": "≤ 3 sentences",
  "evidence": [{"evidence_id": "doc:PDD#p34#c2", "quote": "…", "supports": "…"}],
  "data_gaps": ["…"],
  "label": "Reported|Estimated|Model estimate|Inference|Data not found"
}
```

| Agent | Tier | Retrieval query / inputs | Notes |
|---|---|---|---|
| Claims Extractor | T1 | whole-doc section headers + targeted chunks (project area, baseline, start date, activity) | JSON schema; values must have page cites |
| Additionality | T1 | "additionality, investment analysis, barrier analysis, common practice" | |
| Baseline | T1 | "baseline scenario, reference region, historical deforestation rate" + satellite facts | |
| Permanence | T1 | "non-permanence risk, buffer, AFOLU risk tool" + fire/deforestation facts | |
| Leakage | T1 | "leakage, activity shifting, displacement" | |
| Monitoring | T1 | "monitoring plan, parameters, frequency, QA/QC" | |
| Developer | T1 | registry facts (developer's other projects, issuance history) | Mostly T0 data |
| Co-benefits | T1 | "SDG, community, biodiversity" + WDPA/population facts | |
| **Anomaly** | T1 | Claims Extractor output **vs** satellite facts (area, tree cover, loss history) | Differences computed in **code** first (e.g. claimed 1,200 ha vs mapped 870 ha = −27%); LLM only explains significance |
| Rating Adjudicator | T2 | all dimension outputs (no raw docs) | Weighted rubric v0.1 + LLM judgement on conflicts; outputs grade + confidence |

Rubric v0.1 weights (documented, versioned — spec §53): Additionality 20, Baseline 20, Permanence 15, Leakage 10, Monitoring 10, Anomaly/Data integrity 15, Developer 5, Co-benefits 5. Base score computed in code; adjudicator may shift by at most one notch with a written reason.

---

## 4. AI Gateway (`services/ai_gateway.py`)

Single entry point for every LLM call.

```text
call(agent, tier, system, facts, schema) →
  1. key = sha256(agent|prompt_version|model|canonical_json(facts))
  2. cache lookup (Mongo `ai_cache`) → hit: return (0 ms model time, $0)
  3. build messages: [stable system prefix + rubric] + [facts/evidence as DATA block]   ← prefix-cache friendly
  4. route tier → model (T1 flash, T2 pro) ; timeout budget per tier; 1 retry w/ backoff; fallback model
  5. JSON parse + schema validate → on failure one repair retry, else structured error
  6. log to `agent_runs`: agent, model, tokens in/out/cached, latency_ms, cost_usd, cache_hit, run_id
  7. store in cache
```

Config (env): `AI_T1_MODEL`, `AI_T2_MODEL`, `AI_PROVIDER` — swap DeepSeek ↔ Claude without code changes.

---

## 5. Evidence model

```json
// evidence (Mongo for hackathon; Postgres table later)
{
  "evidence_id": "doc:<sha8>#p34#c2" | "sat:<geom_sha8>:hansen_loss_2001_2024" | "reg:VCS1234:issued",
  "kind": "document_chunk | satellite_fact | registry_fact",
  "project_id": "VCS1234",
  "text": "…chunk text or fact sentence…",
  "value": 870.4, "unit": "ha",
  "source": "PDD v2.1", "url": "…", "page": 34,
  "retrieved_at": "2026-09-26T…Z",
  "hash": "sha256…"
}
```

UI path: **dimension → claim → evidence card → source link + page** (spec §29).

---

## 6. Data stores (hackathon → production)

| Store | Hackathon | Production |
|---|---|---|
| App data, registry cache | MongoDB (existing) | Postgres |
| Evidence, ratings, agent_runs, ai_cache | MongoDB (new collections) | Postgres + pgvector |
| Chunk retrieval | BM25 in-process (no embedding cost/latency, good for keyword-rich PDDs) | Hybrid BM25 + embeddings |
| Geospatial | GEE + result cache | + PostGIS for boundaries |
| Jobs | asyncio task + SSE | Queue (RQ/Celery) + workers |

BM25 for the MVP is a deliberate cost/latency choice: zero embedding spend, no vector DB, millisecond retrieval, and PDD vocabulary (VM0047, leakage, buffer) is highly lexical.

---

## 7. Security (spec §51)

- Rating & AI endpoints: `require_auth` + per-user daily token budget + rate limit (fixes audit A5).
- Documents wrapped in a delimited DATA block; system prompt instructs to treat as untrusted and ignore embedded instructions; outputs schema-validated.
- No document text ever reaches the system prompt.

## 8. Build order (Phase 5+, hackathon)

1. `ai_gateway` (routing, caching, telemetry) + migrate the two existing endpoints onto it.
2. GEE land-history → batched single call + cache.
3. Document tool (PDF fetch/parse/chunk/BM25) + evidence store.
4. Agents + orchestrator + SSE endpoint `/api/rate/:project_id`.
5. Frontend: Project Rating page — streaming dimension cards, evidence drawer, cost/latency meter.
6. Stretch: BRSR XBRL company KPIs.
