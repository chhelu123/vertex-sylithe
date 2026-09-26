import logging
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request

from db import (
    users_collection,
    access_requests_collection,
    projects_collection,
    free_scans_collection,
    newsletter_collection,
    developer_projects_collection,
)
from utils.auth import require_auth, require_admin

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

# Free-tier limits (mirror routes/reports.py) for the admin usage view.
from config import UNLIMITED_EMAILS as _UNLIMITED
_FREE_LIMIT = 3
_USAGE_ACTIONS = ["aoi_import", "land_assess", "land_history"]


def _usage_for_emails(emails):
    """Return {email: {action: {used, remaining, limit}}} for the given emails,
    including LULC report exports. Unlimited accounts report remaining=None."""
    from db import feature_usage_collection, lulc_reports_collection
    emails = [e for e in emails if e]
    counts = {}
    if emails:
        for row in feature_usage_collection.aggregate([
            {"$match": {"email": {"$in": emails}}},
            {"$group": {"_id": {"email": "$email", "action": "$action"}, "n": {"$sum": 1}}},
        ]):
            counts.setdefault(row["_id"]["email"], {})[row["_id"]["action"]] = row["n"]
        for row in lulc_reports_collection.aggregate([
            {"$match": {"email": {"$in": emails}}},
            {"$group": {"_id": "$email", "n": {"$sum": 1}}},
        ]):
            counts.setdefault(row["_id"], {})["lulc_report"] = row["n"]
    out = {}
    for email in emails:
        unlimited = email.lower() in _UNLIMITED
        actions = {}
        for a in _USAGE_ACTIONS + ["lulc_report"]:
            used = counts.get(email, {}).get(a, 0)
            actions[a] = {
                "used": used,
                "limit": None if unlimited else _FREE_LIMIT,
                "remaining": None if unlimited else max(0, _FREE_LIMIT - used),
            }
        out[email] = {"unlimited": unlimited, "actions": actions}
    return out


def _serialize(doc):
    """Make a MongoDB doc JSON-safe."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    # Normalize legacy camelCase field to snake_case
    if "createdAt" in doc and "created_at" not in doc:
        doc["created_at"] = doc.pop("createdAt")
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


# ── Public: submit access request (any logged-in user) ───────────────────────

@admin_bp.route("/request-access", methods=["POST", "OPTIONS"])
@require_auth
def request_access():
    email = request.current_user.get("email", "").lower()
    user  = users_collection.find_one(
        {"email": email},
        {"fullName": 1, "tier": 1, "primaryActivity": 1, "phone": 1, "phoneNumber": 1,
         "mobile": 1, "company": 1, "organization": 1, "organisation": 1},
    )
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    body = request.get_json(silent=True) or {}
    plan = (body.get("plan") or "").strip()[:60]
    phone = user.get("phone") or user.get("phoneNumber") or user.get("mobile") or ""
    company = user.get("company") or user.get("organization") or user.get("organisation") or ""

    # Prevent duplicate pending requests — update the requested plan if changed
    existing = access_requests_collection.find_one({"user_email": email, "status": "pending"})
    if existing:
        if plan and existing.get("plan") != plan:
            access_requests_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"plan": plan, "updated_at": datetime.now(timezone.utc)}},
            )
        return jsonify({"status": "success", "message": "Request already pending"}), 200

    doc = {
        "user_email":      email,
        "user_name":       user.get("fullName", ""),
        "user_tier":       user.get("tier", "free"),
        "activity":        user.get("primaryActivity", ""),
        "user_phone":      phone,
        "user_company":    company,
        "plan":            plan,
        "status":          "pending",
        "admin_notes":     "",
        "requested_at":    datetime.now(timezone.utc),
        "updated_at":      datetime.now(timezone.utc),
    }
    access_requests_collection.insert_one(doc)
    logger.info(f"Access request from {email} (plan: {plan or 'n/a'})")
    return jsonify({"status": "success"}), 201


# ── Admin: overview stats ─────────────────────────────────────────────────────

@admin_bp.route("/admin/stats", methods=["GET", "OPTIONS"])
@require_admin
def admin_stats():
    total_users      = users_collection.count_documents({})
    free_users       = users_collection.count_documents({"tier": "free"})
    pro_users        = users_collection.count_documents({"tier": "pro"})
    total_requests   = access_requests_collection.count_documents({})
    pending_requests = access_requests_collection.count_documents({"status": "pending"})
    contacted        = access_requests_collection.count_documents({"status": "contacted"})
    approved         = access_requests_collection.count_documents({"status": "approved"})
    total_projects   = projects_collection.count_documents({})
    total_scans      = free_scans_collection.count_documents({})
    newsletter_subs  = newsletter_collection.count_documents({})

    # Recent signups (last 5)
    recent_users = list(
        users_collection.find({}, {"fullName": 1, "email": 1, "tier": 1, "created_at": 1})
        .sort("created_at", -1).limit(5)
    )

    # Recent requests (last 5)
    recent_requests = list(
        access_requests_collection.find({})
        .sort("requested_at", -1).limit(5)
    )

    return jsonify({
        "status": "success",
        "stats": {
            "total_users":      total_users,
            "free_users":       free_users,
            "pro_users":        pro_users,
            "total_requests":   total_requests,
            "pending_requests": pending_requests,
            "contacted":        contacted,
            "approved":         approved,
            "total_projects":   total_projects,
            "total_scans":      total_scans,
            "newsletter_subs":  newsletter_subs,
        },
        "recent_users":    [_serialize(u) for u in recent_users],
        "recent_requests": [_serialize(r) for r in recent_requests],
    }), 200


# ── Admin: developer projects (submitted via the Add Project form) ────────────

@admin_bp.route("/admin/projects", methods=["GET", "OPTIONS"])
@require_admin
def admin_projects():
    """All projects submitted by developers. Boundary geojson is replaced with a
    lightweight flag/count; use the detail endpoint to fetch the full boundary."""
    search = request.args.get("search", "").strip()
    query = {}
    if search:
        query = {"$or": [
            {"name":            {"$regex": search, "$options": "i"}},
            {"developer_email": {"$regex": search, "$options": "i"}},
            {"country":         {"$regex": search, "$options": "i"}},
        ]}

    docs = list(developer_projects_collection.find(query).sort("created_at", -1).limit(500))
    out = []
    for d in docs:
        gj = d.get("geojson")
        feats = 0
        if isinstance(gj, dict):
            if gj.get("type") == "FeatureCollection":
                feats = len(gj.get("features") or [])
            elif gj.get("type") in ("Feature", "Polygon", "MultiPolygon"):
                feats = 1
        d.pop("geojson", None)
        row = _serialize(d)
        row["has_boundary"] = bool(gj)
        row["boundary_features"] = feats
        out.append(row)

    return jsonify({"status": "success", "total": len(out), "projects": out}), 200


@admin_bp.route("/admin/projects/<project_id>", methods=["GET", "OPTIONS"])
@require_admin
def admin_project_detail(project_id):
    """Full project including the uploaded boundary geojson (KML source)."""
    try:
        doc = developer_projects_collection.find_one({"_id": ObjectId(project_id)})
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400
    if not doc:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    return jsonify({"status": "success", "project": _serialize(doc)}), 200


# ── Admin: users ──────────────────────────────────────────────────────────────

@admin_bp.route("/admin/users", methods=["GET", "OPTIONS"])
@require_admin
def admin_users():
    search = request.args.get("search", "").strip()
    page   = max(int(request.args.get("page", 1)), 1)
    limit  = min(int(request.args.get("limit", 50)), 100)
    skip   = (page - 1) * limit

    query = {}
    if search:
        query = {"$or": [
            {"email":    {"$regex": search, "$options": "i"}},
            {"fullName": {"$regex": search, "$options": "i"}},
        ]}

    total = users_collection.count_documents(query)
    users = list(
        users_collection.find(query, {"password": 0, "otp": 0})
        .sort("created_at", -1).skip(skip).limit(limit)
    )
    usage = _usage_for_emails([u.get("email") for u in users])
    serialized = []
    for u in users:
        d = _serialize(u)
        d["usage"] = usage.get(u.get("email"))
        serialized.append(d)

    return jsonify({
        "status": "success",
        "total":  total,
        "page":   page,
        "users":  serialized,
    }), 200


@admin_bp.route("/admin/users/<user_id>", methods=["GET", "OPTIONS"])
@require_admin
def admin_user_detail(user_id):
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)}, {"password": 0, "otp": 0})
    except Exception:
        return jsonify({"status": "error", "message": "Invalid ID"}), 400
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    requests = list(
        access_requests_collection.find({"user_email": user["email"]})
        .sort("requested_at", -1)
    )
    scans = list(
        free_scans_collection.find({"$or": [{"email": user["email"]}, {"user_email": user["email"]}]})
        .sort("created_at", -1).limit(20)
    )
    return jsonify({
        "status":          "success",
        "user":            _serialize(user),
        "usage":           _usage_for_emails([user["email"]]).get(user["email"]),
        "access_requests": [_serialize(r) for r in requests],
        "scans":           [_serialize(s) for s in scans],
    }), 200


@admin_bp.route("/admin/users/<user_id>", methods=["PATCH", "OPTIONS"])
@require_admin
def admin_update_user(user_id):
    data = request.get_json() or {}
    allowed = {k: v for k, v in data.items() if k in ("tier", "primaryActivity")}
    if not allowed:
        return jsonify({"status": "error", "message": "Nothing to update"}), 400

    result = users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": allowed}
    )
    if result.matched_count == 0:
        return jsonify({"status": "error", "message": "User not found"}), 404

    return jsonify({"status": "success"}), 200


# ── Admin: access requests ────────────────────────────────────────────────────

@admin_bp.route("/admin/access-requests", methods=["GET", "OPTIONS"])
@require_admin
def admin_access_requests():
    status = request.args.get("status", "")
    page   = max(int(request.args.get("page", 1)), 1)
    limit  = min(int(request.args.get("limit", 50)), 100)
    skip   = (page - 1) * limit

    query = {}
    if status:
        query["status"] = status

    total    = access_requests_collection.count_documents(query)
    requests = list(
        access_requests_collection.find(query)
        .sort("requested_at", -1).skip(skip).limit(limit)
    )

    return jsonify({
        "status":   "success",
        "total":    total,
        "page":     page,
        "requests": [_serialize(r) for r in requests],
    }), 200


@admin_bp.route("/admin/access-requests/<req_id>", methods=["PATCH", "OPTIONS"])
@require_admin
def admin_update_request(req_id):
    data   = request.get_json() or {}
    update = {"updated_at": datetime.now(timezone.utc)}

    if "status" in data:
        if data["status"] not in ("pending", "contacted", "approved", "rejected"):
            return jsonify({"status": "error", "message": "Invalid status"}), 400
        update["status"] = data["status"]

    if "admin_notes" in data:
        update["admin_notes"] = data["admin_notes"]

    result = access_requests_collection.update_one(
        {"_id": ObjectId(req_id)},
        {"$set": update}
    )
    if result.matched_count == 0:
        return jsonify({"status": "error", "message": "Request not found"}), 404

    # If approved, upgrade user tier
    if data.get("status") == "approved":
        req_doc = access_requests_collection.find_one({"_id": ObjectId(req_id)})
        if req_doc:
            users_collection.update_one(
                {"email": req_doc["user_email"]},
                {"$set": {"tier": "pro"}}
            )

    return jsonify({"status": "success"}), 200


# ── Admin: free scans ─────────────────────────────────────────────────────────

@admin_bp.route("/admin/scans", methods=["GET", "OPTIONS"])
@require_admin
def admin_scans():
    page  = max(int(request.args.get("page", 1)), 1)
    limit = min(int(request.args.get("limit", 50)), 100)
    skip  = (page - 1) * limit

    total = free_scans_collection.count_documents({})
    scans = list(
        free_scans_collection.find({})
        .sort("created_at", -1).skip(skip).limit(limit)
    )

    return jsonify({
        "status": "success",
        "total":  total,
        "page":   page,
        "scans":  [_serialize(s) for s in scans],
    }), 200


# ── Admin: newsletter subscribers ─────────────────────────────────────────────

@admin_bp.route("/admin/newsletter", methods=["GET", "OPTIONS"])
@require_admin
def admin_newsletter():
    page  = max(int(request.args.get("page", 1)), 1)
    limit = min(int(request.args.get("limit", 50)), 100)
    skip  = (page - 1) * limit

    total = newsletter_collection.count_documents({})
    subs  = list(
        newsletter_collection.find({})
        .sort("created_at", -1).skip(skip).limit(limit)
    )

    return jsonify({
        "status":      "success",
        "total":       total,
        "page":        page,
        "subscribers": [_serialize(s) for s in subs],
    }), 200
