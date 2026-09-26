# Sylithe Company Carbon Rating v0.1

> Spec §11–§12, §30, §52–§53. Implemented in `sylithe-backend/services/company_rating.py`.
> Scores are computed by code from stored, evidence-linked metrics. No LLM sets a score.

## Data sources and confidence

| Source | How it's read | Confidence |
|---|---|---|
| SEBI BRSR XBRL (NSE filing) | Deterministic parser, `services/brsr_xbrl.py` | **High**, the XBRL element is the evidence pointer |
| BRSR PDF | Carbon Narrative Agent (DeepSeek) extracts targets, credits, Scope 3 and transition actions | **High** if the quote is found on the cited page (±1 page), otherwise **Low** |
| Annual report PDF | Financial & Litigation Agent (DeepSeek) | Same quote-verification rule |
| Sums/ratios of disclosed values | Code | **Calculated**; confidence = weakest input |

Unit note: in the SEBI `in-capmkt` taxonomy the unit `MtCO2e` means **metric tonnes**. For example, Reliance's FY2025-26 Scope 1 is 36,350,070.

Scope 2 is kept on **one basis per time series**: the basis with the most periods wins, and a tie goes to the BRSR-tagged total. Location-based and market-based values are never mixed across years. The Narrative Agent may label a value market- or location-based only when the quote says so.

## KPIs (15)

Scope 1 · Scope 2 · Scope 3 · Scope 1+2 · emissions intensity (tCO2e per ₹ crore revenue) · renewable-energy share · total energy · energy intensity · waste recovered % · water intensity · water withdrawal · reduction vs baseline · carbon credits retired · target progress · climate disclosure score.

Every KPI shows: current, period, previous, change %, target/progress where computable, source + evidence id, confidence, and data state (Reported / Calculated / Data not found).

## Dimensions (0–100) and weights

| Dimension | Weight | Rule |
|---|---|---|
| Disclosure quality | 15 | Share of 11 items present (Scope 1, 2, 3, energy, renewable share, water, waste, intensity, two-year history, targets, external assurance) |
| Emissions trajectory | 20 | `60 − 4 × YoY % change` in Scope 1+2 (−10% → 100, +10% → 20), clamped |
| Carbon intensity trend | 15 | Same formula on revenue intensity. Sector benchmarks are not applied in v0.1 |
| Renewable-energy transition | 15 | `1.2 × renewable share %` |
| Climate target credibility | 15 | Dated net-zero target 30 + interim target with base year 30 + SBTi validated 30 (committed 15) + renewable target 10 |
| Carbon-credit quality & use | 5 | 70 if every disclosure names registry and project, else 40. Not scored if no credits are disclosed |
| Climate & environmental legal exposure | 5 | Explicit climate litigation 30 · environmental proceedings/penalties 60 · none found in reviewed pages 90 (**Inference**, Low confidence) |
| Data confidence | 10 | Share of KPI values at High confidence |

**Legal-cost rule (spec §10):** a legal expense counts as climate-related only when the source explicitly says so. A "Legal and professional fees" line is shown as a P&L line, never as climate litigation spend. Code enforces this even if the agent mislabels it.

## Overall grade

Weighted mean over the dimensions that were scored. The grade is published only if **≥ 5 dimensions are scored and data confidence ≥ 50**; otherwise it reads "Insufficient data".

| Score | Grade | Band |
|---|---|---|
| ≥ 80 | A | Leader |
| ≥ 65 | B | Advanced |
| ≥ 50 | C | Developing |
| ≥ 35 | D | Lagging |
| < 35 | E | Weak |

Each recompute appends a new record to `company_ratings` with its methodology version. History is never rewritten.

## Known limitations (v0.1)

- No sector benchmarks: intensity is scored on its trend, not its level against peers.
- Coverage is limited to NSE-listed equities (the NSE filings APIs are the discovery source).
- Litigation is checked against annual-report pages only. There is no web or court-database search yet.

## Emissions pathway & carbon suggestion (Sylithe Emissions Pathway v0.1)

Implemented in `sylithe-backend/services/company_pathway.py`, with SBTi data from `services/sbti.py`.

| Question | How it is answered |
|---|---|
| How much is the company emitting? | Disclosed Scope 1+2 per period (BRSR) |
| How much should it emit? | 1.5°C pathway: **4.2% of base-year emissions per year, linear** (SBTi absolute contraction approach); net zero = **≥90% below base year by 2050** |
| Its own target | An SBTi-validated Scope 1+2 near-term target from the [SBTi Target Dashboard](https://sciencebasedtargets.org/target-dashboard), when base-year emissions are disclosed; otherwise the disclosed net-zero or reduction target (linear) |
| Gap | Actual − 1.5°C pathway for each disclosed year; cut needed by 2030 |
| Levers | Rules over the company's own data: Scope 2 share and renewable %, Scope 1 share, YoY change, Scope 3 disclosure, SBTi status (not committed / commitment removed) |
| Carbon suggestion | Sized to the current gap (or to net-zero residual if on track). Projects matched in the same country: removals before avoidance, methodologies with cited integrity concerns excluded, Sylithe grades below BBB excluded. **Credits never count toward reduction targets.** |

SBTi data (companies and targets) is refreshed weekly and matched by ISIN first, then by exact normalised name, so a subsidiary (e.g. Reliance Jio) is never attached to its parent.
