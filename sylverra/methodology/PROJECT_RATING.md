# Sylverra Project Rating v0.1

> Spec §13–§17, §28–§30, §53–§54. Implemented in `sylithe-backend/services/project_rating.py`.
> *This is a Sylverra analytical assessment based on available evidence. It is not a registry certification
> or a replacement for formal validation/verification.*

## Pipeline

```text
Project id
 → Project Research Agent (code)  OffsetsDB registry facts · Gold Standard public API record · linked public PDFs
 → Anomaly Agent (code)           issuance spike · vintage concentration · late old-vintage issuance · issuance gap ·
                                  issuance vs registry estimate · cancelled/inactive status · low retirement
 → Methodology KB                 category profile + cited methodology findings (services/methodology_kb.py)
 → 10 dimension agents (DeepSeek T1, parallel) — each sees only its relevant evidence items
 → Evidence validation (code)     any cited evidence id the agent was not given is dropped
 → Weighted rubric (code)         base score → base grade
 → Rating Adjudicator (DeepSeek T2) may shift the grade by at most one notch, with a written reason
```

## Dimensions and weights

| Dimension | Weight |
|---|---|
| Additionality | 20 |
| Baseline integrity | 15 |
| Permanence | 10 (0 when the category stores no carbon, e.g. renewables, cookstoves) |
| Leakage | 5 |
| Monitoring | 10 |
| Verification | 10 |
| Developer | 5 |
| Methodology | 10 |
| Transparency | 5 |
| Co-benefits | 5 |
| Data quality | 5 (computed in code from evidence coverage) |

Each dimension stores: score, risk, reason, evidence (id, what it supports, source, page), data gaps, data state, confidence and the agent's reasoning summary.

Dimension confidence: **High** if a cited item is from a project document, **Medium** if from registry or anomaly data, **Low** if only methodology or category knowledge is cited.

## Grades

| Score | ≥85 | ≥75 | ≥65 | ≥55 | ≥45 | ≥35 | ≥25 | <25 |
|---|---|---|---|---|---|---|---|---|
| Grade | AAA | AA | A | BBB | BB | B | C | D |

- Fewer than 5 scored dimensions → no grade.
- No project documents analysed → the rating is **provisional** with Low overall confidence.

## Methodology knowledge base v0.1 (cited)

| Protocol(s) | Finding | Source |
|---|---|---|
| ACM0002, AMS-I.D | ICVCM: credits from current renewable-energy methodologies will not receive the CCP label (additionality) | [ICVCM](https://icvcm.org/carbon-credits-from-current-renewable-energy-methodologies-will-not-receive-high-integrity-ccp-label/) |
| GS TPDDTEC, GS kitchen cookstoves, AMS-II.G, VMR0006 | Cookstove sample over-credited ~9.2x; only the separate GS metered & measured methodology was close (~1.5x) | [Nature Sustainability 2024](https://www.nature.com/articles/s41893-023-01259-6) |
| VM0007, VM0009, VM0015, VM0006 | Most sampled REDD+ projects showed no significant deforestation reduction vs synthetic controls; ex-ante baselines tended to be overstated | [Science 2023](https://www.science.org/doi/10.1126/science.ade3535) |
| VM0048 | ICVCM approved as meeting the CCPs | [ICVCM](https://icvcm.org/integrity-council-approves-three-redd-methodologies/) |
| VM0047 | ICVCM approved (v1.0 and v1.1) | [Verra](https://verra.org/icvcm-approves-updated-version-of-verras-afforestation-reforestation-and-revegetation-methodology/) |

All sources accessed 2026-09-26. Findings are **class-level** and are always labelled Inference when applied to a specific project.

## Human review (spec §54)

Admins can annotate or override any dimension via `POST /api/intel/ratings/:id/review` (score, risk and a required reason). Each record stores the AI assessment, the human assessment, the reviewer and a timestamp. The AI assessment is never modified.

## Versioning (spec §53)

Each rating stores `methodology_version`, `prompt_version`, `kb_version`, the model ids and the registry snapshot date. Re-rating appends a new record, and the history shows the version each rating was made with.
