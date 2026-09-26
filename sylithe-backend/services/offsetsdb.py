"""
Registry data for Module 2 — CarbonPlan OffsetsDB (deterministic, no LLM).

OffsetsDB is an open, regularly updated harmonisation of the Verra, Gold Standard, ACR,
CAR, ART TREES, Isometric and Cercarbono registries (projects + every issuance and
retirement transaction). It replaces per-registry scrapers: the old Verra search API
now serves the new Platts-hosted registry app and Gold Standard's bulk endpoint is
bot-protected (checked 2026-09-26).

Terms: CarbonPlan claims no copyright in the factual data; each registry's own terms may
apply (verify before redistribution). Cite: CarbonPlan (2024) "OffsetsDB",
https://carbonplan.org/research/offsets-db
"""
import ast
import csv
import io
import logging
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

import requests
from pymongo import ReplaceOne

from db import registry_projects_collection, registry_meta_collection

logger = logging.getLogger(__name__)

SOURCE_URL = "https://carbonplan-offsets-db.s3.us-west-2.amazonaws.com/production/latest/offsets-db.csv.zip"
SOURCE_CITATION = 'CarbonPlan (2024) "OffsetsDB", https://carbonplan.org/research/offsets-db'
REGISTRY_NAMES = {
    "verra": "Verra (VCS)", "gold-standard": "Gold Standard", "american-carbon-registry": "American Carbon Registry",
    "climate-action-reserve": "Climate Action Reserve", "art-trees": "ART TREES", "isometric": "Isometric",
    "cercarbono": "Cercarbono",
}

csv.field_size_limit(10_000_000)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _list(x):
    if not x:
        return []
    try:
        v = ast.literal_eval(x)
        return [str(i) for i in v] if isinstance(v, (list, tuple)) else [str(v)]
    except (ValueError, SyntaxError):
        return [x]


def _date(x):
    return (x or "")[:10] or None


def ingest(progress=None):
    """Download the latest OffsetsDB snapshot and upsert aggregated projects. Returns summary dict."""
    say = progress or (lambda *_: None)
    say("download", "Downloading OffsetsDB snapshot")
    resp = requests.get(SOURCE_URL, timeout=300)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = {n.split("/")[-1]: n for n in zf.namelist()}
    generated_at = None
    if "metadata.json" in names:
        import json
        generated_at = json.loads(zf.read(names["metadata.json"])).get("generated_at")

    say("credits", "Aggregating issuance & retirement transactions")
    agg = defaultdict(lambda: {
        "issuance_by_vintage": defaultdict(float), "issuance_by_year": defaultdict(float),
        "retirement_by_year": defaultdict(float), "n_issuances": 0, "n_retirements": 0,
        "last_issuance_at": None, "last_retirement_at": None, "beneficiaries": defaultdict(float),
    })
    with zf.open(names["credits.csv"]) as fh:
        for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
            pid = row.get("project_id")
            if not pid:
                continue
            a = agg[pid]
            qty = _f(row.get("quantity"))
            d = _date(row.get("transaction_date"))
            year = d[:4] if d else "unknown"
            kind = row.get("transaction_type")
            if kind == "issuance":
                a["n_issuances"] += 1
                a["issuance_by_vintage"][row.get("vintage") or "unknown"] += qty
                a["issuance_by_year"][year] += qty
                if d and (a["last_issuance_at"] is None or d > a["last_issuance_at"]):
                    a["last_issuance_at"] = d
            elif kind == "retirement":
                a["n_retirements"] += 1
                a["retirement_by_year"][year] += qty
                if d and (a["last_retirement_at"] is None or d > a["last_retirement_at"]):
                    a["last_retirement_at"] = d
                ben = (row.get("retirement_beneficiary_harmonized") or "").strip()
                if ben:
                    a["beneficiaries"][ben] += qty

    say("projects", "Upserting projects")
    now = datetime.now(timezone.utc)
    ops, count = [], 0
    with zf.open(names["projects.csv"]) as fh:
        for p in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
            pid = p["project_id"]
            a = agg.get(pid)
            doc = {
                "_id": pid, "project_id": pid, "name": p.get("name"), "registry": p.get("registry"),
                "registry_name": REGISTRY_NAMES.get(p.get("registry"), p.get("registry")),
                "country": p.get("country") or None, "category": p.get("category"),
                "project_type": p.get("project_type"), "protocol": _list(p.get("protocol")),
                "protocol_unassigned": _list(p.get("protocol_unassigned")),
                "proponent": p.get("proponent") or None, "status": p.get("status") or "unknown",
                "project_url": p.get("project_url"), "is_compliance": p.get("is_compliance") == "True",
                "listed_at": _date(p.get("listed_at")), "first_issuance_at": _date(p.get("first_issuance_at")),
                "first_retirement_at": _date(p.get("first_retirement_at")),
                "issued": _f(p.get("issued")), "retired": _f(p.get("retired")),
                "source": {"dataset": "OffsetsDB", "generated_at": generated_at, "url": SOURCE_URL,
                           "citation": SOURCE_CITATION},
                "ingested_at": now,
            }
            if a:
                doc.update({
                    "issuance_by_vintage": dict(sorted(a["issuance_by_vintage"].items())),
                    "issuance_by_year": dict(sorted(a["issuance_by_year"].items())),
                    "retirement_by_year": dict(sorted(a["retirement_by_year"].items())),
                    "n_issuances": a["n_issuances"], "n_retirements": a["n_retirements"],
                    "last_issuance_at": a["last_issuance_at"], "last_retirement_at": a["last_retirement_at"],
                    "top_beneficiaries": [{"name": k, "quantity": v} for k, v in
                                          sorted(a["beneficiaries"].items(), key=lambda kv: -kv[1])[:8]],
                })
            doc["retirement_ratio"] = round(doc["retired"] / doc["issued"], 4) if doc["issued"] else None
            ops.append(ReplaceOne({"_id": pid}, doc, upsert=True))
            count += 1
            if len(ops) >= 1000:
                registry_projects_collection.bulk_write(ops, ordered=False)
                ops = []
    if ops:
        registry_projects_collection.bulk_write(ops, ordered=False)

    summary = {"_id": "offsetsdb", "generated_at": generated_at, "ingested_at": now, "projects": count,
               "source_url": SOURCE_URL, "citation": SOURCE_CITATION}
    registry_meta_collection.replace_one({"_id": "offsetsdb"}, summary, upsert=True)
    say("done", f"{count} projects ingested")
    return summary


def meta():
    return registry_meta_collection.find_one({"_id": "offsetsdb"}, {"_id": 0})


def developer_portfolio(proponent):
    """Deterministic track-record facts for a developer across all registries."""
    if not proponent:
        return None
    rows = list(registry_projects_collection.find(
        {"proponent": proponent},
        {"_id": 0, "project_id": 1, "name": 1, "registry": 1, "status": 1, "issued": 1, "retired": 1,
         "category": 1, "country": 1, "protocol": 1}))
    return {
        "proponent": proponent,
        "projects": len(rows),
        "registries": sorted({r["registry"] for r in rows}),
        "countries": sorted({r["country"] for r in rows if r.get("country")}),
        "categories": sorted({r["category"] for r in rows if r.get("category")}),
        "total_issued": sum(r.get("issued") or 0 for r in rows),
        "total_retired": sum(r.get("retired") or 0 for r in rows),
        "with_issuance": sum(1 for r in rows if (r.get("issued") or 0) > 0),
        "statuses": {s: sum(1 for r in rows if r.get("status") == s) for s in {r.get("status") for r in rows}},
        "sample": sorted(rows, key=lambda r: -(r.get("issued") or 0))[:10],
    }
