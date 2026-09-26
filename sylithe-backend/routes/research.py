"""
Global AI search + Research Workspace (spec §37–§39) and the Overview dashboard API.

The research agent answers only from Sylithe's own evidence-backed data via tools
(companies, KPIs, project registry facts, ratings). It keeps conversational context per session.
"""
import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from db import (
    companies_collection, registry_projects_collection, project_ratings_collection, research_sessions_collection,
    company_metrics_collection, company_documents_collection, jobs_collection, agent_runs_collection,
    evidence_collection,
)
from services import nse, offsetsdb
from services.ai import run_tools, AgentError, ai_configured
from utils.auth import require_auth
from utils.serialize import clean

logger = logging.getLogger(__name__)
research_bp = Blueprint("research", __name__)


# ---------------------------------------------------------------- tools

def _t_search_companies(query, limit=8):
    rx = {"$regex": re.escape(query), "$options": "i"}
    tracked = list(companies_collection.find({"$or": [{"name": rx}, {"aliases": rx}, {"industry": rx}]},
                                             {"slug": 1, "name": 1, "industry": 1, "rating.grade": 1, "status": 1, "listing": 1}).limit(limit))
    matches = []
    try:
        matches = nse.resolve(query, limit=5)
    except nse.NseError:
        pass
    return {"tracked_companies": clean(tracked),
            "nse_listed_matches_not_yet_researched": [m for m in matches if m["symbol"] not in {(t.get("listing") or {}).get("nse_symbol") for t in tracked}]}


def _t_get_company(slug):
    c = companies_collection.find_one({"_id": slug}, {"kpis": 1, "rating": 1, "name": 1, "industry": 1, "targets": 1,
                                                     "carbon_credits": 1, "legal_disclosures": 1, "data_gaps": 1,
                                                     "emissions_trend": 1, "listing": 1, "assurance": 1, "pathway": 1})
    if not c:
        return {"error": "company not tracked — it must be researched first"}
    for k in c.get("kpis") or []:
        if k:
            k["sources"] = [{"title": s.get("title"), "page": s.get("page"), "evidence_id": s.get("evidence_id")} for s in k.get("sources", [])]
    pw = c.get("pathway") or {}
    c["pathway"] = {k: pw.get(k) for k in ("rows", "gap_latest", "on_track", "required_annual_rate_to_2030", "sbti", "levers",
                                          "company_target", "assumptions")} | {
        "credit_suggestion": {k: v for k, v in (pw.get("credit_suggestion") or {}).items() if k != "projects"} | {
            "projects": [{x: p.get(x) for x in ("project_id", "name", "kind", "category", "grade", "available")}
                         for p in (pw.get("credit_suggestion") or {}).get("projects", [])]}}
    c["rating"] = {k: (c.get("rating") or {}).get(k) for k in ("grade", "overall_score", "confidence", "status", "note", "dimensions", "methodology_version")}
    for key in ("targets", "carbon_credits", "legal_disclosures"):
        c[key] = [{k: v for k, v in x.items() if k in ("type", "description", "activity", "quantity_tco2e", "category",
                                                       "climate_related_explicit", "page", "source_title", "evidence_id", "quote")}
                  for x in (c.get(key) or [])][:12]
    return clean(c)


def _t_rank_companies(kpi, order="desc", limit=10):
    rows = []
    for c in companies_collection.find({"kpis": {"$exists": True}}, {"name": 1, "slug": 1, "kpis": 1}):
        k = next((x for x in c.get("kpis") or [] if x and x["key"] == kpi and x.get("current") is not None), None)
        if k:
            rows.append({"company": c["name"], "slug": c["slug"], "value": k["current"], "unit": k.get("unit"),
                         "period": k.get("period"), "confidence": k.get("confidence"),
                         "evidence_ids": [s.get("evidence_id") for s in k.get("sources", []) if s]})
    rows.sort(key=lambda r: r["value"], reverse=(order == "desc"))
    return {"kpi": kpi, "companies_with_data": len(rows), "ranking": rows[:limit],
            "note": "Only companies already researched in Sylithe are included."}


def _t_search_projects(query=None, country=None, category=None, registry=None, protocol=None, rated_only=False, limit=10):
    q = {}
    if query:
        rx = {"$regex": re.escape(query), "$options": "i"}
        q["$or"] = [{"name": rx}, {"project_id": rx}, {"proponent": rx}]
    if country:
        q["country"] = {"$regex": f"^{re.escape(country)}$", "$options": "i"}
    if category:
        q["category"] = category
    if registry:
        q["registry"] = registry
    if protocol:
        q["protocol"] = protocol.lower()
    if rated_only:
        q["latest_rating"] = {"$exists": True}
    rows = list(registry_projects_collection.find(q, {"_id": 0, "project_id": 1, "name": 1, "registry": 1, "country": 1, "category": 1,
                                                      "protocol": 1, "proponent": 1, "issued": 1, "retired": 1, "status": 1,
                                                      "latest_rating": 1}).sort("issued", -1).limit(min(limit, 25)))
    return {"total_matching": registry_projects_collection.count_documents(q), "projects": clean(rows),
            "source": (offsetsdb.meta() or {}).get("citation")}


def _t_get_project(project_id):
    p = registry_projects_collection.find_one({"_id": project_id}, {"issuance_by_year": 0, "retirement_by_year": 0})
    if not p:
        return {"error": "project not found"}
    r = project_ratings_collection.find_one({"project_id": project_id}, sort=[("created_at", -1)])
    if r:
        p["rating"] = {k: r.get(k) for k in ("grade", "overall_score", "confidence", "provisional", "note", "anomalies", "methodology_version", "created_at")}
        p["rating"]["dimensions"] = [{k: d.get(k) for k in ("key", "label", "score", "risk", "reason", "confidence", "data_gaps")}
                                     | {"evidence": [{"evidence_id": e["evidence_id"], "source": e.get("source"), "page": e.get("page")} for e in d.get("evidence", [])]}
                                     for d in r["dimensions"]]
    else:
        p["rating"] = "not yet rated — the user can run a rating from the project page"
    return clean(p)


def _t_get_evidence(evidence_id):
    e = evidence_collection.find_one({"evidence_id": evidence_id}, {"_id": 0})
    return clean(e) if e else {"error": "evidence not found"}


TOOLS = [
    {"type": "function", "function": {"name": "search_companies", "description": "Find companies tracked in Sylithe (and NSE-listed matches not yet researched).",
                                      "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_company", "description": "Get a tracked company's KPIs, rating, targets, carbon credits, legal disclosures, evidence ids, and its emissions pathway (actual vs 1.5°C-aligned emissions, gap, SBTi status, reduction levers and matched carbon projects).",
                                      "parameters": {"type": "object", "properties": {"slug": {"type": "string"}}, "required": ["slug"]}}},
    {"type": "function", "function": {"name": "rank_companies", "description": "Rank researched companies by a KPI key: scope1, scope2, total_emissions, emissions_intensity, renewable_pct, total_energy, waste_recovery, water_withdrawal, disclosure_score.",
                                      "parameters": {"type": "object", "properties": {"kpi": {"type": "string"}, "order": {"type": "string", "enum": ["asc", "desc"]}, "limit": {"type": "integer"}}, "required": ["kpi"]}}},
    {"type": "function", "function": {"name": "search_projects", "description": "Search carbon projects (Verra, Gold Standard, ACR, CAR, ART, Isometric, Cercarbono). category ∈ forest, renewable-energy, energy-efficiency, ghg-management, agriculture, fuel-switching, land-use, biomass-cdr. registry ∈ verra, gold-standard, american-carbon-registry, climate-action-reserve.",
                                      "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "country": {"type": "string"}, "category": {"type": "string"},
                                                                                      "registry": {"type": "string"}, "protocol": {"type": "string"}, "rated_only": {"type": "boolean"}, "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "get_project", "description": "Get a project's registry facts and latest Sylithe rating with dimension reasons and evidence ids.",
                                      "parameters": {"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}}},
    {"type": "function", "function": {"name": "get_evidence", "description": "Get the source, page and verbatim quote behind an evidence id.",
                                      "parameters": {"type": "object", "properties": {"evidence_id": {"type": "string"}}, "required": ["evidence_id"]}}},
]
HANDLERS = {"search_companies": _t_search_companies, "get_company": _t_get_company, "rank_companies": _t_rank_companies,
            "search_projects": _t_search_projects, "get_project": _t_get_project, "get_evidence": _t_get_evidence}

SYSTEM = """You are Sylithe's research analyst for company carbon intelligence and carbon-project ratings.
Answer using ONLY data returned by your tools. Always call tools before answering factual questions.

Evidence rules:
- Every number or factual claim must be followed by its citation: an evidence id in square brackets like
  [ev_1a2b3c4d5e6f7a8b], or for registry facts "(OffsetsDB)". Never invent evidence ids.
- Distinguish Reported / Calculated / Estimated / Inference / Data not found.
- If a company is not tracked, say so and tell the user they can run the research agents from the Companies page.
  If a project is unrated, say so and suggest running a rating.
- Never describe a project as "best"; use "higher/lower on this dimension", evidence strength and documented risks.
- No investment advice or return promises.
Format: concise markdown with short sections and tables where helpful."""


def _session(sid, email):
    try:
        return research_sessions_collection.find_one({"_id": ObjectId(sid), "owner_email": email})
    except (InvalidId, TypeError):
        return None


@research_bp.route("/research/ask", methods=["POST", "OPTIONS"])
@require_auth
def ask():
    if not ai_configured():
        return jsonify({"status": "error", "message": "AI is not configured on the server (DEEPSEEK_API_KEY)."}), 503
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()[:2000]
    if not question:
        return jsonify({"status": "error", "message": "question is required"}), 400
    email = request.current_user.get("email")
    sess = _session(body.get("session_id"), email) if body.get("session_id") else None
    history = (sess or {}).get("messages", [])[-12:]
    msgs = [{"role": m["role"], "content": m["content"]} for m in history] + [{"role": "user", "content": question}]
    try:
        out = run_tools("research_agent", SYSTEM, msgs, TOOLS, HANDLERS, context={"user": email})
    except AgentError as e:
        return jsonify({"status": "error", "message": str(e)}), 502
    cited = sorted(set(re.findall(r"\[(ev_[0-9a-f]{16})\]", out["answer"])))
    known = {e["evidence_id"]: clean(e) for e in evidence_collection.find({"evidence_id": {"$in": cited}}, {"_id": 0})}
    now = datetime.now(timezone.utc)
    new = [{"role": "user", "content": question, "at": now},
           {"role": "assistant", "content": out["answer"], "at": now, "tools": out["tool_trace"],
            "citations": list(known), "unverified_citations": [c for c in cited if c not in known]}]
    if sess:
        research_sessions_collection.update_one({"_id": sess["_id"]}, {"$push": {"messages": {"$each": new}}, "$set": {"updated_at": now}})
        sid = sess["_id"]
    else:
        sid = research_sessions_collection.insert_one({"owner_email": email, "title": question[:80], "messages": new,
                                                       "created_at": now, "updated_at": now}).inserted_id
    return jsonify(clean({"session_id": sid, "answer": out["answer"], "evidence": known,
                          "unverified_citations": [c for c in cited if c not in known],
                          "tools_used": out["tool_trace"], "cost_usd": out["cost_usd"]}))


@research_bp.route("/research/sessions", methods=["GET", "OPTIONS"])
@require_auth
def sessions():
    rows = list(research_sessions_collection.find({"owner_email": request.current_user.get("email")},
                                                  {"title": 1, "updated_at": 1}).sort("updated_at", -1).limit(30))
    return jsonify(clean({"sessions": rows}))


@research_bp.route("/research/sessions/<sid>", methods=["GET", "OPTIONS"])
@require_auth
def session_detail(sid):
    s = _session(sid, request.current_user.get("email"))
    if not s:
        return jsonify({"status": "error", "message": "Session not found"}), 404
    return jsonify(clean(s))


# ---------------------------------------------------------------- overview dashboard

@research_bp.route("/overview", methods=["GET"])
def overview():
    companies = list(companies_collection.find({"kpis": {"$exists": True}}, {"name": 1, "slug": 1, "kpis": 1, "rating": 1,
                                                                            "emissions_trend": 1, "last_researched_at": 1}))
    def kpi(c, key):
        return next((x for x in c.get("kpis") or [] if x and x["key"] == key), None) or {}
    company_rows = [{
        "name": c["name"], "slug": c["slug"], "grade": (c.get("rating") or {}).get("grade"),
        "total_emissions": kpi(c, "total_emissions").get("current"), "total_period": kpi(c, "total_emissions").get("period"),
        "total_change_pct": kpi(c, "total_emissions").get("change_pct"),
        "renewable_pct": kpi(c, "renewable_pct").get("current"), "intensity": kpi(c, "emissions_intensity").get("current"),
        "intensity_unit": kpi(c, "emissions_intensity").get("unit"), "target_progress": kpi(c, "net_zero_progress").get("current"),
        "trend": c.get("emissions_trend") or [],
    } for c in companies]

    meta = offsetsdb.meta()
    reg = {}
    if meta:
        reg = {
            "by_registry": [{"registry": r["_id"], "projects": r["n"], "issued": r["issued"]} for r in registry_projects_collection.aggregate([
                {"$group": {"_id": "$registry", "n": {"$sum": 1}, "issued": {"$sum": "$issued"}}}, {"$sort": {"n": -1}}])],
            "by_category": [{"category": r["_id"], "projects": r["n"], "issued": r["issued"]} for r in registry_projects_collection.aggregate([
                {"$group": {"_id": "$category", "n": {"$sum": 1}, "issued": {"$sum": "$issued"}}}, {"$sort": {"issued": -1}}])],
            "rating_distribution": [{"grade": r["_id"], "count": r["n"]} for r in registry_projects_collection.aggregate([
                {"$match": {"latest_rating.grade": {"$ne": None}}}, {"$group": {"_id": "$latest_rating.grade", "n": {"$sum": 1}}}])],
            "total_projects": registry_projects_collection.estimated_document_count(),
            "total_issued": next(registry_projects_collection.aggregate([{"$group": {"_id": None, "s": {"$sum": "$issued"}}}]), {}).get("s", 0),
            "snapshot": meta.get("generated_at"), "citation": meta.get("citation"),
        }
    recent_ratings = list(project_ratings_collection.find({}, {"project_id": 1, "project_name": 1, "grade": 1, "overall_score": 1,
                                                              "confidence": 1, "provisional": 1, "anomalies": 1, "created_at": 1})
                          .sort("created_at", -1).limit(8))
    alerts = []
    for r in recent_ratings:
        for a in r.get("anomalies") or []:
            if a["severity"] in ("high", "medium"):
                alerts.append({"type": "project_anomaly", "project_id": r["project_id"], "project_name": r.get("project_name"),
                               "severity": a["severity"], "text": a["text"], "at": r["created_at"]})
    new_docs = list(company_documents_collection.find({"document_type": {"$in": ["brsr", "annual_report"]}},
                                                      {"company_id": 1, "title": 1, "source_url": 1, "publication_date": 1, "retrieved_at": 1})
                    .sort("retrieved_at", -1).limit(8))
    spend = next(agent_runs_collection.aggregate([{"$group": {"_id": None, "usd": {"$sum": "$cost_usd"}, "n": {"$sum": 1},
                                                              "hits": {"$sum": {"$cond": ["$cache_hit", 1, 0]}}}}]), {})
    return jsonify(clean({
        "counts": {
            "companies_tracked": companies_collection.count_documents({}),
            "companies_with_kpis": len(companies),
            "carbon_data_points": company_metrics_collection.estimated_document_count(),
            "projects_tracked": reg.get("total_projects", 0),
            "projects_rated": registry_projects_collection.count_documents({"latest_rating": {"$exists": True}}),
            "evidence_items": evidence_collection.estimated_document_count(),
        },
        "companies": company_rows, "registry": reg, "recent_ratings": recent_ratings,
        "alerts": alerts[:10], "new_disclosures": new_docs,
        "running_jobs": list(jobs_collection.find({"status": "running"}, {"kind": 1, "subject_id": 1, "created_at": 1}).limit(10)),
        "ai_usage": {"runs": spend.get("n", 0), "cost_usd": round(spend.get("usd", 0), 4), "cache_hits": spend.get("hits", 0)},
    }))
