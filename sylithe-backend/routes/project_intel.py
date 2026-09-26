"""Module 2 API — carbon project intelligence & explainable ratings (under /api/intel)."""
import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from db import (
    registry_projects_collection, project_ratings_collection, project_documents_collection, rating_reviews_collection,
)
from services import documents as D
from services import offsetsdb
from services.ai import ai_configured
from services.jobs import start_job, active_job, get_job
from services.project_rating import rate_project, apply_reviews, DIMENSIONS, METHODOLOGY_VERSION, DISCLAIMER, GRADES
from utils.auth import require_auth, require_admin
from utils.serialize import clean

logger = logging.getLogger(__name__)
intel_bp = Blueprint("intel", __name__)

_LIST_FIELDS = {"project_id": 1, "name": 1, "registry": 1, "registry_name": 1, "country": 1, "category": 1,
                "project_type": 1, "protocol": 1, "proponent": 1, "status": 1, "issued": 1, "retired": 1,
                "retirement_ratio": 1, "first_issuance_at": 1, "last_issuance_at": 1, "latest_rating": 1}
_SORTS = {"issued": [("issued", -1)], "retired": [("retired", -1)], "name": [("name", 1)],
          "recent": [("last_issuance_at", -1)], "rating": [("latest_rating.score", -1)]}


def _ensure_registry():
    if not offsetsdb.meta():
        raise RuntimeError("Registry data not loaded yet — an admin must run POST /api/intel/registry/refresh")


@intel_bp.route("/intel/registry/meta", methods=["GET"])
def registry_meta():
    m = offsetsdb.meta()
    return jsonify(clean({"loaded": bool(m), **(m or {})}))


@intel_bp.route("/intel/registry/refresh", methods=["POST", "OPTIONS"])
@require_admin
def registry_refresh():
    def run(job):
        return offsetsdb.ingest(lambda k, label: job.step(k, label, "done"))
    job_id = start_job("registry_ingest", "registry", "offsetsdb", run, requested_by=request.current_user.get("email"))
    return jsonify({"status": "ok", "job_id": job_id})


@intel_bp.route("/intel/projects", methods=["GET"])
def list_projects():
    try:
        _ensure_registry()
    except RuntimeError as e:
        return jsonify({"status": "error", "message": str(e), "projects": [], "total": 0}), 200
    a = request.args
    query = {}
    if a.get("q"):
        rx = {"$regex": re.escape(a["q"].strip()), "$options": "i"}
        query["$or"] = [{"name": rx}, {"project_id": rx}, {"proponent": rx}]
    for field in ("country", "category", "registry", "status"):
        if a.get(field) and a[field] != "all":
            query[field] = a[field]
    if a.get("protocol"):
        query["protocol"] = a["protocol"].lower()
    if a.get("rated") == "1":
        query["latest_rating"] = {"$exists": True}
    if a.get("min_issued"):
        query["issued"] = {"$gte": float(a["min_issued"])}
    page = max(int(a.get("page", 1)), 1)
    per = min(int(a.get("per_page", 25)), 100)
    total = registry_projects_collection.count_documents(query)
    rows = list(registry_projects_collection.find(query, _LIST_FIELDS)
                .sort(_SORTS.get(a.get("sort", "issued"), _SORTS["issued"])).skip((page - 1) * per).limit(per))
    return jsonify(clean({"projects": rows, "total": total, "page": page, "per_page": per}))


@intel_bp.route("/intel/projects/facets", methods=["GET"])
def facets():
    country = request.args.get("country")
    match = {"country": country} if country and country != "all" else {}

    def group(field):
        return [{"value": r["_id"], "count": r["n"], "issued": r["issued"]} for r in registry_projects_collection.aggregate([
            {"$match": match}, {"$group": {"_id": f"${field}", "n": {"$sum": 1}, "issued": {"$sum": "$issued"}}},
            {"$sort": {"n": -1}}, {"$limit": 60}]) if r["_id"]]
    return jsonify(clean({
        "registries": group("registry"), "categories": group("category"), "statuses": group("status"),
        "countries": [{"value": r["_id"], "count": r["n"]} for r in registry_projects_collection.aggregate([
            {"$group": {"_id": "$country", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 80}]) if r["_id"]],
        "rating_distribution": [{"grade": r["_id"], "count": r["n"]} for r in registry_projects_collection.aggregate([
            {"$match": {**match, "latest_rating.grade": {"$ne": None}}},
            {"$group": {"_id": "$latest_rating.grade", "n": {"$sum": 1}}}])],
    }))


def _latest_rating(pid):
    r = project_ratings_collection.find_one({"project_id": pid}, sort=[("created_at", -1)])
    return apply_reviews(r) if r else None


@intel_bp.route("/intel/projects/<pid>", methods=["GET"])
def get_project(pid):
    p = registry_projects_collection.find_one({"_id": pid})
    if not p:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    p["rating"] = _latest_rating(pid)
    p["documents"] = list(project_documents_collection.find({"project_id": pid}).sort("added_at", -1))
    p["developer"] = offsetsdb.developer_portfolio(p.get("proponent"))
    job = active_job("project", pid, "project_rating")
    p["active_job"] = job
    p["disclaimer"] = DISCLAIMER
    return jsonify(clean(p))


@intel_bp.route("/intel/projects/<pid>/rate", methods=["POST", "OPTIONS"])
@require_auth
def rate(pid):
    if not registry_projects_collection.find_one({"_id": pid}, {"_id": 1}):
        return jsonify({"status": "error", "message": "Project not found"}), 404
    if not ai_configured():
        return jsonify({"status": "error", "message": "AI is not configured on the server (DEEPSEEK_API_KEY)."}), 503
    email = request.current_user.get("email")
    job_id = start_job("project_rating", "project", pid, rate_project, pid, email, requested_by=email)
    return jsonify({"status": "ok", "job_id": job_id})


@intel_bp.route("/intel/projects/<pid>/ratings", methods=["GET"])
def rating_history(pid):
    rows = list(project_ratings_collection.find({"project_id": pid},
                                                {"dimensions": 0}).sort("created_at", -1).limit(50))
    return jsonify(clean({"ratings": rows}))


@intel_bp.route("/intel/projects/<pid>/documents", methods=["POST", "OPTIONS"])
@require_auth
def link_document(pid):
    """Link a *public* project document URL (PDD, monitoring or verification report). No file upload."""
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not re.match(r"^https://", url):
        return jsonify({"status": "error", "message": "A public https:// PDF link is required"}), 400
    if not registry_projects_collection.find_one({"_id": pid}, {"_id": 1}):
        return jsonify({"status": "error", "message": "Project not found"}), 404
    try:
        raw = D.download_pdf(url)
        pages = D.parse_pdf(raw)
    except D.DocumentError as e:
        return jsonify({"status": "error", "message": f"Could not read that PDF: {e}"}), 422
    doc = {
        "project_id": pid, "source_url": url, "title": (body.get("title") or url.rsplit("/", 1)[-1])[:200],
        "document_type": body.get("document_type") or "other", "document_hash": D.sha256(raw),
        "page_count": len(pages), "status": "parsed", "added_by": request.current_user.get("email"),
        "added_at": datetime.now(timezone.utc),
    }
    project_documents_collection.update_one({"project_id": pid, "source_url": url}, {"$set": doc}, upsert=True)
    return jsonify(clean({"status": "ok", "document": doc}))


@intel_bp.route("/intel/compare", methods=["GET"])
def compare():
    ids = [i.strip() for i in request.args.get("ids", "").split(",") if i.strip()][:5]
    out = []
    for pid in ids:
        p = registry_projects_collection.find_one({"_id": pid}, _LIST_FIELDS)
        if not p:
            continue
        r = _latest_rating(pid)
        p["rating"] = {k: r.get(k) for k in ("grade", "overall_score", "confidence", "provisional", "created_at",
                                             "methodology_version", "dimensions", "anomalies")} if r else None
        out.append(p)
    dims = [{"key": k, "label": v[0]} for k, v in DIMENSIONS.items()] + [{"key": "data_quality", "label": "Data quality"}]
    return jsonify(clean({"projects": out, "dimensions": dims, "disclaimer": DISCLAIMER,
                          "language_note": "Comparisons describe relative evidence strength and documented risk on each dimension, not an overall 'best' project."}))


@intel_bp.route("/intel/ratings/<rating_id>/review", methods=["POST", "OPTIONS"])
@require_admin
def review(rating_id):
    """Analyst override / annotation (spec §54). The AI assessment is kept unchanged alongside."""
    body = request.get_json(silent=True) or {}
    try:
        rating = project_ratings_collection.find_one({"_id": ObjectId(rating_id)})
    except InvalidId:
        rating = None
    if not rating:
        return jsonify({"status": "error", "message": "Rating not found"}), 404
    dim = body.get("dimension")
    ai = next((d for d in rating["dimensions"] if d["key"] == dim), None)
    if not ai:
        return jsonify({"status": "error", "message": "Unknown dimension"}), 400
    if not (body.get("reason") or "").strip():
        return jsonify({"status": "error", "message": "A reason is required"}), 400
    rec = {
        "rating_id": rating_id, "project_id": rating["project_id"], "dimension": dim,
        "ai_assessment": {"score": ai.get("score"), "risk": ai.get("risk"), "reason": ai.get("reason")},
        "human_score": body.get("score"), "human_risk": body.get("risk"), "reason": body["reason"].strip(),
        "evidence": body.get("evidence") or [], "reviewer": request.current_user.get("email"),
        "created_at": datetime.now(timezone.utc),
    }
    rating_reviews_collection.insert_one(rec)
    return jsonify(clean({"status": "ok", "review": rec}))


@intel_bp.route("/intel/methodology", methods=["GET"])
def methodology():
    from services.methodology_kb import KB_VERSION, CATEGORY_PROFILES, METHODOLOGY_NOTES
    return jsonify({
        "version": METHODOLOGY_VERSION, "kb_version": KB_VERSION, "disclaimer": DISCLAIMER,
        "dimensions": [{"key": k, "label": v[0], "weight": v[1]} for k, v in DIMENSIONS.items()] + [{"key": "data_quality", "label": "Data quality", "weight": 5}],
        "grades": [{"min_score": t, "grade": g} for t, g in GRADES],
        "category_profiles": CATEGORY_PROFILES,
        "methodology_notes": {k: v for k, v in METHODOLOGY_NOTES.items()},
    })
