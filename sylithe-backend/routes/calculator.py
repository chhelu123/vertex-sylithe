"""
Company carbon calculator — the ONLY place in Sylithe where users upload files.

A company user uploads their own activity documents (electricity bills, fuel invoices, CSV
exports) → the Activity Extraction Agent pulls quantities with page-verified quotes → the user
reviews/edits lines → Scope 1/2 is calculated in code from cited emission factors.
Inventories are private to their owner.
"""
import csv
import io
import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request

from db import calc_inventories_collection, calc_uploads_collection
from services import documents as D
from services.ai import call_json, AgentError, ai_configured
from services.emission_factors import ACTIVITY_TYPES, FUELS, FACTORS_VERSION, calculate_line, FactorError, GRID_EF_T_PER_MWH, CEA_V21, IPCC_2006
from services.evidence import obj, arr, enum, nullable, STR, NUM, INT
from utils.auth import require_auth
from utils.serialize import clean

logger = logging.getLogger(__name__)
calculator_bp = Blueprint("calculator", __name__)

MAX_UPLOAD = 20 * 1024 * 1024

_EXTRACT_SCHEMA = obj({
    "lines": arr(obj({
        "activity_type": enum(*ACTIVITY_TYPES),
        "quantity": NUM, "unit": STR, "period": STR, "facility": nullable(STR),
        "description": STR, "page": INT, "quote": STR,
    })),
    "document_kind": STR,
    "data_gaps": arr(STR),
})
_EXTRACT_SYSTEM = """You are Sylithe's Activity Data Extraction Agent. You read a company's own utility bills,
fuel invoices or energy statements and extract consumption quantities for a GHG inventory.

activity_type: electricity_grid (purchased grid electricity), electricity_renewable (only if the document shows a
renewable contract / REC / green tariff), diesel, petrol, lpg, natural_gas, coal, fuel_oil, kerosene.
Rules: copy quantities and units exactly as printed (kWh, MWh, units, L, kL, kg, t, GJ, MMBtu). Do not convert.
Extract consumption, not amounts in rupees. One line per meter/fuel/billing period.
quote: short verbatim text from the page containing the quantity; page: the page element's number attribute."""


def _now():
    return datetime.now(timezone.utc)


def _oid(s):
    try:
        return ObjectId(s)
    except (InvalidId, TypeError):
        return None


def _owned(inv_id):
    oid = _oid(inv_id)
    if not oid:
        return None
    return calc_inventories_collection.find_one({"_id": oid, "owner_email": request.current_user.get("email")})


def _compute(inv):
    lines, totals, errors = [], {"Scope 1": 0.0, "Scope 2": 0.0}, []
    for ln in inv.get("lines", []):
        if ln.get("excluded"):
            lines.append({**ln, "result": None})
            continue
        try:
            r = calculate_line(ln["activity_type"], float(ln["quantity"]), ln["unit"])
            totals[r["scope"]] += r["tco2e"]
            lines.append({**ln, "result": r})
        except (FactorError, ValueError, TypeError) as e:
            errors.append({"line_id": ln["line_id"], "error": str(e)})
            lines.append({**ln, "result": None, "error": str(e)})
    by_activity = {}
    for ln in lines:
        if ln.get("result"):
            by_activity[ln["activity_type"]] = by_activity.get(ln["activity_type"], 0) + ln["result"]["tco2e"]
    return {
        "lines": lines, "errors": errors,
        "totals": {k: round(v, 3) for k, v in totals.items()} | {"Scope 1+2": round(sum(totals.values()), 3)},
        "by_activity": {k: round(v, 3) for k, v in by_activity.items()},
        "factors_version": FACTORS_VERSION, "label": "Estimated",
        "notes": ["Scope 1 uses CO2-only IPCC 2006 default factors; CH4/N2O excluded.",
                  f"Scope 2 location-based uses CEA V21.0 grid factor {GRID_EF_T_PER_MWH} tCO2/MWh (FY2024-25).",
                  "Lines extracted by AI must be reviewed before the inventory is used for reporting."],
    }


@calculator_bp.route("/calculator/factors", methods=["GET"])
def factors():
    return jsonify({"version": FACTORS_VERSION, "activity_types": ACTIVITY_TYPES,
                    "fuels": FUELS, "grid_ef_t_per_mwh": GRID_EF_T_PER_MWH, "sources": [CEA_V21, IPCC_2006]})


@calculator_bp.route("/calculator/inventories", methods=["GET", "POST", "OPTIONS"])
@require_auth
def inventories():
    email = request.current_user.get("email")
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        doc = {"owner_email": email, "name": (body.get("name") or "My inventory")[:120],
               "company": (body.get("company") or "")[:160], "period": (body.get("period") or "")[:40],
               "lines": [], "created_at": _now(), "updated_at": _now()}
        res = calc_inventories_collection.insert_one(doc)
        doc["_id"] = res.inserted_id
        return jsonify(clean(doc))
    rows = list(calc_inventories_collection.find({"owner_email": email}).sort("updated_at", -1))
    return jsonify(clean({"inventories": [{**r, "summary": _compute(r)["totals"], "lines": len(r.get("lines", []))} for r in rows]}))


@calculator_bp.route("/calculator/inventories/<inv_id>", methods=["GET", "DELETE", "OPTIONS"])
@require_auth
def inventory(inv_id):
    inv = _owned(inv_id)
    if not inv:
        return jsonify({"status": "error", "message": "Inventory not found"}), 404
    if request.method == "DELETE":
        calc_inventories_collection.delete_one({"_id": inv["_id"]})
        calc_uploads_collection.delete_many({"inventory_id": str(inv["_id"])})
        return jsonify({"status": "ok"})
    uploads = list(calc_uploads_collection.find({"inventory_id": str(inv["_id"])}).sort("uploaded_at", -1))
    return jsonify(clean({**inv, "uploads": uploads, "calculation": _compute(inv)}))


@calculator_bp.route("/calculator/inventories/<inv_id>/lines", methods=["POST", "OPTIONS"])
@require_auth
def upsert_line(inv_id):
    """Add a manual line, or edit/exclude an existing one (body.line_id)."""
    inv = _owned(inv_id)
    if not inv:
        return jsonify({"status": "error", "message": "Inventory not found"}), 404
    body = request.get_json(silent=True) or {}
    if body.get("activity_type") and body["activity_type"] not in ACTIVITY_TYPES:
        return jsonify({"status": "error", "message": "Unknown activity type"}), 400
    lines = inv.get("lines", [])
    if body.get("line_id"):
        for ln in lines:
            if ln["line_id"] == body["line_id"]:
                for k in ("activity_type", "quantity", "unit", "period", "facility", "excluded", "reviewed"):
                    if k in body:
                        ln[k] = body[k]
                ln["edited_by_user"] = True
    else:
        try:
            qty = float(body.get("quantity"))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "quantity must be a number"}), 400
        lines.append({"line_id": str(ObjectId()), "activity_type": body.get("activity_type"), "quantity": qty,
                      "unit": body.get("unit"), "period": body.get("period"), "facility": body.get("facility"),
                      "source": "manual", "reviewed": True})
    calc_inventories_collection.update_one({"_id": inv["_id"]}, {"$set": {"lines": lines, "updated_at": _now()}})
    inv["lines"] = lines
    return jsonify(clean({"status": "ok", "calculation": _compute(inv)}))


def _csv_lines(raw):
    text = raw.decode("utf-8-sig", errors="replace")
    out = []
    for i, r in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        if r.get("activity_type") not in ACTIVITY_TYPES:
            continue
        try:
            qty = float(r.get("quantity", "").replace(",", ""))
        except ValueError:
            continue
        out.append({"activity_type": r["activity_type"], "quantity": qty, "unit": r.get("unit"),
                    "period": r.get("period"), "facility": r.get("facility"), "row": i,
                    "quote": f"CSV row {i}", "verified": True})
    return out


@calculator_bp.route("/calculator/inventories/<inv_id>/upload", methods=["POST", "OPTIONS"])
@require_auth
def upload(inv_id):
    inv = _owned(inv_id)
    if not inv:
        return jsonify({"status": "error", "message": "Inventory not found"}), 404
    f = request.files.get("file")
    if not f:
        return jsonify({"status": "error", "message": "file is required"}), 400
    raw = f.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        return jsonify({"status": "error", "message": "File larger than 20 MB"}), 413
    name = (f.filename or "upload")[:200]
    upload_rec = {"inventory_id": str(inv["_id"]), "owner_email": inv["owner_email"], "filename": name,
                  "sha256": D.sha256(raw), "uploaded_at": _now()}
    new_lines, gaps, cost = [], [], 0.0

    if name.lower().endswith(".csv"):
        extracted = _csv_lines(raw)
        upload_rec["kind"] = "csv"
    elif raw.startswith(b"%PDF"):
        if not ai_configured():
            return jsonify({"status": "error", "message": "AI extraction is not configured (DEEPSEEK_API_KEY)."}), 503
        pages = D.parse_pdf(raw)
        upload_rec.update({"kind": "pdf", "pages": len(pages)})
        text_pages = [(i + 1, t[:8000]) for i, t in enumerate(pages[:40]) if t.strip()]
        if not text_pages:
            return jsonify({"status": "error", "message": "No text found in this PDF (scanned image PDFs are not supported yet)."}), 422
        try:
            out = call_json("activity_extraction", _EXTRACT_SYSTEM, D.pages_block(name, text_pages), _EXTRACT_SCHEMA,
                            effort="low", context={"inventory_id": str(inv["_id"])}, use_cache=False)
        except AgentError as e:
            return jsonify({"status": "error", "message": str(e)}), 502
        cost = out["cost_usd"]
        gaps = out["result"]["data_gaps"]
        extracted = []
        for ln in out["result"]["lines"]:
            verified, page = D.verify_quote(pages, ln["page"], ln["quote"])
            extracted.append({**ln, "page": page, "verified": verified})
    else:
        return jsonify({"status": "error", "message": "Upload a PDF bill/invoice or a CSV with columns activity_type,quantity,unit,period,facility"}), 415

    for ln in extracted:
        new_lines.append({"line_id": str(ObjectId()), "source": "upload", "upload": name, "reviewed": False, **ln})
    upload_rec.update({"lines_extracted": len(new_lines), "data_gaps": gaps, "cost_usd": cost})
    calc_uploads_collection.insert_one(upload_rec)
    lines = inv.get("lines", []) + new_lines
    calc_inventories_collection.update_one({"_id": inv["_id"]}, {"$set": {"lines": lines, "updated_at": _now()}})
    inv["lines"] = lines
    return jsonify(clean({"status": "ok", "upload": upload_rec, "calculation": _compute(inv)}))
