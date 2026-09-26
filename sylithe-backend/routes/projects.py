import logging
import time

from flask import Blueprint, jsonify, request

from db import projects_collection
from services.registry import ensure_projects_cached, fetch_and_cache_all

logger = logging.getLogger(__name__)
projects_bp = Blueprint("projects", __name__)

# In-memory cache for filter values (refreshed every 10 minutes)
_filters_cache = {"data": None, "ts": 0}
_FILTERS_TTL = 600  # seconds

def _get_filters():
    now = time.time()
    if _filters_cache["data"] and now - _filters_cache["ts"] < _FILTERS_TTL:
        return _filters_cache["data"]
    filters = {
        "registries": projects_collection.distinct("registry", {"country": "India"}),
        "types":      sorted(set(projects_collection.distinct("type", {"country": "India"}))),
        "states":     sorted([s for s in projects_collection.distinct("state", {"country": "India"}) if s]),
    }
    _filters_cache["data"] = filters
    _filters_cache["ts"] = now
    return filters

SORT_MAP = {
    "credits_issued":    [("credits_issued", -1)],
    "credits_available": [("credits_available", -1)],
    "name":              [("name", 1)],
    "start_year":        [("start_year", -1)],
    "area":              [("area_ha", -1)],
}


@projects_bp.route("/projects", methods=["GET"])
def get_projects():
    try:
        ensure_projects_cached()

        registry     = request.args.get("registry", "all")
        project_type = request.args.get("type", "all")
        state        = request.args.get("state", "all")
        status_f     = request.args.get("status", "all")
        search       = request.args.get("search", "").strip()
        sort_by      = request.args.get("sort", "credits_issued")
        page         = max(int(request.args.get("page", 1)), 1)
        per_page     = min(int(request.args.get("per_page", 20)), 100)

        query = {"country": "India"}
        if registry != "all":
            query["registry"] = registry
        if project_type != "all":
            query["type"] = {"$regex": project_type, "$options": "i"}
        if state != "all":
            query["state"] = {"$regex": state, "$options": "i"}
        if status_f != "all":
            query["status"] = {"$regex": status_f, "$options": "i"}
        if search:
            query["$or"] = [
                {"name":      {"$regex": search, "$options": "i"}},
                {"id":        {"$regex": search, "$options": "i"}},
                {"developer": {"$regex": search, "$options": "i"}},
                {"state":     {"$regex": search, "$options": "i"}},
            ]

        sort_order = SORT_MAP.get(sort_by, [("credits_issued", -1)])
        total      = projects_collection.count_documents(query)
        skip       = (page - 1) * per_page

        raw = list(
            projects_collection.find(query, {"_id": 0, "cached_at": 0})
            .sort(sort_order)
            .skip(skip)
            .limit(per_page)
        )

        return jsonify({
            "status":      "success",
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": -(-total // per_page),
            "projects":    raw,
            "filters":     _get_filters(),
        }), 200

    except Exception as e:
        logger.error(f"Projects list error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@projects_bp.route("/projects/refresh", methods=["POST"])
def refresh_projects():
    try:
        count = fetch_and_cache_all()
        return jsonify({"status": "success", "message": f"Refreshed {count} projects"}), 200
    except Exception as e:
        logger.error(f"Projects refresh error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@projects_bp.route("/projects/<project_id>", methods=["GET"])
def get_project_detail(project_id):
    try:
        project = projects_collection.find_one({"id": project_id}, {"_id": 0, "cached_at": 0})
        if not project:
            return jsonify({"status": "error", "message": "Project not found"}), 404
        return jsonify({"status": "success", "project": project}), 200
    except Exception as e:
        logger.error(f"Project detail error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
