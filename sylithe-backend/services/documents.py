"""
Document tool — deterministic, no LLM.

Downloads a public PDF, splits it into pages, and selects the pages relevant
to a topic by keyword scoring so agents only read what they need (cost, latency).
Quotes returned by agents are verified against the exact page text, which is
what makes "view source → page → highlighted evidence" trustworthy.
"""
import hashlib
import io
import logging
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 80 * 1024 * 1024
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# Topic → keywords used to pick pages for each agent.
TOPICS = {
    "emissions": ["scope 1", "scope 2", "scope 3", "ghg", "greenhouse", "tco2", "co2e", "emission intensity",
                  "emissions intensity", "carbon footprint", "principle 6"],
    "energy": ["energy consumption", "renewable", "electricity", "fuel consumption", "gigajoule", " gj", "energy intensity"],
    "water_waste": ["water withdrawal", "water consumption", "kilolitre", "waste generated", "recycled", "waste recovered", "hazardous waste"],
    "targets": ["net zero", "net-zero", "carbon neutral", "sbti", "science based", "target", "decarbon", "reduction target", "transition plan"],
    "carbon_credits": ["carbon credit", "offset", "retire", "verra", "gold standard", "vcs", "renewable energy certificate", "i-rec"],
    "financial": ["revenue from operations", "total income", "profit after tax", "ebitda", "capital expenditure", "legal and professional",
                  "csr", "environmental expenditure", "capex", "statement of profit and loss"],
    "litigation": ["litigation", "legal proceedings", "penalt", "show cause", "national green tribunal", "ngt", "pollution control board",
                   "fine", "contingent liabilit", "compounding fee", "environmental clearance", "non-compliance"],
    # Module 2 — project documents
    "project_additionality": ["additionality", "investment analysis", "barrier analysis", "common practice", "regulatory surplus"],
    "project_baseline": ["baseline scenario", "baseline emission", "reference region", "historical", "deforestation rate", "baseline"],
    "project_permanence": ["non-permanence", "permanence", "buffer", "reversal", "afolu non-permanence risk", "risk rating"],
    "project_leakage": ["leakage", "activity shifting", "displacement", "market effects"],
    "project_monitoring": ["monitoring plan", "monitoring report", "parameter", "frequency", "qa/qc", "quality assurance", "data and parameters"],
    "project_verification": ["verification", "validation", "vvb", "doe", "verification body", "opinion", "corrective action", "clarification request"],
    "project_methodology": ["methodology", "applicability", "vm00", "ams-", "acm00", "ar-", "tool"],
    "project_area": ["project area", "hectare", " ha ", "project boundary", "geographic", "coordinates", "location"],
    "project_issuance": ["emission reductions", "removals", "vcu", "ver", "credits", "ex-ante", "ex-post", "issuance", "tco2e"],
    "project_cobenefits": ["sdg", "sustainable development", "community", "biodiversity", "employment", "livelihood", "women", "stakeholder"],
}


class DocumentError(Exception):
    pass


DOWNLOAD_DEADLINE_S = 180


def download_pdf(url):
    started = time.time()
    try:
        resp = requests.get(url, headers={"User-Agent": _UA, "Accept": "application/pdf,*/*"}, timeout=(15, 60), stream=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DocumentError(f"download failed: {e}") from e
    data = io.BytesIO()
    try:
        for chunk in resp.iter_content(1024 * 256):
            data.write(chunk)
            if data.tell() > MAX_PDF_BYTES:
                raise DocumentError("document larger than 80 MB")
            if time.time() - started > DOWNLOAD_DEADLINE_S:
                raise DocumentError(f"download exceeded {DOWNLOAD_DEADLINE_S}s")
    except requests.RequestException as e:
        raise DocumentError(f"download interrupted: {e}") from e
    finally:
        resp.close()
    raw = data.getvalue()
    if not raw.startswith(b"%PDF"):
        raise DocumentError("URL did not return a PDF")
    return raw


def parse_pdf(raw):
    """Return list of page texts (index 0 = page 1)."""
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pages.append("")
        return pages
    except Exception as e:
        raise DocumentError(f"could not parse PDF: {e}") from e


def cached_pages(url, fetch):
    """
    Parsed page text cached by URL (filings are immutable), so re-running agents never re-downloads.
    `fetch()` must return raw PDF bytes. Returns (pages, sha256, from_cache).
    """
    from db import document_text_cache_collection as cache
    hit = cache.find_one({"_id": url})
    if hit:
        return hit["pages"], hit["sha256"], True
    raw = fetch()
    if not raw.startswith(b"%PDF"):
        raise DocumentError("URL did not return a PDF")
    pages = parse_pdf(raw)
    digest = sha256(raw)
    if sum(len(p) for p in pages) < 12_000_000:  # stay well under Mongo's 16 MB document limit
        cache.replace_one({"_id": url}, {"_id": url, "pages": pages, "sha256": digest,
                                         "cached_at": datetime.now(timezone.utc)}, upsert=True)
    return pages, digest, False


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def select_pages(pages, topics, max_pages=18, max_chars=90000):
    """Pick the most topic-relevant pages; returns [(page_number, text)] in page order."""
    keywords = [k for t in topics for k in TOPICS.get(t, [])]
    scored = []
    for i, text in enumerate(pages):
        low = text.lower()
        if not low.strip():
            continue
        score = sum(low.count(k) for k in keywords)
        if score:
            scored.append((score, i))
    scored.sort(reverse=True)
    chosen, total = [], 0
    for _, i in scored:
        if len(chosen) >= max_pages:
            break
        t = pages[i][:9000]
        if total + len(t) > max_chars:
            continue
        chosen.append(i)
        total += len(t)
    return [(i + 1, pages[i][:9000]) for i in sorted(chosen)]


def pages_block(doc_label, selected):
    """Render selected pages as a delimited DATA block for an agent prompt."""
    parts = [f'<document label="{doc_label}">']
    for num, text in selected:
        parts.append(f'<page number="{num}">\n{text}\n</page>')
    parts.append("</document>")
    return "\n".join(parts)


def _norm(s):
    return re.sub(r"[^a-z0-9.%]+", " ", (s or "").lower()).strip()


def verify_quote(pages, page_number, quote):
    """
    Check a quote against the cited page (and its neighbours, since PDF page labels
    and physical pages sometimes differ by one). Returns (verified, actual_page).
    """
    q = _norm(quote)
    if len(q) < 6:
        return False, page_number
    candidates = [page_number, page_number - 1, page_number + 1] if page_number else []
    for n in candidates:
        if 1 <= n <= len(pages):
            text = _norm(pages[n - 1])
            if q in text:
                return True, n
            # tolerate PDF-extraction spacing differences on long quotes
            if len(q) > 25:
                m = SequenceMatcher(None, text, q, autojunk=False).find_longest_match(0, len(text), 0, len(q))
                if m.size >= 0.8 * len(q):
                    return True, n
    return False, page_number
