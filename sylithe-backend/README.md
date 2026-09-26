# Sylithe — Backend

Flask API, AI agents and pipelines for **Sylithe**, the evidence-backed carbon intelligence platform.

| Area | Code |
|---|---|
| AI gateway (DeepSeek, schema validation, cache, cost/latency logging) | `services/ai.py` |
| Company research pipeline (NSE discovery, BRSR XBRL parser, narrative & financial agents) | `services/company_agents.py`, `brsr_xbrl.py`, `nse.py` |
| KPIs, company rating, emissions pathway, SBTi | `services/company_rating.py`, `company_pathway.py`, `sbti.py` |
| Project rating pipeline (10 dimension agents + adjudicator), registry data, methodology KB | `services/project_rating.py`, `offsetsdb.py`, `methodology_kb.py` |
| Evidence, documents, background jobs | `services/evidence.py`, `documents.py`, `jobs.py` |
| API | `routes/companies.py`, `project_intel.py`, `research.py`, `calculator.py` |

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # MONGO_URI, JWT_SECRET, DEEPSEEK_API_KEY
.venv/bin/python app.py     # http://localhost:5001
```

Full documentation, agent workflows and architecture: see the main repository
[vertex-sylithe](https://github.com/chhelu123/vertex-sylithe#readme).
