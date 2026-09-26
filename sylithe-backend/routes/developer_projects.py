import uuid
import logging
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request

from db import developer_projects_collection, dev_activity_collection
from utils.auth import require_auth

logger = logging.getLogger(__name__)
dev_projects_bp = Blueprint("dev_projects", __name__)


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


def _log_activity(email, project_id, project_name, action):
    try:
        dev_activity_collection.insert_one({
            "developer_email": email,
            "project_id": str(project_id),
            "project_name": project_name,
            "action": action,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception:
        pass


# ── GET /api/dev/projects ─────────────────────────────────────────────────────
def _round_coords(c, nd=4):
    if isinstance(c, list):
        if c and isinstance(c[0], (int, float)):
            return [round(float(x), nd) for x in c[:2]]
        return [_round_coords(x, nd) for x in c]
    return c


def _simplify_ring(coords, max_pts=120):
    """Decimate a flat list of [x,y] points to at most max_pts (keeps a thumbnail-sized outline)."""
    if not isinstance(coords, list) or len(coords) <= max_pts:
        return coords
    step = max(1, len(coords) // max_pts)
    out = coords[::step]
    if out[-1] != coords[-1]:
        out.append(coords[-1])
    return out


def _simplify_geometry(geom):
    if not isinstance(geom, dict):
        return geom
    t = geom.get("type")
    coords = geom.get("coordinates")
    try:
        if t == "Polygon":
            coords = [_simplify_ring(_round_coords(r)) for r in coords]
        elif t == "MultiPolygon":
            coords = [[_simplify_ring(_round_coords(r)) for r in poly] for poly in coords]
        else:
            coords = _round_coords(coords)
    except Exception:
        return geom
    return {"type": t, "coordinates": coords}


def _preview_geojson(gj):
    """Small, low-precision boundary used to draw the project thumbnail."""
    if not isinstance(gj, dict):
        return None, 0
    try:
        if gj.get("type") == "FeatureCollection":
            feats = gj.get("features", []) or []
            simplified = [{"type": "Feature", "properties": {},
                           "geometry": _simplify_geometry((f or {}).get("geometry") or {})}
                          for f in feats if (f or {}).get("geometry")]
            return {"type": "FeatureCollection", "features": simplified}, len(simplified)
        if gj.get("type") == "Feature":
            return {"type": "Feature", "properties": {}, "geometry": _simplify_geometry(gj.get("geometry") or {})}, 1
        return {"type": "Feature", "properties": {}, "geometry": _simplify_geometry(gj)}, 1
    except Exception:
        return None, 0


@dev_projects_bp.route("/dev/projects", methods=["GET", "OPTIONS"])
@require_auth
def list_projects():
    email = request.current_user["email"]
    docs = list(
        developer_projects_collection.find({"developer_email": email})
        .sort("created_at", -1)
    )
    # Replace the heavy full geojson with a small simplified preview + polygon count,
    # so cards can draw the boundary thumbnail without shipping MBs of geometry.
    for d in docs:
        preview, count = _preview_geojson(d.get("geojson"))
        d.pop("geojson", None)
        d["geojson"] = preview
        d["polygon_count"] = count
    # Compute stats in the same query result to avoid a second round-trip
    total_area    = sum(d.get("area_ha", 0) or 0 for d in docs)
    total_carbon  = sum(d.get("estimated_carbon", 0) or 0 for d in docs)
    verified      = sum(1 for d in docs if d.get("status") in ("verified", "credits_issued"))
    in_verif      = sum(1 for d in docs if d.get("status") == "under_verification")
    credits       = sum((d.get("carbon_credits") or {}).get("issued", 0) for d in docs)
    stats = {
        "total_projects": len(docs),
        "total_area_ha":  round(total_area, 2),
        "total_carbon":   round(total_carbon, 2),
        "verified_count": verified,
        "in_verification": in_verif,
        "credits_issued": round(credits, 2),
    }
    return jsonify({
        "status":   "success",
        "projects": [_serialize(d) for d in docs],
        "stats":    stats,
    }), 200


# ── POST /api/dev/projects ────────────────────────────────────────────────────
@dev_projects_bp.route("/dev/projects", methods=["POST", "OPTIONS"])
@require_auth
def create_project():
    email = request.current_user["email"]
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"status": "error", "message": "Project name is required"}), 400

    area_ha = data.get("area_ha")
    try:
        area_ha = float(area_ha) if area_ha is not None else 0.0
    except (ValueError, TypeError):
        area_ha = 0.0

    estimated_carbon = data.get("estimated_carbon")
    try:
        estimated_carbon = float(estimated_carbon) if estimated_carbon is not None else 0.0
    except (ValueError, TypeError):
        estimated_carbon = 0.0

    now = datetime.now(timezone.utc)
    doc = {
        "developer_email":    email,
        "name":               name,
        "type":               data.get("type", ""),
        "country":            data.get("country", ""),
        "state":              data.get("state", ""),
        "district":           data.get("district", ""),
        "crediting_standard": data.get("crediting_standard", ""),
        "methodology":        data.get("methodology", ""),
        "start_date":         data.get("start_date", ""),
        "credit_start":       data.get("credit_start", ""),
        "end_date":           data.get("end_date", ""),
        "project_length":     data.get("project_length", ""),
        "land_tenure":        data.get("land_tenure", ""),
        "community_benefit":  bool(data.get("community_benefit", False)),
        "biodiversity_impact": data.get("biodiversity_impact", ""),
        "baseline_scenario":  data.get("baseline_scenario", ""),
        "monitoring_plan":    data.get("monitoring_plan", ""),
        "leakage_risk":       data.get("leakage_risk", ""),
        "ccp_eligible":       data.get("ccp_eligible", ""),
        "proponent":          data.get("proponent", ""),
        "proponent_contact":  data.get("proponent_contact", ""),
        "description":        data.get("description", ""),
        "area_ha":            area_ha,
        "estimated_carbon":   estimated_carbon,
        "geojson":            data.get("geojson", None),
        "status":             "onboarded",
        "verification_steps": {
            "boundary_uploaded":  bool(data.get("geojson")),
            "lulc_classified":    False,
            "chm_run":            False,
            "baseline_set":       False,
            "biomass_estimated":  False,
            "reports_generated":  False,
        },
        "carbon_credits": {"issued": 0.0, "pending": estimated_carbon, "retired": 0.0},
        "documents":  [],
        "milestones": [
            {"label": "Project Onboarded",    "date": now.strftime("%Y-%m-%d"), "done": True},
            {"label": "LULC Classification",  "date": "",  "done": False},
            {"label": "CHM Verification",     "date": "",  "done": False},
            {"label": "Baseline Established", "date": "",  "done": False},
            {"label": "Credits Projected",    "date": "",  "done": False},
        ],
        "created_at": now,
        "updated_at": now,
    }
    result = developer_projects_collection.insert_one(doc)
    _log_activity(email, result.inserted_id, name, "Project created")
    return jsonify({"status": "success", "id": str(result.inserted_id)}), 201


# ── GET /api/dev/projects/<id> ────────────────────────────────────────────────
@dev_projects_bp.route("/dev/projects/<project_id>", methods=["GET", "OPTIONS"])
@require_auth
def get_project(project_id):
    email = request.current_user["email"]
    try:
        doc = developer_projects_collection.find_one(
            {"_id": ObjectId(project_id), "developer_email": email}
        )
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400
    if not doc:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    return jsonify({"status": "success", "project": _serialize(doc)}), 200


# ── PATCH /api/dev/projects/<id> ──────────────────────────────────────────────
@dev_projects_bp.route("/dev/projects/<project_id>", methods=["PATCH", "OPTIONS"])
@require_auth
def update_project(project_id):
    email = request.current_user["email"]
    data  = request.get_json() or {}
    try:
        oid = ObjectId(project_id)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400

    doc = developer_projects_collection.find_one({"_id": oid, "developer_email": email})
    if not doc:
        return jsonify({"status": "error", "message": "Project not found"}), 404

    allowed_scalar = [
        "name", "type", "country", "state", "district", "crediting_standard",
        "methodology", "start_date", "credit_start", "end_date", "project_length",
        "land_tenure", "community_benefit", "biodiversity_impact",
        "baseline_scenario", "monitoring_plan", "leakage_risk", "ccp_eligible",
        "proponent", "proponent_contact", "description", "area_ha",
        "estimated_carbon", "geojson", "status", "milestones",
    ]
    update = {"updated_at": datetime.now(timezone.utc)}
    for k in allowed_scalar:
        if k in data:
            update[k] = data[k]

    if "verification_steps" in data and isinstance(data["verification_steps"], dict):
        existing = doc.get("verification_steps", {})
        existing.update(data["verification_steps"])
        update["verification_steps"] = existing
        done_count = sum(1 for v in existing.values() if v)
        if done_count >= 6:
            update["status"] = "verified"
        elif done_count >= 2:
            update["status"] = "under_verification"
        _log_activity(email, oid, doc["name"], "Verification step updated")

    if "carbon_credits" in data and isinstance(data["carbon_credits"], dict):
        existing = doc.get("carbon_credits", {})
        existing.update(data["carbon_credits"])
        update["carbon_credits"] = existing
        if existing.get("issued", 0) > 0:
            update["status"] = "credits_issued"
        _log_activity(email, oid, doc["name"], "Carbon credits updated")

    if "status" in data and data["status"] != doc.get("status"):
        _log_activity(email, oid, doc["name"], f"Status changed to {data['status']}")

    developer_projects_collection.update_one({"_id": oid}, {"$set": update})
    return jsonify({"status": "success"}), 200


# ── DELETE /api/dev/projects/<id> ─────────────────────────────────────────────
@dev_projects_bp.route("/dev/projects/<project_id>", methods=["DELETE", "OPTIONS"])
@require_auth
def delete_project(project_id):
    email = request.current_user["email"]
    try:
        oid = ObjectId(project_id)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400
    result = developer_projects_collection.delete_one({"_id": oid, "developer_email": email})
    if result.deleted_count == 0:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    _log_activity(email, oid, project_id, "Project deleted")
    return jsonify({"status": "success"}), 200


# ── GET /api/dev/stats ────────────────────────────────────────────────────────
@dev_projects_bp.route("/dev/stats", methods=["GET", "OPTIONS"])
@require_auth
def dev_stats():
    email = request.current_user["email"]
    docs = list(developer_projects_collection.find(
        {"developer_email": email},
        {"area_ha": 1, "estimated_carbon": 1, "status": 1, "carbon_credits": 1}
    ))
    total_projects  = len(docs)
    total_area      = sum(d.get("area_ha", 0) or 0 for d in docs)
    total_carbon    = sum(d.get("estimated_carbon", 0) or 0 for d in docs)
    verified_count  = sum(1 for d in docs if d.get("status") in ("verified", "credits_issued"))
    credits_issued  = sum((d.get("carbon_credits") or {}).get("issued", 0) for d in docs)
    return jsonify({
        "status": "success",
        "stats": {
            "total_projects":  total_projects,
            "total_area_ha":   round(total_area, 2),
            "total_carbon":    round(total_carbon, 2),
            "verified_count":  verified_count,
            "credits_issued":  round(credits_issued, 2),
        }
    }), 200


# ── GET /api/dev/activity ─────────────────────────────────────────────────────
@dev_projects_bp.route("/dev/activity", methods=["GET", "OPTIONS"])
@require_auth
def dev_activity():
    email = request.current_user["email"]
    docs  = list(
        dev_activity_collection.find({"developer_email": email})
        .sort("timestamp", -1).limit(30)
    )
    return jsonify({"status": "success", "activity": [_serialize(d) for d in docs]}), 200


# ── POST /api/dev/projects/<id>/documents ─────────────────────────────────────
@dev_projects_bp.route("/dev/projects/<project_id>/documents", methods=["POST", "OPTIONS"])
@require_auth
def add_document(project_id):
    email = request.current_user["email"]
    data  = request.get_json() or {}
    try:
        oid = ObjectId(project_id)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400

    doc = developer_projects_collection.find_one({"_id": oid, "developer_email": email}, {"name": 1})
    if not doc:
        return jsonify({"status": "error", "message": "Project not found"}), 404

    entry = {
        "doc_id":      str(uuid.uuid4()),
        "name":        data.get("name", "Untitled"),
        "file_type":   data.get("file_type", "Other"),
        "size_kb":     data.get("size_kb", 0),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    developer_projects_collection.update_one(
        {"_id": oid},
        {"$push": {"documents": entry}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    _log_activity(email, oid, doc["name"], f"Document uploaded: {entry['name']}")
    return jsonify({"status": "success", "doc_id": entry["doc_id"]}), 201


# ── DELETE /api/dev/projects/<id>/documents/<doc_id> ──────────────────────────
@dev_projects_bp.route("/dev/projects/<project_id>/documents/<doc_id>", methods=["DELETE", "OPTIONS"])
@require_auth
def delete_document(project_id, doc_id):
    email = request.current_user["email"]
    try:
        oid = ObjectId(project_id)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400
    developer_projects_collection.update_one(
        {"_id": oid, "developer_email": email},
        {"$pull": {"documents": {"doc_id": doc_id}}}
    )
    return jsonify({"status": "success"}), 200
