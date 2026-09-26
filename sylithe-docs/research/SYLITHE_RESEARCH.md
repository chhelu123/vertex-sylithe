# Sylithe — Research (Phase 2, hackathon edition)

> Spec §3, §41–43, §55. Date accessed for all sources: **2026-09-26**.
> Hackathon scope: the ten research files in spec §44 are consolidated into two:
> this file (market, data, licensing, product answers) and
> `AI_COST_LATENCY_RESEARCH.md` (models, pricing, agent performance design).
> Confidence: **H** = official/primary source, **M** = reputable secondary, **L** = general knowledge, not re-verified today.

---

## 1. Competitor landscape

### 1.1 Carbon-project rating agencies (Module 2's direct competitors)

| Claim | Source | Conf. | Why it matters |
|---|---|---|---|
| BeZero, Sylvera and Calyx Global all now rate on the same **AAA–D 8-point scale**; Calyx moved to it in Jan 2025. | [climate-decode](https://climate-decode.com/insights/vcm-series/vcm-2026-era-of-integrity/who-rates-carbon-rating-agencies), [sentinelearth](https://www.sentinelearth.com/post/carbon-credit-rating-agencies) | M | Using AAA–D makes Sylithe ratings instantly legible to buyers. The existing `land-summary` already emits AAA–D. |
| Sylvera = automated data + human analyst review; scores carbon delivery, additionality, permanence, co-benefits; strong in forestry via geospatial / proprietary Biomass Atlas. | [sentinelearth](https://www.sentinelearth.com/post/carbon-credit-rating-agencies), [srs.credit](https://srs.credit/carbon-credit-risk-analysis) | M | Sylvera's moat is geospatial; Sylithe already has a GEE pipeline — same lane, India-first. |
| Calyx: 940 projects, 27 types, 121 methodologies; programme → methodology → project three-level evaluation; conservative on baselines/over-crediting. | [sentinelearth](https://www.sentinelearth.com/post/carbon-credit-rating-agencies) | M | Adopt the 3-level structure: methodology-level risk is computed **once** and reused across all projects on that methodology (big cost saver). |
| Same letter grade ≠ same meaning; a BB from one agency can be B or BBB at another. | [climate-decode](https://climate-decode.com/insights/vcm-series/vcm-2026-era-of-integrity/who-rates-carbon-rating-agencies) | M | Differentiate on **explainability**: every dimension links to page-level evidence. |
| Carbon Market Watch assessed rating agencies' transparency & methodology. | [CMW report (PDF)](https://carbonmarketwatch.org/wp-content/uploads/2023/09/PCG_CMW_rating_agencies_final_report_.pdf) | H | Transparency of methodology is a known industry criticism → publish Sylithe's method + version it (spec §53). |

### 1.2 Company carbon accounting (Module 1)
Watershed, Persefoni, Sweep, Plan A, Normative, Greenly, EcoVadis — **L** (not re-verified today). Pattern: these are *first-party* tools (a company measures itself from its own ERP data). Sylithe's Module 1 is *third-party intelligence* built from public disclosures — closer to a research terminal than an accounting tool. Not a head-on competitor for the MVP.

### 1.3 Gap Sylithe can own
1. **India-first** — Indian registries' projects + BRSR data + India satellite context; global agencies are thin here.
2. **Evidence-linked AI rating** — every score → claim → document page / satellite layer.
3. **PDD-vs-satellite anomaly check** — automated cross-check of what the project *claims* (area, forest cover, baseline deforestation) against what satellites *show*. Sylithe's GEE pipeline makes this cheap to build.
4. **Cost** — agent pipeline designed for cents per project (see AI research), enabling coverage of *every* Indian project, not a curated subset.

---

## 2. Data sources & licensing

### 2.1 Carbon registries

| Source | Access | Licensing notes | Conf. |
|---|---|---|---|
| **Verra** | Public, unauthenticated project search API (already used in `services/registry.py`); Project Hub APIs need login. | Registry ToU: comply with database rights; **must not use output to misrepresent project quality, ownership or verification status.** → Sylithe ratings must carry the disclaimer in spec §16. | H [Verra ToU Jul 2026](https://verra.org/documents/verra-registry-terms-of-use/), [Registry overview](https://verra.org/registry/overview/) |
| **Gold Standard** | Public Impact Registry with filter + **Export** function; public records incl. project documentation. | Use export / public pages; check ToU before bulk use. | H [GS Impact Registry](https://www.goldstandard.org/impact-registry), [User Guide v1.0](https://goldstandard.cdn.prismic.io/goldstandard/ZuligLVsGrYSvbMV_GoldStandardRegistryUserGuide-v1.0.pdf) |
| **OffsetsDB (CarbonPlan)** | Open-source harmonised dataset + Python tooling covering **Verra, Gold Standard, ACR, CAR, ART TREES, CARB**. | Licence not stated on the API page — verify on GitHub before production. | M [offsets-db-data docs](https://offsets-db-data.readthedocs.io/en/stable/api.html) |

**Decision:** for the hackathon, keep the existing Verra + GS fetchers. For production, evaluate OffsetsDB as the multi-registry base (removes 4 bespoke scrapers). Avoid third-party scrapers (Apify etc.) — ToU risk.

### 2.2 Indian company disclosures (Module 1)

| Claim | Source | Conf. |
|---|---|---|
| BRSR Core = 49 KPIs incl. absolute and intensity GHG (Scope 1 & 2), renewable share, water. | [Greenplaces](https://greenplaces.com/regulation/sebi-business-responsbility-sustainability-report/) | M |
| BRSR must be filed with exchanges in **PDF and XBRL**, same day as the annual report. | [NSE circular NSE/CML/2024/11](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Circular_10052024_1.pdf) | H |
| NSE lists XBRL filing information and an annual-reports/XBRL filings section. | [NSE XBRL info](https://www.nseindia.com/static/companies-listing/xbrl-information), [NSE annual reports](https://www.nseindia.com/companies-listing/corporate-filings-annual-reports-xbrl) | H |
| NSE moved to single filing via API-based integration for BRSR (Mar 2026). | [NSE circular 2026-03](https://nsearchives.nseindia.com/web/circular/2026-03/Circular_on_single_filing_system_through_API-based_integration_-BRSR_20260330193318.pdf) | H |

**⚡ Key cost/latency finding:** BRSR XBRL is *structured*. Scope 1/2, energy, water, waste can be pulled by a **deterministic XBRL parser — zero LLM tokens, milliseconds, and near-perfect accuracy** — with the XBRL tag as the evidence pointer. The LLM is only needed for unstructured sections (litigation, targets, narrative) → a large reduction in Module 1 AI cost.
Open item: confirm NSE's terms for bulk/programmatic download before production (NSE site blocks naive scraping).

### 2.3 Geospatial

| Claim | Source | Conf. |
|---|---|---|
| Since 27 Apr 2026, noncommercial EE projects get a monthly EECU quota (Community tier default); over quota → throttled, not stopped. | [EE noncommercial tiers](https://developers.google.com/earth-engine/guides/noncommercial_tiers) | H |
| **Commercial/operational use by private companies requires a paid commercial EE account** (subscription + compute). | [EE transition to commercial](https://developers.google.com/earth-engine/guides/transition_to_commercial), [EE pricing](https://cloud.google.com/earth-engine/pricing) | H |

**Implications:** (1) a hackathon demo is fine on a noncommercial project; **Sylithe as a paid product must move to a commercial EE plan** — a real cost line. (2) Every EECU saved matters → cache GEE results per geometry (historical years never change) and batch reducers into one call (see `CURRENT_ARCHITECTURE.md` G1/G2).
Datasets already integrated (Dynamic World, ESA WorldCover, Hansen GFC, MODIS burned area, Sentinel-2, CHIRPS, GLO-30, OpenLandMap SOC, ESA CCI biomass, Meta canopy height, JRC GFC2020, WDPA, GHSL, VIIRS) — each has its own licence; audit before commercial launch (spec §41).

---

## 3. Answers to spec §55 (hackathon-grade)

| # | Question | Answer |
|---|---|---|
| 1 | Differentiated product | Evidence-linked, AI-agent carbon project rating for India, with automated PDD-vs-satellite anomaly detection, at a cost low enough to rate every project. |
| 2 | Who pays | Corporate credit buyers & investors (due diligence), then developers (pre-validation readiness). |
| 3 | Strongest initial segment | Indian corporates buying credits under CCTS / net-zero pressure. |
| 4 | Module with strongest immediate fit | **Module 2 (Project Rating)** — has data seed (`projects_cache`) + GEE engine + existing AAA–D grading. |
| 5 | Legally sourceable | Public registry records & documents, BRSR XBRL/PDF, open satellite datasets (licence per dataset). |
| 6 | Needs licensing | GEE for commercial use; any commercial price data; possibly bulk NSE access. |
| 7 | Registries to integrate | Verra, Gold Standard now; ACR/CAR/ART via OffsetsDB later. |
| 9 | Reliably automatable | Registry metadata, XBRL KPIs, satellite statistics, document field extraction with citations. |
| 10 | Keep human-reviewed | Final rating publication, additionality judgement, litigation attribution (spec §10, §54). |
| 15 | MVP | See §4. |
| 18 | Biggest technical risk | LLM hallucinating numbers → mitigated by "numbers come from tools, LLM only interprets" + citations. |
| 19 | Biggest data risk | PDF quality / scanned PDDs; registry ToU. |
| 20 | Biggest legal risk | Ratings being read as certification → mandatory disclaimer; Verra ToU "no misrepresentation". |

## 4. MVP recommendation for the hackathon

Spec §47 proposes Company Intelligence first. **For the hackathon we recommend inverting to Project Rating first (MVP 2)**, because:
- it is the most *vertical-AI* story (agents reading PDDs + satellites),
- it reuses the strongest existing assets (registry cache + GEE),
- the anomaly agent gives a live, judge-visible "AI caught something" moment.

**Demo flow:** pick an Indian ARR/REDD+ project → agents fetch & parse its PDD → parallel dimension agents score it with page citations → satellite agent checks claimed area/forest cover against GEE → orchestrator produces an explainable AAA–D rating, streamed section by section, with cost & latency shown on screen.

Module 1 (BRSR XBRL → KPI dashboard) is the stretch goal; Module 3 already exists.
