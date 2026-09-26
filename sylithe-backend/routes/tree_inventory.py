"""
Tree Inventory API — Field-level tree enumeration for carbon credit projects.

Each tree record is stored per project + plot (polygon index).
Fields follow VCS/Gold Standard MRV requirements for forest carbon projects.
"""
import logging
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request

from db import tree_inventory_collection, developer_projects_collection
from utils.auth import require_auth

logger = logging.getLogger(__name__)
tree_inv_bp = Blueprint("tree_inventory", __name__)


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


# ── GET /api/dev/tree-inventory/<project_id>/<plot_index> ─────────────────────
@tree_inv_bp.route("/dev/tree-inventory/<project_id>/<int:plot_index>", methods=["GET", "OPTIONS"])
@require_auth
def get_trees(project_id, plot_index):
    """Fetch all tree records for a specific project + plot."""
    email = request.current_user["email"]

    # Verify project ownership
    try:
        proj = developer_projects_collection.find_one(
            {"_id": ObjectId(project_id), "developer_email": email},
            {"name": 1}
        )
    except Exception:
        return jsonify({"status": "error", "message": "Invalid project ID"}), 400

    if not proj:
        return jsonify({"status": "error", "message": "Project not found"}), 404

    trees = list(
        tree_inventory_collection.find({
            "developer_email": email,
            "project_id": project_id,
            "plot_index": plot_index,
        }).sort("tree_id", 1)
    )
    return jsonify({
        "status": "success",
        "trees": [_serialize(t) for t in trees],
    }), 200


# ── POST /api/dev/tree-inventory/<project_id>/<plot_index> ────────────────────
@tree_inv_bp.route("/dev/tree-inventory/<project_id>/<int:plot_index>", methods=["POST", "OPTIONS"])
@require_auth
def add_tree(project_id, plot_index):
    """Add a new tree record. Auto-assigns incremental tree_id per plot."""
    email = request.current_user["email"]
    data = request.get_json() or {}

    # Verify project ownership
    try:
        proj = developer_projects_collection.find_one(
            {"_id": ObjectId(project_id), "developer_email": email},
            {"name": 1}
        )
    except Exception:
        return jsonify({"status": "error", "message": "Invalid project ID"}), 400

    if not proj:
        return jsonify({"status": "error", "message": "Project not found"}), 404

    # Auto-increment tree_id within this project+plot
    last_tree = tree_inventory_collection.find_one(
        {"developer_email": email, "project_id": project_id, "plot_index": plot_index},
        sort=[("tree_id", -1)]
    )
    next_id = (last_tree["tree_id"] + 1) if last_tree else 1

    # Parse numeric fields safely
    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None and val != "" else default
        except (ValueError, TypeError):
            return default

    now = datetime.now(timezone.utc)
    doc = {
        "developer_email": email,
        "project_id": project_id,
        "plot_index": plot_index,
        "tree_id": next_id,
        "latitude": safe_float(data.get("latitude"), None),
        "longitude": safe_float(data.get("longitude"), None),
        "species_common": (data.get("species_common") or "").strip(),
        "species_scientific": (data.get("species_scientific") or "").strip(),
        "height_m": safe_float(data.get("height_m")),
        "dbh_cm": safe_float(data.get("dbh_cm")),
        "crown_diameter_m": safe_float(data.get("crown_diameter_m")),
        "health_status": data.get("health_status", "healthy"),  # healthy | stressed | dead | damaged
        "age_class": data.get("age_class", "mature"),  # seedling | sapling | pole | mature | over-mature
        "notes": (data.get("notes") or "").strip(),
        "created_at": now,
        "updated_at": now,
    }

    result = tree_inventory_collection.insert_one(doc)
    return jsonify({
        "status": "success",
        "tree": _serialize({**doc, "_id": result.inserted_id}),
    }), 201


# ── PATCH /api/dev/tree-inventory/<tree_oid> ──────────────────────────────────
@tree_inv_bp.route("/dev/tree-inventory/<tree_oid>", methods=["PATCH", "OPTIONS"])
@require_auth
def update_tree(tree_oid):
    """Update an existing tree record."""
    email = request.current_user["email"]
    data = request.get_json() or {}

    try:
        oid = ObjectId(tree_oid)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid tree ID"}), 400

    doc = tree_inventory_collection.find_one({"_id": oid, "developer_email": email})
    if not doc:
        return jsonify({"status": "error", "message": "Tree record not found"}), 404

    allowed = [
        "latitude", "longitude", "species_common", "species_scientific",
        "height_m", "dbh_cm", "crown_diameter_m", "health_status", "age_class", "notes",
    ]
    update = {"updated_at": datetime.now(timezone.utc)}
    for k in allowed:
        if k in data:
            update[k] = data[k]

    tree_inventory_collection.update_one({"_id": oid}, {"$set": update})
    return jsonify({"status": "success"}), 200


# ── DELETE /api/dev/tree-inventory/<tree_oid> ─────────────────────────────────
@tree_inv_bp.route("/dev/tree-inventory/<tree_oid>", methods=["DELETE", "OPTIONS"])
@require_auth
def delete_tree(tree_oid):
    """Delete a tree record."""
    email = request.current_user["email"]

    try:
        oid = ObjectId(tree_oid)
    except Exception:
        return jsonify({"status": "error", "message": "Invalid tree ID"}), 400

    result = tree_inventory_collection.delete_one({"_id": oid, "developer_email": email})
    if result.deleted_count == 0:
        return jsonify({"status": "error", "message": "Tree record not found"}), 404
    return jsonify({"status": "success"}), 200


# ── GET /api/dev/tree-inventory/summary/<project_id> ──────────────────────────
@tree_inv_bp.route("/dev/tree-inventory/summary/<project_id>", methods=["GET", "OPTIONS"])
@require_auth
def tree_summary(project_id):
    """Get summary stats per plot for a project."""
    email = request.current_user["email"]

    pipeline = [
        {"$match": {"developer_email": email, "project_id": project_id}},
        {"$group": {
            "_id": "$plot_index",
            "tree_count": {"$sum": 1},
            "avg_height": {"$avg": "$height_m"},
            "avg_dbh": {"$avg": "$dbh_cm"},
            "species_list": {"$addToSet": "$species_common"},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = list(tree_inventory_collection.aggregate(pipeline))
    summary = {}
    for r in results:
        summary[r["_id"]] = {
            "tree_count": r["tree_count"],
            "avg_height": round(r["avg_height"] or 0, 1),
            "avg_dbh": round(r["avg_dbh"] or 0, 1),
            "species_count": len(r["species_list"]),
        }
    return jsonify({"status": "success", "summary": summary}), 200
