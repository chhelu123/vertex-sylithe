"""Module 1 API — company carbon intelligence, evidence and agent jobs."""
import logging
import re

from flask import Blueprint, jsonify, request

from db import (
    companies_collection, company_documents_collection, company_metrics_collection,
    company_ratings_collection, evidence_collection, jobs_collection,
)
from services import nse
from services.ai import ai_configured
from services.company_agents import run_company_research
from services.company_rating import rebuild_company_intelligence, METHODOLOGY_VERSION, DIMENSION_WEIGHTS, KPI_DEFS
from services.jobs import start_job, get_job, active_job
from utils.auth import require_auth, require_admin
from utils.serialize import clean

logger = logging.getLogger(__name__)
companies_bp = Blueprint("companies", __name__)

_LIST_FIELDS = {"slug": 1, "name": 1, "listing": 1, "industry": 1, "status": 1, "rating.grade": 1,
                "rating.overall_score": 1, "rating.confidence": 1, "rating.status": 1, "kpis": 1,
                "last_researched_at": 1, "emissions_trend": 1}


def _summary(c):
    k = {x["key"]: x for x in (c.get("kpis") or []) if x}
    pick = lambda key: {f: k[key].get(f) for f in ("current", "unit", "period", "change_pct", "confidence")} if key in k else None
    return {
        "slug": c["slug"], "name": c["name"], "symbol": (c.get("listing") or {}).get("nse_symbol"),
        "industry": c.get("industry"), "status": c.get("status"), "rating": c.get("rating"),
        "last_researched_at": c.get("last_researched_at"),
        "total_emissions": pick("total_emissions"), "renewable_pct": pick("renewable_pct"),
        "emissions_intensity": pick("emissions_intensity"), "emissions_trend": c.get("emissions_trend"),
    }


@companies_bp.route("/companies", methods=["GET"])
def list_companies():
    q = request.args.get("q", "").strip()
    query = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query = {"$or": [{"name": rx}, {"aliases": rx}, {"listing.nse_symbol": rx}, {"industry": rx}]}
    rows = [_summary(c) for c in companies_collection.find(query, _LIST_FIELDS).sort("name", 1).limit(200)]
    out = {"companies": rows, "total": len(rows)}
    if q and request.args.get("include_nse", "1") == "1":
        tracked = {r["symbol"] for r in rows}
        try:
            out["nse_matches"] = [dict(m, tracked=m["symbol"] in tracked) for m in nse.resolve(q)]
        except nse.NseError as e:
            out["nse_matches"] = []
            out["nse_error"] = str(e)
    return jsonify(clean(out))


@companies_bp.route("/companies/research", methods=["POST", "OPTIONS"])
@require_auth
def research_company():
    """Start the agent pipeline for an NSE symbol. Returns a job id to poll."""
    body = request.get_json(silent=True) or {}
    symbol = (body.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"status": "error", "message": "symbol is required"}), 400
    if not nse.get_equity(symbol):
        return jsonify({"status": "error", "message": f"{symbol} is not an NSE-listed equity"}), 404
    if not ai_configured():
        return jsonify({"status": "error", "message": "AI is not configured on the server (DEEPSEEK_API_KEY)."}), 503
    job_id = start_job("company_research", "company_symbol", symbol, run_company_research, symbol,
                       requested_by=request.current_user.get("email"))
    return jsonify({"status": "ok", "job_id": job_id})


@companies_bp.route("/companies/<slug>", methods=["GET"])
def get_company(slug):
    c = companies_collection.find_one({"_id": slug})
    if not c:
        return jsonify({"status": "error", "message": "Company not found"}), 404
    docs = list(company_documents_collection.find({"company_id": slug}, {"company_id": 0}).sort("reporting_period", -1))
    symbol = (c.get("listing") or {}).get("nse_symbol")
    job = active_job("company_symbol", symbol, "company_research") or jobs_collection.find_one(
        {"subject_type": "company_symbol", "subject_id": symbol}, sort=[("created_at", -1)])
    financial = list(company_metrics_collection.find(
        {"company_id": slug, "metric": {"$regex": "_inr_cr$"}}, {"_id": 0, "company_id": 0}).sort("period", -1))
    c["documents"] = docs
    c["financials"] = financial
    c["latest_job"] = job
    c["methodology"] = {"version": METHODOLOGY_VERSION, "weights": DIMENSION_WEIGHTS}
    return jsonify(clean(c))


@companies_bp.route("/companies/<slug>/metrics", methods=["GET"])
def company_metrics(slug):
    rows = list(company_metrics_collection.find({"company_id": slug}, {"_id": 0}).sort([("metric", 1), ("period", 1)]))
    return jsonify(clean({"metrics": rows}))


@companies_bp.route("/companies/<slug>/ratings", methods=["GET"])
def company_rating_history(slug):
    rows = list(company_ratings_collection.find({"company_id": slug}).sort("created_at", -1).limit(50))
    return jsonify(clean({"ratings": rows}))


@companies_bp.route("/companies/<slug>/recompute", methods=["POST", "OPTIONS"])
@require_admin
def recompute(slug):
    if not companies_collection.find_one({"_id": slug}):
        return jsonify({"status": "error", "message": "Company not found"}), 404
    return jsonify(clean(rebuild_company_intelligence(slug)))


@companies_bp.route("/kpi-definitions", methods=["GET"])
def kpi_definitions():
    return jsonify({"kpis": [{"key": k, "label": l, "metric": m, "unit": u, "better": d} for k, l, m, u, d in KPI_DEFS],
                    "methodology_version": METHODOLOGY_VERSION, "weights": DIMENSION_WEIGHTS})


@companies_bp.route("/evidence/<evidence_id>", methods=["GET"])
def evidence(evidence_id):
    e = evidence_collection.find_one({"evidence_id": evidence_id}, {"_id": 0})
    if not e:
        return jsonify({"status": "error", "message": "Evidence not found"}), 404
    return jsonify(clean(e))


@companies_bp.route("/jobs/<job_id>", methods=["GET"])
def job_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    return jsonify(clean(job))
