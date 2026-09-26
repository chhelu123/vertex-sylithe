"""
SBTi Target Dashboard data (deterministic, no LLM).

Source: https://sciencebasedtargets.org/target-dashboard — "Download data by company / by target"
(updated weekly on Thursdays). Matched to companies by ISIN first, then by exact normalised name,
so similarly named group companies (e.g. a subsidiary) are never attached to the wrong company.
"""
import io
import logging
import re
from datetime import datetime, timezone

import requests
from openpyxl import load_workbook

from db import sbti_companies_collection, sbti_targets_collection, registry_meta_collection

logger = logging.getLogger(__name__)

COMPANIES_URL = "https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx"
TARGETS_URL = "https://files.sciencebasedtargets.org/production/files/targets-excel.xlsx"
DASHBOARD_URL = "https://sciencebasedtargets.org/target-dashboard"
REFRESH_DAYS = 7
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
_SUFFIX = re.compile(r"\b(limited|ltd|private|pvt|inc|corp|corporation|company|co|plc|llc)\b\.?", re.I)


def norm_name(s):
    s = _SUFFIX.sub(" ", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _rows(url):
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=120)
    r.raise_for_status()
    ws = load_workbook(io.BytesIO(r.content), read_only=True, data_only=True).active
    it = ws.iter_rows(values_only=True)
    header = [h for h in next(it)]
    for row in it:
        if row and row[0] is not None:
            yield {h: (v.isoformat() if isinstance(v, datetime) else v) for h, v in zip(header, row) if h}


def _clean(v):
    return None if v in (None, "", "NA") else v


def ingest():
    now = datetime.now(timezone.utc)
    companies = []
    for r in _rows(COMPANIES_URL):
        doc = {k: _clean(v) for k, v in r.items()}
        doc["_id"] = str(int(float(r["sbti_id"])))
        doc["name_norm"] = norm_name(r.get("company_name"))
        companies.append(doc)
    targets = []
    for r in _rows(TARGETS_URL):
        if r.get("action") != "Target":
            continue
        doc = {k: _clean(v) for k, v in r.items()}
        doc["_id"] = r["row_entry_id"]
        doc["sbti_id"] = str(int(float(r["sbti_id"])))
        targets.append(doc)
    if companies:
        sbti_companies_collection.delete_many({})
        sbti_companies_collection.insert_many(companies)
    if targets:
        sbti_targets_collection.delete_many({})
        sbti_targets_collection.insert_many(targets)
    meta = {"_id": "sbti", "ingested_at": now, "companies": len(companies), "targets": len(targets),
            "source": DASHBOARD_URL}
    registry_meta_collection.replace_one({"_id": "sbti"}, meta, upsert=True)
    return meta


def ensure_fresh():
    meta = registry_meta_collection.find_one({"_id": "sbti"})
    if meta and (datetime.now(timezone.utc) - meta["ingested_at"].replace(tzinfo=timezone.utc)).days < REFRESH_DAYS:
        return meta
    try:
        return ingest()
    except Exception as e:  # SBTi being unreachable must not break company research
        logger.warning(f"SBTi refresh failed: {e}")
        return meta


def _pct(v):
    try:
        return float(str(v).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _yr(v):
    m = re.search(r"(\d{4})", str(v or ""))
    return int(m.group(1)) if m else None


def lookup(isin=None, name=None):
    """SBTi status + Scope 1+2 targets for a company, or None if the company isn't on the dashboard."""
    ensure_fresh()
    c = sbti_companies_collection.find_one({"isin": isin}) if isin else None
    matched_by = "ISIN" if c else None
    if not c and name:
        c = sbti_companies_collection.find_one({"name_norm": norm_name(name)})
        matched_by = "exact name" if c else None
    if not c:
        return None
    rows = list(sbti_targets_collection.find({"sbti_id": c["_id"]}))
    targets = []
    for t in rows:
        targets.append({
            "horizon": t.get("target"), "scope": t.get("scope"), "type": t.get("type"), "sub_type": t.get("sub_type"),
            "reduction_pct": _pct(t.get("target_value")), "base_year": _yr(t.get("base_year")),
            "target_year": _yr(t.get("target_year")), "year_type": t.get("year_type"),
            "classification": t.get("target_classification_short"), "wording": t.get("target_wording"),
            "published": t.get("date_published"),
        })
    s12 = [t for t in targets if t["scope"] in ("1+2", "1+2+3") and t["type"] == "Absolute"
           and t["sub_type"] == "Reduction" and t["reduction_pct"] and t["base_year"] and t["target_year"]]
    near = sorted([t for t in s12 if t["horizon"] == "Near-term"], key=lambda t: t["target_year"])
    return {
        "sbti_id": c["_id"], "company_name": c.get("company_name"), "matched_by": matched_by,
        "near_term_status": c.get("near_term_status"), "near_term_classification": c.get("near_term_target_classification"),
        "near_term_target_year": c.get("near_term_target_year"), "net_zero_status": c.get("net_zero_status"),
        "net_zero_year": c.get("net_zero_year"), "status_reason": c.get("status_reason"),
        "full_target_language": c.get("full_target_language"), "date_updated": c.get("date_updated"),
        "targets": targets, "scope12_near_term": near[0] if near else None,
        "source": DASHBOARD_URL,
    }
