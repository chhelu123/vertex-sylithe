# AI Cost, Latency & Performance Research

> Spec §42, §43 (AI), §28. Date accessed: **2026-09-26**.
> Goal: the Sylverra agent layer must be **cheap per project, fast to first result, and accurate** — in that order of design pressure, never at the expense of the no-hallucination rule (§52).

---

## 1. Model pricing snapshot (USD per 1M tokens)

| Model | Input | Cached input | Output | Source | Conf. |
|---|---|---|---|---|---|
| DeepSeek V4.1 Flash (off-peak) | 0.15 | 0.003 | 0.60 | [aipricing.guru](https://www.aipricing.guru/deepseek-pricing/), [BenchLM](https://benchlm.ai/deepseek/api-pricing) | M |
| DeepSeek V4.1 Flash (peak) | 0.30 | 0.006 | 1.20 | same | M |
| DeepSeek V4 Pro (off-peak) | 0.66 | 0.022 | 1.98 | [devtk.ai](https://devtk.ai/en/models/deepseek-v4/), [CloudZero](https://www.cloudzero.com/blog/deepseek-pricing/) | M |
| Gemini 2.5 Flash-Lite (retiring 16 Oct 2026) | 0.10 | — | 0.40 | [BenchLM](https://benchlm.ai/google/api-pricing), [Morph](https://www.morphllm.com/gemini-api-pricing) | M |
| Gemini 3.7 Flash (intro price to 31 Dec 2026) | 0.75 | — | 3.75 | same | M |
| Claude Haiku 4.5 | 1.00 | ~0.10 | 5.00 | Anthropic model table (cached 2026-06-24) | H |
| Claude Sonnet 5 | 2.00 | ~0.20 | 10.00 | same | H |
| Claude Opus 5 | 5.00 | ~0.50 | 25.00 | same | H |

Notes
- **DeepSeek peak windows** (weekdays 01:00–04:00 & 06:00–10:00 UTC = **06:30–09:30 & 11:30–15:30 IST**) cost 2×. Schedule bulk/background rating jobs off-peak. (M)
- Cached-input prices are ~10% of list on both DeepSeek and Anthropic → **prefix caching is the single largest free lever.**
- Anthropic Message Batches run at **50% cost** (async) — ideal for nightly portfolio re-rating. (H)
- The current code already holds a DeepSeek key → **DeepSeek is the hackathon default**; the gateway (below) keeps the provider swappable.

---

## 2. Where cost and latency actually come from

For an agentic rating pipeline, spend is dominated by **input tokens re-read by many agents** (a 100-page PDD ≈ 50–70k tokens), not by output. Latency is dominated by **serial steps** (sequential LLM calls, sequential GEE `.getInfo()` round-trips) and **reasoning-model thinking time**.

So the design levers, ranked by impact:

| # | Lever | Cuts | How in Sylverra |
|---|---|---|---|
| 1 | **Don't call an LLM when code can answer** | cost, latency, hallucination | XBRL parser for BRSR KPIs; GEE stats for land; registry API for issuance. LLM only *interprets* numbers it's given. |
| 2 | **Parse once, retrieve per agent** | cost (≈10×) | PDD parsed & chunked once; each dimension agent gets only its top-k relevant chunks (~4–8k tokens), not the whole PDD. |
| 3 | **Result caching** (content-addressed) | cost & latency → ~0 on repeat | Key = `sha256(agent, prompt_version, model, input_facts)`. Same project, same docs → instant, free. |
| 4 | **Prompt-prefix caching** | input cost ~90% on shared prefix | Stable system prompt + methodology rubric first, variable facts last. |
| 5 | **Model routing (tiers)** | cost 5–30× on bulk work | T0 code → T1 fast/cheap model for extraction & narrative → T2 reasoning model only for final rating adjudication. |
| 6 | **Parallel fan-out** | latency ≈ slowest agent, not the sum | Dimension agents run concurrently (asyncio). |
| 7 | **Streaming (SSE)** | perceived latency | UI shows each dimension as it finishes; time-to-first-result in seconds. |
| 8 | **Methodology-level reuse** (Calyx-style 3 levels) | cost | Methodology risk (e.g. VM0047) computed once, reused across every project on it. |
| 9 | **Structured output + validation** | retries, failure cost | JSON schema per agent; evidence ids must exist in the retrieved chunks, otherwise the claim is dropped. |
| 10 | **Budgets & telemetry** | runaway cost | Per-run token budget; every call logged (model, tokens in/out/cached, ms, $). |
| 11 | **Off-peak / batch scheduling** | cost 50% | Background re-rating in DeepSeek off-peak or Anthropic Batches. |

---

## 3. Cost model — rating one project

Assumptions (stated, spec §45): PDD ≈ 60k tokens; 8 dimension agents; each writes ~800 output tokens; adjudicator writes ~1.5k.

| Design | Calculation | ≈ Cost / project | Latency shape |
|---|---|---|---|
| **Naive**: 8 agents each read whole PDD on a frontier model (Opus 5) | 8×60k×$5 + 8×0.8k×$25 + adjudicator | **≈ $2.70** | serial ≈ 8× single call |
| **Optimised, Claude tiers**: retrieval (6k/agent) on Haiku 4.5 + Sonnet 5 adjudicator (20k in) | 8×6k×$1 + 8×0.8k×$5 + 20k×$2 + 1.5k×$10 | **≈ $0.13** | parallel ≈ 1 agent + adjudicator |
| **Optimised, DeepSeek**: retrieval on V4.1 Flash + V4 Pro adjudicator (off-peak) | 8×6k×$0.15 + 8×0.8k×$0.6 + 20k×$0.66 + 1.5k×$1.98 | **≈ $0.03** | parallel |
| **Cache hit** (same project, same docs) | lookup | **$0.00** | ~ms |

→ **~20–100× cheaper than naive** with the same (or better, because focused) evidence.

### Scale (spec §42) — LLM spend only, optimised DeepSeek path, one full rating each

| Scale | Projects | Companies (BRSR: XBRL = $0; LLM only for ~20k tokens of narrative) | Est. LLM $ |
|---|---|---|---|
| 1,000 | $30 | ~$5 | **~$35** |
| 10,000 | $300 | ~$50 | **~$350** |
| 100,000 | $3,000 | ~$500 | **~$3,500** |

These are rough estimates (LLM only). At scale the dominant costs become **GEE commercial compute, PDF/OCR, and storage** — not LLM tokens. GEE commercial rates were not retrievable today; get a quote (research open item).

---

## 4. Latency budget (target for the demo)

| Stage | Current code | Target |
|---|---|---|
| Land history (GEE) | ~13 sequential `.getInfo()` | 1 batched call; cached → < 1 s on repeat |
| AI report narrative | 1 reasoning-model call, 60–90 s (per repo comment) | Parallel fast-model sections, first section streamed in a few seconds |
| Full project rating | n/a | First dimension on screen in seconds; full rating well under a minute; repeat = instant |

---

## 5. Accuracy / performance guardrails (non-negotiable, §29, §52)

1. **Numbers come from tools, never from the model.** Agents receive numbers; outputs referencing a number must cite the fact id it came from.
2. **Evidence validation in code:** every `evidence_id` in an agent's output must exist in the chunks it was given; otherwise the claim is dropped and confidence lowered.
3. **Labels:** `Reported` / `Estimated` / `Model estimate` / `Inference` / `Data not found` on every value.
4. **Documents are untrusted input:** wrapped as data, never concatenated into the instruction section; agents told to ignore instructions inside documents (spec §51).
5. **Versioning:** each rating stores `methodology_version`, `prompt_version`, and model ids (spec §53).

## 6. Decision

- **Hackathon:** DeepSeek V4.1 Flash (T1) + DeepSeek V4 Pro (T2) behind a provider-agnostic `ai_gateway`, since the key already exists and it's the cheapest.
- **Production:** keep the gateway; A/B tiers on an eval set (e.g. Claude Haiku 4.5 / Sonnet 5 vs DeepSeek) and choose per route on *cost per correct rating*, not per token.
