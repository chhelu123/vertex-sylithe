"""
NSE public-filings client (no LLM).

Used by the Module 1 discovery step instead of web search:
  - EQUITY_L.csv → company resolver (symbol, name, ISIN) for every NSE-listed equity
  - /api/annual-reports            → annual report PDFs
  - /api/corporate-bussiness-sustainabilitiy → BRSR PDF + BRSR XBRL (SEBI in-capmkt taxonomy)

Access is on-demand for one company at a time and cached; confirm NSE's terms
before any bulk / production crawling (sylithe-docs/research/SYLVERRA_RESEARCH.md §2.2).
"""
import csv
import io
import logging
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

from db import nse_equities_collection

logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
ANNUAL_REPORTS_URL = "https://www.nseindia.com/api/annual-reports"
BRSR_URL = "https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy"  # (sic) NSE's own spelling
EQUITY_LIST_TTL_S = 7 * 24 * 3600

_session = None


class NseError(Exception):
    pass


def _http():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Accept": "application/json,text/csv,*/*",
                                 "Referer": "https://www.nseindia.com/"})
    return _session


def _get(url, params=None, timeout=30):
    last = None
    for attempt in range(3):
        try:
            r = _http().get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise NseError(f"NSE request failed ({url}): {last}")


def refresh_equity_list(force=False):
    meta = nse_equities_collection.find_one({"_id": "__meta__"})
    if meta and not force and time.time() - meta["fetched_ts"] < EQUITY_LIST_TTL_S:
        return meta["count"]
    text = _get(EQUITY_LIST_URL, timeout=60).text
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        if not r.get("SYMBOL"):
            continue
        rows.append({
            "_id": r["SYMBOL"], "symbol": r["SYMBOL"], "name": r.get("NAME OF COMPANY", ""),
            "isin": r.get("ISIN NUMBER", ""), "series": r.get("SERIES", ""),
            "listed_on": r.get("DATE OF LISTING", ""), "name_lc": r.get("NAME OF COMPANY", "").lower(),
        })
    if rows:
        nse_equities_collection.delete_many({"_id": {"$ne": "__meta__"}, "symbol": {"$nin": [x["symbol"] for x in rows]}})
        for x in rows:
            nse_equities_collection.replace_one({"_id": x["_id"]}, x, upsert=True)
        nse_equities_collection.replace_one({"_id": "__meta__"}, {"_id": "__meta__", "fetched_ts": time.time(),
                                                                   "count": len(rows)}, upsert=True)
    return len(rows)


_STOP = {"limited", "ltd", "ltd.", "the", "india", "industries", "company", "corporation", "co", "and", "&"}


def _tokens(s):
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t and t not in _STOP}


def resolve(query, limit=8):
    """Fuzzy-match a company name or symbol against the NSE equity list."""
    try:
        refresh_equity_list()
    except NseError as e:
        logger.warning(f"equity list refresh failed: {e}")
    q = query.strip()
    if not q:
        return []
    exact = nse_equities_collection.find_one({"_id": q.upper()})
    qt = _tokens(q)
    ql = q.lower()
    scored = []
    for e in nse_equities_collection.find({"_id": {"$ne": "__meta__"}}, {"_id": 0}):
        nt = _tokens(e["name"])
        overlap = len(qt & nt) / max(len(qt), 1)
        ratio = SequenceMatcher(None, ql, e["name_lc"]).ratio()
        starts = 1.0 if e["name_lc"].startswith(ql) or e["symbol"].lower().startswith(ql) else 0.0
        score = 0.5 * overlap + 0.3 * ratio + 0.2 * starts
        if score > 0.35:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    out = [dict(e, match_score=round(s, 3)) for s, e in scored[:limit]]
    if exact:
        exact.pop("_id", None)
        out = [dict(exact, match_score=1.0)] + [o for o in out if o["symbol"] != exact["symbol"]]
    for o in out:
        o.pop("name_lc", None)
    return out[:limit]


def get_equity(symbol):
    e = nse_equities_collection.find_one({"_id": symbol.upper()}, {"_id": 0, "name_lc": 0})
    if not e:
        refresh_equity_list()
        e = nse_equities_collection.find_one({"_id": symbol.upper()}, {"_id": 0, "name_lc": 0})
    return e


def _fy(from_yr, to_yr):
    try:
        return f"FY{int(from_yr)}-{str(int(to_yr))[-2:]}"
    except (TypeError, ValueError):
        return None


def annual_reports(symbol):
    data = _get(ANNUAL_REPORTS_URL, {"index": "equities", "symbol": symbol}).json().get("data") or []
    out = []
    for d in data:
        if not (d.get("fileName") or "").lower().endswith(".pdf"):
            continue
        out.append({
            "document_type": "annual_report",
            "title": f"Annual Report {_fy(d.get('fromYr'), d.get('toYr'))}",
            "reporting_period": _fy(d.get("fromYr"), d.get("toYr")),
            "publication_date": d.get("broadcast_dttm"),
            "url": d["fileName"],
            "size": d.get("attFileSize"),
            "found_via": "NSE annual reports filing",
        })
    return out


def brsr_filings(symbol):
    data = _get(BRSR_URL, {"index": "equities", "symbol": symbol}).json().get("data") or []
    out = []
    for d in data:
        period = _fy(d.get("fyFrom"), d.get("fyTo"))
        base = {"reporting_period": period, "publication_date": d.get("submissionDate"),
                "found_via": "NSE BRSR filing", "revision": d.get("revisionDate")}
        if d.get("attachmentFile"):
            out.append({**base, "document_type": "brsr", "title": f"BRSR {period}", "url": d["attachmentFile"],
                        "size": d.get("attFileSize")})
        if d.get("xbrlFile"):
            out.append({**base, "document_type": "brsr_xbrl", "title": f"BRSR XBRL {period}", "url": d["xbrlFile"],
                        "size": d.get("xbrlFileSize")})
    return out


DOWNLOAD_DEADLINE_S = 180


def download(url, max_bytes=80 * 1024 * 1024, deadline_s=DOWNLOAD_DEADLINE_S):
    """Stream a file with a hard overall deadline (a trickling server must not stall an agent job)."""
    started = time.time()
    try:
        r = _http().get(url, timeout=(15, 60), stream=True)
    except requests.RequestException as e:
        raise NseError(f"download failed: {e}") from e
    if r.status_code != 200:
        raise NseError(f"download failed: HTTP {r.status_code}")
    buf = io.BytesIO()
    try:
        for chunk in r.iter_content(256 * 1024):
            buf.write(chunk)
            if buf.tell() > max_bytes:
                raise NseError("file larger than 80 MB")
            if time.time() - started > deadline_s:
                raise NseError(f"download exceeded {deadline_s}s ({buf.tell() // 1_000_000} MB received)")
    except requests.RequestException as e:
        raise NseError(f"download interrupted: {e}") from e
    finally:
        r.close()
    return buf.getvalue()


def now():
    return datetime.now(timezone.utc)
