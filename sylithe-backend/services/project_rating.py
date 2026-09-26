"""
Module 2 — Carbon Project Rating (spec §13–§17, §28–§30, §53–§54).

  Project id
    → Project Research Agent   registry facts (OffsetsDB) + Gold Standard API detail + linked public docs  [code]
    → Anomaly Agent (code)     issuance cadence, vintage concentration, late old-vintage issuance,
                               issuance vs estimate, retirement pattern                                  [code]
    → Methodology Agent        methodology knowledge base (cited)                                        [KB]
    → Dimension agents         additionality, baseline, permanence, leakage, monitoring, verification,
                               developer, methodology, transparency, co-benefits — run in parallel      [DeepSeek T1]
    → Evidence validation      every cited evidence id must exist in the facts given to that agent      [code]
    → Scoring                  weighted rubric v0.1 → AAA–D                                             [code]
    → Adjudicator              may move the grade by at most one notch, with a written reason           [DeepSeek T2]

Every rating stores methodology/prompt/model versions and is never overwritten (history preserved).
"""
import logging
import statistics
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from db import (
    registry_projects_collection, project_ratings_collection, project_documents_collection, rating_reviews_collection,
)
from services import documents as D
from services import methodology_kb as KB
from services.ai import call_json, AgentError, T1_MODEL, T2_MODEL
from services.evidence import (
    save_evidence, obj, arr, nullable, enum, STR, NUM, INT,
    REPORTED, CALCULATED, INFERENCE, NOT_FOUND, HIGH, MEDIUM, LOW,
)
from services.offsetsdb import developer_portfolio, meta as registry_meta

logger = logging.getLogger(__name__)

METHODOLOGY_VERSION = "Sylithe Project Rating v0.1"
PROMPT_VERSION = "m2-v1"
DISCLAIMER = ("This is a Sylithe analytical assessment based on available evidence. It is not a registry "
              "certification or a replacement for formal validation/verification.")

DIMENSIONS = {
    "additionality": ("Additionality", 20, ["project_additionality"]),
    "baseline": ("Baseline integrity", 15, ["project_baseline", "project_issuance"]),
    "permanence": ("Permanence", 10, ["project_permanence"]),
    "leakage": ("Leakage", 5, ["project_leakage"]),
    "monitoring": ("Monitoring", 10, ["project_monitoring"]),
    "verification": ("Verification", 10, ["project_verification"]),
    "developer": ("Developer", 5, []),
    "methodology": ("Methodology", 10, ["project_methodology"]),
    "transparency": ("Transparency", 5, []),
    "co_benefits": ("Co-benefits", 5, ["project_cobenefits"]),
}
DATA_QUALITY_WEIGHT = 5
GRADES = [(85, "AAA"), (75, "AA"), (65, "A"), (55, "BBB"), (45, "BB"), (35, "B"), (25, "C"), (0, "D")]
GRADE_ORDER = [g for _, g in GRADES]

_DIM_FOCUS = {
    "additionality": "Would the activity have happened without carbon finance? Consider project type, methodology findings, regulatory context and investment/barrier evidence in documents.",
    "baseline": "Is the counterfactual baseline credible and conservative? Consider methodology findings, issuance vs estimates, issuance spikes and document baseline assumptions.",
    "permanence": "Risk that stored carbon is reversed (fire, harvest, land-use change) and whether a buffer/insurance mechanism exists. If the project category has no reversal risk, say so and score high.",
    "leakage": "Risk that emissions shift elsewhere (activity shifting, market effects) and whether leakage is accounted for.",
    "monitoring": "Quality and frequency of monitoring: metered vs surveyed parameters, issuance cadence and gaps, QA/QC evidence.",
    "verification": "Independent validation/verification history: VVB/DOE named, verification opinions, number of verified issuances, corrective actions.",
    "developer": "Developer track record from the registry portfolio: number of projects, issuance/retirement history, categories, cancelled projects.",
    "methodology": "Integrity of the methodology itself, using the cited methodology findings (e.g. ICVCM CCP decisions, peer-reviewed over-crediting studies).",
    "transparency": "How much project information is publicly available: registry fields completeness, documents available, retirement beneficiary disclosure.",
    "co_benefits": "Evidence of SDG, community, biodiversity or livelihood benefits and how they are verified.",
}

_DIM_SCHEMA = obj({
    "score": nullable(NUM),
    "risk": enum("low", "medium", "high", "unknown"),
    "reason": STR,
    "evidence": arr(obj({"evidence_id": STR, "supports": STR})),
    "data_gaps": arr(STR),
    "label": enum(REPORTED, CALCULATED, INFERENCE, "Model estimate", NOT_FOUND),
    "reasoning_summary": STR,
})

_DIM_SYSTEM = """You are one of Sylithe's specialised carbon-project due-diligence agents. You assess ONE
dimension of ONE carbon project using ONLY the evidence items provided, each identified by an evidence_id.

Scoring: 0–100 where higher = lower risk / stronger quality on this dimension. Use null when the evidence is
insufficient to judge, with risk "unknown" and label "Data not found".
Rules:
- Cite evidence only by the evidence_id values given. Do not cite anything else.
- Never invent facts about the project (verifier names, areas, dates, prices). If absent, list it as a data gap.
- Category-level or methodology-level findings are indirect evidence: say so and label the conclusion "Inference".
- Use careful analyst language ("higher/lower risk on this dimension", "evidence suggests"), never "best"/"worst"
  or certification language.
- reason: at most 3 sentences. reasoning_summary: at most 2 sentences on how you weighed the evidence."""

_ADJ_SCHEMA = obj({"adjustment": enum("-1", "0", "+1"), "reason": STR, "summary": STR, "key_risks": arr(STR)})
_ADJ_SYSTEM = """You are Sylithe's Rating Adjudicator. You receive a project's dimension assessments (already
scored and evidence-validated) and a base grade computed by a fixed, documented rubric. You may move the grade
by at most one notch (-1, 0, +1) only when dimension outputs conflict in a way the rubric cannot capture
(e.g. a single severe red flag). Default to 0. Write a plain-language summary (≤4 sentences) of the assessment
and list the key documented risks. Do not introduce facts not present in the dimension outputs."""


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- fact gathering (code)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def gold_standard_detail(project_id, name=None):
    """
    Public Gold Standard project record. OffsetsDB ids (GLD12019) are GS registry numbers, which are not
    always the public-API id, so search `query=GS12019` and accept a hit only when the name matches.
    """
    if not project_id.startswith("GLD"):
        return None
    num = project_id[3:]
    headers = {"User-Agent": _UA, "Accept": "application/json"}

    def similar(a, b):
        return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()

    try:
        r = requests.get("https://public-api.goldstandard.org/projects", params={"query": f"GS{num}", "size": 5},
                         headers=headers, timeout=20)
        if r.status_code == 200:
            hits = [h for h in r.json() if not name or similar(h.get("name"), name) >= 0.5]
            if hits:
                return max(hits, key=lambda h: similar(h.get("name"), name))
        r = requests.get(f"https://public-api.goldstandard.org/projects/{num}", headers=headers, timeout=20)
        if r.status_code == 200 and (not name or similar(r.json().get("name"), name) >= 0.5):
            return r.json()
    except (requests.RequestException, ValueError):
        pass
    return None


class Facts:
    """Evidence items handed to agents. Every item is also persisted in the evidence store."""

    def __init__(self, project_id):
        self.project_id = project_id
        self.items = {}

    def add(self, key, text, *, source, url, value=None, unit=None, label=REPORTED, confidence=MEDIUM,
            page=None, quote=None, kind="registry"):
        eid = save_evidence("project", self.project_id, claim=text, quote=quote or text, source_title=source,
                            url=url, page=page, value=value, unit=unit, label=label, confidence=confidence,
                            verified=True, method=kind, agent="project_research")
        self.items[eid] = {"evidence_id": eid, "key": key, "text": text, "source": source, "url": url,
                           "page": page, "kind": kind, "label": label, "confidence": confidence}
        return eid

    def block(self, kinds=None, keys=None):
        rows = [i for i in self.items.values()
                if (kinds is None or i["kind"] in kinds) and (keys is None or i["key"] in keys)]
        return "<facts>\n" + "\n".join(f'[{i["evidence_id"]}] ({i["kind"]}; {i["source"]}{f", p.{i["page"]}" if i["page"] else ""}) {i["text"]}'
                                       for i in rows) + "\n</facts>"


def _fmt(n):
    return f"{n:,.0f}"


def compute_anomalies(p, gs):
    """Deterministic registry signals (spec §15 Agent 10). Returns list of (key, text, severity)."""
    out = []
    issued = p.get("issued") or 0
    by_year = {y: v for y, v in (p.get("issuance_by_year") or {}).items() if y != "unknown" and v > 0}
    by_vintage = {v: q for v, q in (p.get("issuance_by_vintage") or {}).items() if v not in ("unknown", "") and q > 0}
    snapshot_year = int(((registry_meta() or {}).get("generated_at") or str(_now().year))[:4])

    if by_year and len(by_year) >= 3:
        vals = sorted(by_year.values())
        med = statistics.median(vals)
        top_year, top = max(by_year.items(), key=lambda kv: kv[1])
        if med > 0 and top / med >= 5:
            out.append(("issuance_spike", f"Issuance in {top_year} ({_fmt(top)} credits) is {top / med:.1f}x the median annual issuance ({_fmt(med)}).", "medium"))
    if by_vintage and issued:
        v, q = max(by_vintage.items(), key=lambda kv: kv[1])
        share = q / sum(by_vintage.values())
        if share >= 0.6 and len(by_vintage) >= 3:
            out.append(("vintage_concentration", f"{share:.0%} of issued credits come from a single vintage ({v}).", "low"))
    if p.get("first_issuance_at") and by_vintage:
        try:
            first_issue_year = int(p["first_issuance_at"][:4])
            oldest = min(int(v) for v in by_vintage if v.isdigit())
            if first_issue_year - oldest >= 5:
                out.append(("late_issuance", f"First issuance ({first_issue_year}) came {first_issue_year - oldest} years after the oldest vintage ({oldest}); old vintages issued late warrant review of monitoring history.", "medium"))
        except ValueError:
            pass
    if p.get("last_issuance_at") and issued:
        gap = snapshot_year - int(p["last_issuance_at"][:4])
        if gap >= 4 and p.get("status") not in ("completed",):
            out.append(("issuance_gap", f"No issuance for {gap} years (last issuance {p['last_issuance_at']}), status '{p.get('status')}'.", "medium"))
    if gs and gs.get("estimated_annual_credits") and by_year:
        est = float(gs["estimated_annual_credits"] or 0)
        years = len(by_year)
        if est > 0 and years:
            ratio = (issued / years) / est
            if ratio > 1.25:
                out.append(("issuance_above_estimate", f"Average issuance per active year ({_fmt(issued / years)}) is {ratio:.2f}x the registry estimate of {_fmt(est)} credits/year.", "high"))
    if p.get("status") in ("canceled", "inactive"):
        out.append(("status", f"Registry status is '{p['status']}'.", "high"))
    if issued and (p.get("retirement_ratio") or 0) < 0.05 and snapshot_year - int((p.get("first_issuance_at") or str(snapshot_year))[:4]) >= 3:
        out.append(("low_retirement", f"Only {p.get('retirement_ratio', 0):.1%} of issued credits have been retired after 3+ years.", "low"))
    return out


def gather_facts(p, docs_pages):
    """Build the evidence set for a project. docs_pages: [(doc_record, pages)] of linked public documents."""
    f = Facts(p["project_id"])
    src, url = f"OffsetsDB / {p.get('registry_name')}", p.get("project_url") or (p.get("source") or {}).get("url")
    f.add("identity", f"Project {p['project_id']} '{p.get('name')}', registry {p.get('registry_name')}, country {p.get('country')}, "
                      f"category {p.get('category')}, type {p.get('project_type')}, status {p.get('status')}.", source=src, url=url, confidence=HIGH)
    f.add("methodology_id", f"Registered methodology/protocol: {', '.join(p.get('protocol') or []) or 'not recorded'}.", source=src, url=url, confidence=HIGH)
    f.add("developer_name", f"Project proponent/developer: {p.get('proponent') or 'not recorded'}.", source=src, url=url, confidence=HIGH)
    f.add("issuance_totals", f"Credits issued {_fmt(p.get('issued') or 0)}, retired {_fmt(p.get('retired') or 0)} "
                             f"(retirement ratio {(p.get('retirement_ratio') or 0):.1%}); {p.get('n_issuances', 0)} issuance transactions; "
                             f"first issuance {p.get('first_issuance_at') or 'none'}, last {p.get('last_issuance_at') or 'none'}.",
          source=src, url=url, value=p.get("issued"), unit="credits", confidence=HIGH)
    if p.get("issuance_by_vintage"):
        f.add("vintages", "Issuance by vintage: " + ", ".join(f"{v}: {_fmt(q)}" for v, q in p["issuance_by_vintage"].items()),
              source=src, url=url, confidence=HIGH)
    if p.get("top_beneficiaries"):
        f.add("beneficiaries", "Largest disclosed retirement beneficiaries: " + "; ".join(f"{b['name']} ({_fmt(b['quantity'])})" for b in p["top_beneficiaries"][:5]),
              source=src, url=url, confidence=HIGH)

    gs = gold_standard_detail(p["project_id"], p.get("name"))
    if gs:
        gurl = f"https://registry.goldstandard.org/projects/details/{gs.get('id')}"
        f.add("gs_detail", f"Gold Standard record: methodology '{gs.get('methodology')}', type '{gs.get('type')}', size '{gs.get('size')}', "
                           f"estimated annual credits {gs.get('estimated_annual_credits')}, crediting period {gs.get('crediting_period_start_date')} to "
                           f"{gs.get('crediting_period_end_date')}, standard version {gs.get('gsf_standards_version')}, "
                           f"programme of activities: {gs.get('programme_of_activities')}.", source="Gold Standard public API", url=gurl, confidence=HIGH)
        if gs.get("sustainable_development_goals"):
            sdgs = [s.get("name") if isinstance(s, dict) else str(s) for s in gs["sustainable_development_goals"]]
            f.add("sdgs", f"SDGs claimed on the Gold Standard registry: {', '.join(sdgs)}.", source="Gold Standard public API", url=gurl, confidence=MEDIUM)
        if gs.get("description"):
            f.add("gs_description", f"Registry description: {gs['description'][:1200]}", source="Gold Standard public API", url=gurl, confidence=MEDIUM)

    prof = KB.profile_for(p.get("category"))
    kb_url = "https://github.com/chhelu123/vertex-sylithe/tree/main/sylithe-docs/methodology"
    rev = {True: "relevant", False: "not relevant (no stored biological/geological carbon)", None: "unknown"}[prof["reversal_relevant"]]
    f.add("category_profile", f"Category '{p.get('category')}': reversal risk {rev}; leakage relevance {prof['leakage_relevance']}. "
                              f"Typical risk drivers: {'; '.join(prof['drivers'])}.", source=KB.KB_VERSION, url=kb_url,
          label=INFERENCE, confidence=MEDIUM, kind="methodology_kb")
    for n in KB.notes_for(p.get("protocol")):
        f.add("methodology_note", f"[{n['protocol']}] {n['finding']}", source=n["source"], url=n["url"],
              confidence=HIGH, kind="methodology_kb")

    dev = developer_portfolio(p.get("proponent"))
    if dev:
        f.add("developer_portfolio", f"Developer portfolio (all registries in OffsetsDB): {dev['projects']} projects "
                                     f"({dev['with_issuance']} with issuance), total issued {_fmt(dev['total_issued'])}, retired {_fmt(dev['total_retired'])}, "
                                     f"registries {', '.join(dev['registries'])}, countries {', '.join(dev['countries'][:8])}, statuses {dev['statuses']}.",
              source="OffsetsDB (aggregated)", url=(p.get("source") or {}).get("url"), confidence=HIGH, kind="registry")

    anomalies = compute_anomalies(p, gs)
    for key, text, sev in anomalies:
        f.add(f"anomaly_{key}", f"Registry signal ({sev}): {text}", source="Sylithe anomaly checks (computed from OffsetsDB)",
              url=url, label=CALCULATED, confidence=HIGH, kind="anomaly")

    for doc, pages in docs_pages:
        for topic in {t for _, _, ts in DIMENSIONS.values() for t in ts}:
            for num, text in D.select_pages(pages, [topic], max_pages=2, max_chars=7000):
                f.add(topic, f"{doc['title']} page {num} excerpt: {text[:3500]}", source=doc["title"], url=doc["source_url"],
                      page=num, confidence=HIGH, kind="document", quote=text[:300])
    return f, gs, anomalies


# ---------------------------------------------------------------- agents

def _dimension_agent(job, project, facts, dim_key):
    label, _, topics = DIMENSIONS[dim_key]
    keys = {
        "additionality": ["identity", "methodology_id", "gs_detail", "gs_description", "category_profile", "methodology_note"],
        "baseline": ["identity", "methodology_id", "issuance_totals", "vintages", "gs_detail", "category_profile", "methodology_note"],
        "permanence": ["identity", "category_profile", "gs_detail", "gs_description"],
        "leakage": ["identity", "category_profile", "gs_description"],
        "monitoring": ["identity", "issuance_totals", "vintages", "category_profile", "methodology_note"],
        "verification": ["identity", "issuance_totals", "gs_detail"],
        "developer": ["developer_name", "developer_portfolio", "identity"],
        "methodology": ["methodology_id", "category_profile", "methodology_note", "gs_detail"],
        "transparency": ["identity", "methodology_id", "developer_name", "issuance_totals", "beneficiaries", "gs_detail", "gs_description"],
        "co_benefits": ["identity", "sdgs", "gs_description"],
    }[dim_key]
    keys = set(keys) | {k for k in (i["key"] for i in facts.items.values()) if k.startswith("anomaly_")} | set(topics)
    block = facts.block(keys=keys)
    user = (f"Dimension: {label}\nFocus: {_DIM_FOCUS[dim_key]}\n\nProject: {project['project_id']} — {project.get('name')}\n\n{block}")
    out = call_json(f"dim_{dim_key}", _DIM_SYSTEM, user, _DIM_SCHEMA, effort="low", prompt_version=PROMPT_VERSION,
                    context={"job_id": job.id if job else None, "project_id": project["project_id"]}, max_tokens=4000)
    if job:
        job.add_cost(out["cost_usd"])
    res = out["result"]
    given = {e for e, i in facts.items.items() if i["key"] in keys}
    valid = [e for e in res["evidence"] if e["evidence_id"] in given]
    dropped = len(res["evidence"]) - len(valid)
    kinds = {facts.items[e["evidence_id"]]["kind"] for e in valid}
    if res["score"] is None:
        conf = None
    elif "document" in kinds:
        conf = HIGH
    elif kinds & {"registry", "anomaly"}:
        conf = MEDIUM
    else:
        conf = LOW
    label_out = res["label"] if valid or res["score"] is None else INFERENCE
    return {
        "key": dim_key, "label": label, "score": None if res["score"] is None else round(max(0, min(100, res["score"])), 1),
        "risk": res["risk"], "reason": res["reason"], "reasoning_summary": res["reasoning_summary"],
        "evidence": [{**e, "source": facts.items[e["evidence_id"]]["source"], "url": facts.items[e["evidence_id"]]["url"],
                      "page": facts.items[e["evidence_id"]]["page"], "kind": facts.items[e["evidence_id"]]["kind"]} for e in valid],
        "evidence_dropped": dropped, "data_gaps": res["data_gaps"], "status": label_out, "confidence": conf,
        "model": out["model"], "cache_hit": out["cache_hit"],
    }


def _grade(score):
    return next(g for t, g in GRADES if score >= t)


def _shift(grade, n):
    i = GRADE_ORDER.index(grade) - n  # list is best→worst, so +1 notch moves left
    return GRADE_ORDER[max(0, min(len(GRADE_ORDER) - 1, i))]


def rate_project(job, project_id, requested_by=None):
    p = registry_projects_collection.find_one({"_id": project_id})
    if not p:
        raise AgentError(f"Project {project_id} not found in registry data.")

    step = (lambda *a, **k: job.step(*a, **k)) if job else (lambda *a, **k: None)
    step("research", "Project Research Agent — registry, Gold Standard API, linked documents")
    docs_pages = []
    for doc in project_documents_collection.find({"project_id": project_id, "status": {"$in": ["parsed", "linked"]}}):
        try:
            raw = D.download_pdf(doc["source_url"])
            docs_pages.append((doc, D.parse_pdf(raw)))
        except D.DocumentError as e:
            project_documents_collection.update_one({"_id": doc["_id"]}, {"$set": {"status": "failed", "error": str(e)[:200]}})
    facts, gs, anomalies = gather_facts(p, docs_pages)
    step("research", "Project Research Agent — registry, Gold Standard API, linked documents", "done",
         f"{len(facts.items)} evidence items, {len(docs_pages)} documents")
    step("anomaly", "Anomaly Agent — registry consistency checks", "done",
         f"{len(anomalies)} signal(s)" if anomalies else "no anomalies detected")

    step("dimensions", "Dimension agents (10, in parallel)")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {k: pool.submit(_dimension_agent, job, p, facts, k) for k in DIMENSIONS}
        dims, failures = [], []
        for k, fut in futures.items():
            try:
                dims.append(fut.result())
            except AgentError as e:
                failures.append(k)
                dims.append({"key": k, "label": DIMENSIONS[k][0], "score": None, "risk": "unknown",
                             "reason": f"Agent failed: {e}", "evidence": [], "data_gaps": [], "status": NOT_FOUND, "confidence": None})
    step("dimensions", "Dimension agents (10, in parallel)", "done" if not failures else "failed",
         f"{sum(1 for d in dims if d['score'] is not None)}/10 dimensions scored" + (f"; failed: {', '.join(failures)}" if failures else ""))

    prof = KB.profile_for(p.get("category"))
    weights = {k: w for k, (_, w, _) in DIMENSIONS.items()}
    if prof["reversal_relevant"] is False:
        weights["permanence"] = 0  # no stored carbon to reverse — don't let it inflate the score
    doc_kinds = sum(1 for i in facts.items.values() if i["kind"] == "document")
    coverage = min(100, 25 + 15 * len(docs_pages) + (20 if gs else 0) + (10 if p.get("issued") else 0)
                   + (10 if doc_kinds else 0))
    dq = {"key": "data_quality", "label": "Data quality", "score": float(coverage), "risk": "low" if coverage >= 70 else "medium" if coverage >= 45 else "high",
          "reason": f"{len(docs_pages)} project documents analysed; {'Gold Standard registry record; ' if gs else ''}"
                    f"registry transaction history {'available' if p.get('issued') else 'not available'}.",
          "evidence": [], "data_gaps": [] if docs_pages else ["No project documents (PDD, monitoring or verification reports) analysed"],
          "status": CALCULATED, "confidence": HIGH}
    dims.append(dq)
    weights["data_quality"] = DATA_QUALITY_WEIGHT

    scored = [d for d in dims if d["score"] is not None and weights.get(d["key"], 0) > 0]
    wsum = sum(weights[d["key"]] for d in scored)
    base_score = round(sum(d["score"] * weights[d["key"]] for d in scored) / wsum, 1) if wsum else None
    provisional = not docs_pages
    if base_score is None or len(scored) < 5:
        grade, base_grade, adj = None, None, {"adjustment": "0", "reason": "Insufficient scored dimensions.", "summary": "", "key_risks": []}
    else:
        base_grade = _grade(base_score)
        step("adjudicate", "Rating Adjudicator")
        try:
            payload = [{k: d.get(k) for k in ("key", "label", "score", "risk", "reason", "confidence", "status")} for d in dims]
            out = call_json("rating_adjudicator", _ADJ_SYSTEM,
                            f"Project: {p['project_id']} — {p.get('name')} ({p.get('category')}, {p.get('registry_name')})\n"
                            f"Base score {base_score} → base grade {base_grade}.\n<facts>\n{payload}\n</facts>",
                            _ADJ_SCHEMA, tier=2, effort="low", prompt_version=PROMPT_VERSION,
                            context={"job_id": job.id if job else None, "project_id": project_id}, max_tokens=3000)
            if job:
                job.add_cost(out["cost_usd"])
            adj = out["result"]
            step("adjudicate", "Rating Adjudicator", "done", f"adjustment {adj['adjustment']}")
        except AgentError as e:
            adj = {"adjustment": "0", "reason": f"Adjudicator unavailable: {e}", "summary": "", "key_risks": []}
            step("adjudicate", "Rating Adjudicator", "failed", str(e)[:200])
        grade = _shift(base_grade, int(adj["adjustment"]))

    confs = [d["confidence"] for d in dims if d.get("confidence")]
    overall_conf = LOW if provisional or not confs else (HIGH if confs.count(HIGH) >= len(confs) * 0.6 else MEDIUM)
    rating = {
        "project_id": project_id, "project_name": p.get("name"), "registry": p.get("registry_name"),
        "methodology_version": METHODOLOGY_VERSION, "prompt_version": PROMPT_VERSION, "kb_version": KB.KB_VERSION,
        "models": {"dimensions": T1_MODEL, "adjudicator": T2_MODEL},
        "registry_snapshot": (registry_meta() or {}).get("generated_at"),
        "overall_score": base_score, "base_grade": base_grade, "grade": grade,
        "adjustment": adj, "provisional": provisional, "confidence": overall_conf,
        "dimensions": dims, "weights": weights, "anomalies": [{"key": k, "text": t, "severity": s} for k, t, s in anomalies],
        "documents_analysed": [{"title": d["title"], "url": d["source_url"], "pages": len(pg)} for d, pg in docs_pages],
        "evidence_count": len(facts.items), "disclaimer": DISCLAIMER,
        "requested_by": requested_by, "created_at": _now(),
        "note": ("Provisional: registry, methodology and developer evidence only — no project documents analysed."
                 if provisional else None),
    }
    res = project_ratings_collection.insert_one(rating)
    registry_projects_collection.update_one({"_id": project_id}, {"$set": {
        "latest_rating": {"grade": grade, "score": base_score, "confidence": overall_conf, "provisional": provisional,
                          "rating_id": str(res.inserted_id), "created_at": rating["created_at"],
                          "methodology_version": METHODOLOGY_VERSION}}})
    return {"rating_id": str(res.inserted_id), "grade": grade, "score": base_score}


def apply_reviews(rating):
    """Overlay human analyst reviews (spec §54) without mutating the stored AI assessment."""
    reviews = list(rating_reviews_collection.find({"rating_id": str(rating["_id"])}, {"_id": 0}).sort("created_at", 1))
    by_dim = {}
    for r in reviews:
        by_dim[r["dimension"]] = r
    for d in rating["dimensions"]:
        if d["key"] in by_dim:
            d["human_review"] = by_dim[d["key"]]
    rating["reviews"] = reviews
    return rating
