"""
Module 1 — Company Carbon Intelligence pipeline (spec §7–§10, §31).

Nobody uploads anything here: agents discover public filings themselves.

  Company name / NSE symbol
    → Company Resolver            NSE equity list (fuzzy match)                        [code]
    → Document Discovery Agent    NSE annual-report + BRSR filings (PDF + XBRL)        [code]
    → BRSR XBRL Parser            Scope 1/2, energy, water, waste, revenue — exact     [code, High confidence]
    → Carbon Narrative Agent      BRSR PDF pages → targets, credits, Scope 3, gaps     [DeepSeek + quote verification]
    → Financial & Litigation Agent annual report pages → P&L lines, legal/env matters  [DeepSeek + quote verification]
    → KPIs + Company Carbon Rating                                                     [code, services/company_rating.py]
"""
import logging
import re
from datetime import datetime, timezone

from pymongo import ReturnDocument

from db import companies_collection, company_documents_collection, company_metrics_collection
from services import documents as D
from services import nse
from services.ai import call_json, AgentError
from services.brsr_xbrl import parse as parse_xbrl
from services.evidence import (
    save_evidence, obj, arr, nullable, enum, STR, NUM, INT, BOOL,
    REPORTED, CALCULATED, HIGH, MEDIUM, LOW,
)
from services.units import normalise

logger = logging.getLogger(__name__)

PROMPT_VERSION = "m1-v1"

METRICS = (
    "scope1_tco2e", "scope2_tco2e", "scope2_location_tco2e", "scope2_market_tco2e", "scope3_tco2e",
    "emissions_intensity_revenue", "emissions_intensity_physical",
    "total_energy_gj", "renewable_energy_gj", "renewable_energy_pct", "electricity_consumption_gj",
    "energy_intensity_revenue",
    "water_withdrawal_kl", "water_consumption_kl", "water_intensity_revenue",
    "waste_generated_t", "waste_recovered_t", "waste_recovery_pct",
)
FIN_METRICS = (
    "revenue_inr_cr", "ebitda_inr_cr", "pat_inr_cr", "capex_inr_cr", "environmental_capex_inr_cr",
    "sustainability_expenditure_inr_cr", "csr_spend_inr_cr", "legal_professional_fees_inr_cr",
    "carbon_credit_spend_inr_cr", "renewable_investment_inr_cr", "environmental_penalties_inr_cr",
)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]


def normalize_period(p):
    """'FY 2024-25', 'FY25', '2024-2025', 'FY2025' → 'FY2024-25' where possible."""
    if not p:
        return None
    s = str(p).upper().replace(" ", "")
    m = re.search(r"(20\d{2})[-–/](20)?(\d{2})", s)
    if m:
        return f"FY{m.group(1)}-{m.group(3)}"
    m = re.search(r"FY(20)?(\d{2})$", s)
    if m:
        end = int(m.group(2))
        return f"FY20{end - 1:02d}-{end:02d}"
    m = re.search(r"(20\d{2})", s)
    if m:
        return f"CY{m.group(1)}"
    return str(p)


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- persistence helpers

def _store_document(company, d, *, raw=None, pages=None, status=None, error=None):
    doc_hash = D.sha256(raw) if raw else None
    record = {
        "company_id": company["_id"],
        "document_type": d["document_type"],
        "title": d["title"],
        "reporting_period": normalize_period(d.get("reporting_period")),
        "publication_date": d.get("publication_date"),
        "source_url": d["url"],
        "source_domain": re.sub(r"^https?://(www\.)?", "", d["url"]).split("/")[0],
        "document_hash": doc_hash,
        "size": d.get("size"),
        "page_count": len(pages) if pages else None,
        "found_via": d.get("found_via"),
        "status": status or ("parsed" if pages else "indexed"),
        "error": error,
        "retrieved_at": _now(),
    }
    if doc_hash:
        dup = company_documents_collection.find_one({"company_id": company["_id"], "document_hash": doc_hash,
                                                     "source_url": {"$ne": d["url"]}})
        if dup:
            record.update({"status": "duplicate", "duplicate_of": str(dup["_id"])})
    company_documents_collection.update_one({"company_id": company["_id"], "source_url": d["url"]},
                                            {"$set": record}, upsert=True)
    return company_documents_collection.find_one({"company_id": company["_id"], "source_url": d["url"]})


def _put_metric(company, doc, *, metric, value, unit, period, evidence_id, label, confidence, verified,
                method, page=None, boundary=None, value_norm=None, unit_norm=None):
    if value_norm is None:
        value_norm, unit_norm, _ = normalise(metric, value, unit)
    company_metrics_collection.update_one(
        {"company_id": company["_id"], "metric": metric, "period": period, "document_id": str(doc["_id"])},
        {"$set": {
            "company_id": company["_id"], "metric": metric, "period": period,
            "value": value, "unit": unit, "value_norm": value_norm, "unit_norm": unit_norm,
            "boundary": boundary, "label": label, "confidence": confidence, "verified": verified,
            "evidence_id": evidence_id, "document_id": str(doc["_id"]), "document_type": doc["document_type"],
            "source_title": doc["title"], "source_url": doc["source_url"], "page": page,
            "extraction_method": method, "updated_at": _now(),
        }},
        upsert=True,
    )


def _verify(pages, page, quote):
    verified, page = D.verify_quote(pages, page, quote)
    return verified, page, (HIGH if verified else LOW)


# ---------------------------------------------------------------- XBRL (deterministic)

# Upper bounds for per-₹-crore intensities. Heavy emitters (cement, steel, power) sit in the hundreds to low
# thousands of tCO2e per ₹ crore; values far above these indicate a unit error in the filing (e.g. a filer
# entering "per ₹ crore" figures in the per-rupee field, or revenue in crores in an INR field).
_INTENSITY_MAX = {"emissions_intensity_revenue": 1e4, "energy_intensity_revenue": 1e5, "water_intensity_revenue": 1e5}


def validate_xbrl_facts(facts):
    """Return {id(fact): reason} for tagged values that fail plausibility checks."""
    issues = {}
    by = {(f["metric"], f["period"]): f for f in facts}
    for f in facts:
        m, v = f["metric"], f["value"]
        if m == "revenue_inr_cr" and v < 1:
            issues[id(f)] = "Revenue below ₹1 crore — likely entered in crores/lakhs in an INR field"
        elif m in _INTENSITY_MAX and v > _INTENSITY_MAX[m]:
            issues[id(f)] = f"Implausible intensity ({v:,.0f} per ₹ crore) — likely a unit error in the filing"
        elif m == "scope3_tco2e" and v == 0:
            issues[id(f)] = "Scope 3 tagged as 0 — treated as not disclosed"
        elif m == "total_energy_gj":
            # Grid/fossil energy emits roughly 0.05–0.2 tCO2 per GJ; if Scope 1+2 is far below 1% of the
            # non-renewable energy total, the energy figure was almost certainly entered in MJ (1000x).
            ren = by.get(("renewable_energy_gj", f["period"]))
            s1, s2 = by.get(("scope1_tco2e", f["period"])), by.get(("scope2_tco2e", f["period"]))
            non_ren = v - (ren["value"] if ren else 0)
            if s1 and s2 and non_ren > 0 and (s1["value"] + s2["value"]) < 0.002 * non_ren:
                issues[id(f)] = ("Energy total inconsistent with reported Scope 1+2 (likely MJ entered as GJ) — "
                                 "energy KPIs not used")
        elif m == "waste_recovered_t":
            gen = by.get(("waste_generated_t", f["period"]))
            if gen and gen["value"] and v > gen["value"] * 1.05:
                issues[id(f)] = "Waste recovered exceeds waste generated (may include legacy stock) — ratio not computed"
    return issues


def revalidate_stored_xbrl(company_id):
    """Re-apply plausibility checks to stored XBRL values (e.g. after a new check is added). Returns issue list."""
    rows = list(company_metrics_collection.find({"company_id": company_id, "document_type": "brsr_xbrl"}))
    facts = [{"metric": r["metric"], "period": r["period"], "value": r["value"], "_row": r} for r in rows]
    issues = validate_xbrl_facts(facts)
    found = []
    for f in facts:
        issue = issues.get(id(f))
        company_metrics_collection.update_one({"_id": f["_row"]["_id"]}, {"$set": {"validation_issue": issue}})
        if issue:
            found.append(f"{f['metric']} {f['period']}: {issue}")
    # derived energy metrics from the same filing inherit the energy check
    bad_periods = [f["period"] for f in facts if f["metric"] == "total_energy_gj" and issues.get(id(f))]
    if bad_periods:
        company_metrics_collection.update_many(
            {"company_id": company_id, "document_type": "brsr_xbrl", "period": {"$in": bad_periods},
             "metric": {"$in": ["renewable_energy_gj", "electricity_consumption_gj", "energy_intensity_revenue"]}},
            {"$set": {"validation_issue": "Energy figures in this filing failed the energy/emissions consistency check"}})
    return found


def ingest_xbrl(job, company, doc, raw, pdf_doc=None):
    parsed = parse_xbrl(raw)
    boundary = parsed["profile"].get("reporting_boundary")
    issues = validate_xbrl_facts(parsed["facts"])
    parsed["validation_issues"] = []
    for f in parsed["facts"]:
        label = CALCULATED if f.get("calculated") else REPORTED
        issue = issues.get(id(f))
        conf = LOW if issue else HIGH
        eid = save_evidence(
            "company", company["_id"], claim=f"{f['metric']} = {f['value']:,} {f['unit']} ({f['period']})"
                                              + (f" — flagged: {issue}" if issue else ""),
            quote=f["raw"], source_title=doc["title"], url=doc["source_url"], page=None,
            document_id=str(doc["_id"]), value=f["value"], unit=f["unit"], period=f["period"], label=label,
            confidence=conf, verified=True, method="xbrl_parser", agent="brsr_xbrl_parser",
        )
        _put_metric(company, doc, metric=f["metric"], value=f["value"], unit=f["unit"], period=f["period"],
                    evidence_id=eid, label=label, confidence=conf, verified=True,
                    method=f"BRSR XBRL parser ({f['element']})", boundary=boundary,
                    value_norm=f["value"], unit_norm=f["unit"])
        company_metrics_collection.update_one(
            {"company_id": company["_id"], "metric": f["metric"], "period": f["period"], "document_id": str(doc["_id"])},
            {"$set": {"validation_issue": issue}})
        if issue:
            parsed["validation_issues"].append(f"{f['metric']} {f['period']}: {issue}")
    return parsed


# ---------------------------------------------------------------- LLM extraction agents

_CARBON_SCHEMA = obj({
    "metrics": arr(obj({
        "metric": enum(*METRICS), "value": NUM, "unit": STR, "period": STR, "boundary": STR,
        "page": INT, "quote": STR, "label": enum(REPORTED, CALCULATED),
    })),
    "scope3_categories": arr(obj({"category": STR, "value": NUM, "unit": STR, "period": STR, "page": INT, "quote": STR})),
    "targets": arr(obj({
        "type": enum("net_zero", "carbon_neutral", "emissions_reduction", "renewable_energy", "energy_efficiency",
                     "water", "waste", "other"),
        "description": STR, "scope_coverage": STR,
        "base_year": nullable(STR), "base_value": nullable(NUM),
        "target_year": nullable(STR), "target_value": nullable(NUM), "target_unit": nullable(STR),
        "sbti_status": enum("validated", "committed", "not_mentioned", "other"),
        "page": INT, "quote": STR,
    })),
    "carbon_credits": arr(obj({
        "activity": enum("purchased", "retired", "generated", "sold"),
        "quantity_tco2e": nullable(NUM), "registry": nullable(STR), "project": nullable(STR),
        "vintage": nullable(STR), "price": nullable(STR), "page": INT, "quote": STR,
    })),
    "transition_actions": arr(obj({"description": STR, "page": INT, "quote": STR})),
    "data_gaps": arr(STR),
})

_CARBON_SYSTEM = """You are Sylithe's Carbon Narrative Agent. You read selected pages of an Indian company's
Business Responsibility and Sustainability Report (BRSR) and extract climate information exactly as disclosed.

Focus on what structured XBRL does not carry well: Scope 3 totals and categories, climate targets
(net-zero, reduction, renewable), SBTi status, carbon-credit purchases/retirements/generation, and concrete
transition actions (renewable PPAs, efficiency projects). You may also extract Scope 1/2/energy metrics if shown.

Rules:
- Only extract what the page states. Copy numbers exactly; never convert or estimate.
- Scope 2: use scope2_market_tco2e / scope2_location_tco2e only when the page explicitly says market-based or
  location-based; otherwise use scope2_tco2e.
- Write units explicitly as disclosed (e.g. "tCO2e", "metric tonnes CO2e", "GJ", "%").
- The quote must be a short verbatim span (8–30 words, numbers included) copied from the page text.
- `page` is the number attribute of the <page> element the quote came from.
- Periods like "FY 2024-25". If nothing relevant is found, return empty arrays and list data gaps."""


def extract_brsr_narrative(job, company, doc, pages):
    selected = D.select_pages(pages, ["emissions", "targets", "carbon_credits"], max_pages=16, max_chars=70000)
    if not selected:
        return None
    user = (f"Company: {company['name']}\nDocument: {doc['title']} ({doc.get('reporting_period')})\n\n"
            + D.pages_block(doc["title"], selected))
    out = call_json("carbon_narrative", _CARBON_SYSTEM, user, _CARBON_SCHEMA, effort="low",
                    prompt_version=PROMPT_VERSION, context={"job_id": job.id, "company_id": company["_id"]},
                    max_tokens=12000)
    job.add_cost(out["cost_usd"])
    return out["result"]


_FIN_SCHEMA = obj({
    "financials": arr(obj({
        "metric": enum(*FIN_METRICS), "value": NUM, "unit": STR, "period": STR,
        "basis": enum("consolidated", "standalone", "unspecified"), "page": INT, "quote": STR,
    })),
    "legal_disclosures": arr(obj({
        "category": enum("climate_litigation", "environmental_proceeding", "environmental_penalty",
                         "environmental_provision", "legal_expense_line", "other_legal"),
        "description": STR, "amount": nullable(NUM), "amount_unit": nullable(STR), "period": nullable(STR),
        "climate_related_explicit": BOOL, "status": nullable(STR), "page": INT, "quote": STR,
    })),
    "data_gaps": arr(STR),
})

_FIN_SYSTEM = """You are Sylithe's Financial & Climate-Litigation Agent. You read selected pages of an Indian
annual report and extract (1) financial context lines and (2) legal / environmental proceedings, penalties
and provisions.

Critical rule: never attribute a general legal expense to climate or emissions. Set
climate_related_explicit = true ONLY when the page explicitly says the matter or cost relates to climate,
greenhouse-gas emissions or carbon. "Legal and professional fees" is category legal_expense_line with
climate_related_explicit = false. Pollution-control-board / NGT / environmental-clearance matters are
environmental_proceeding or environmental_penalty.
Copy financial values exactly and write units explicitly ("INR crore", "INR lakh", "INR million").
Quotes: short verbatim spans (8–30 words) from the page; `page` = the page element's number attribute."""


def extract_financial_legal(job, company, doc, pages):
    selected = D.select_pages(pages, ["financial", "litigation"], max_pages=18, max_chars=80000)
    if not selected:
        return None
    user = (f"Company: {company['name']}\nDocument: {doc['title']} ({doc.get('reporting_period')})\n\n"
            + D.pages_block(doc["title"], selected))
    out = call_json("financial_litigation", _FIN_SYSTEM, user, _FIN_SCHEMA, effort="low",
                    prompt_version=PROMPT_VERSION, context={"job_id": job.id, "company_id": company["_id"]},
                    max_tokens=12000)
    job.add_cost(out["cost_usd"])
    return out["result"]


def _save_narrative(company, doc, pages, res):
    stored = 0
    for m in res.get("metrics", []):
        # a Scope 2 basis claim must be visible in the quoted text, otherwise record it as basis-unspecified
        basis_word = {"scope2_market_tco2e": "market", "scope2_location_tco2e": "location"}.get(m["metric"])
        if basis_word and basis_word not in m["quote"].lower():
            m["metric"] = "scope2_tco2e"
        verified, page, conf = _verify(pages, m["page"], m["quote"])
        if m["label"] != REPORTED and conf == HIGH:
            conf = MEDIUM
        period = normalize_period(m["period"])
        eid = save_evidence("company", company["_id"], claim=f"{m['metric']} = {m['value']} {m['unit']} ({period})",
                            quote=m["quote"], source_title=doc["title"], url=doc["source_url"], page=page,
                            document_id=str(doc["_id"]), value=m["value"], unit=m["unit"], period=period,
                            label=m["label"], confidence=conf, verified=verified, agent="carbon_narrative")
        _put_metric(company, doc, metric=m["metric"], value=m["value"], unit=m["unit"], period=period,
                    evidence_id=eid, label=m["label"], confidence=conf, verified=verified, page=page,
                    method="Carbon Narrative Agent (DeepSeek) + page quote verification", boundary=m.get("boundary"))
        stored += 1
    extras = {}
    for key in ("targets", "carbon_credits", "scope3_categories", "transition_actions"):
        items = []
        for item in res.get(key, []):
            verified, page, conf = _verify(pages, item["page"], item["quote"])
            item.update({"page": page, "verified": verified, "confidence": conf,
                         "source_title": doc["title"], "source_url": doc["source_url"]})
            if key == "scope3_categories":
                item["period"] = normalize_period(item.get("period"))
            item["evidence_id"] = save_evidence(
                "company", company["_id"], claim=item.get("description") or item.get("category") or key,
                quote=item["quote"], source_title=doc["title"], url=doc["source_url"], page=page,
                document_id=str(doc["_id"]), label=REPORTED, confidence=conf, verified=verified,
                agent="carbon_narrative")
            items.append(item)
        extras[key] = items
    return stored, extras, res.get("data_gaps", [])


def _save_financial_legal(company, doc, pages, res):
    for f in res.get("financials", []):
        verified, page, conf = _verify(pages, f["page"], f["quote"])
        period = normalize_period(f["period"])
        eid = save_evidence("company", company["_id"], claim=f"{f['metric']} = {f['value']} {f['unit']} ({period})",
                            quote=f["quote"], source_title=doc["title"], url=doc["source_url"], page=page,
                            document_id=str(doc["_id"]), value=f["value"], unit=f["unit"], period=period,
                            label=REPORTED, confidence=conf, verified=verified, agent="financial_litigation")
        _put_metric(company, doc, metric=f["metric"], value=f["value"], unit=f["unit"], period=period,
                    evidence_id=eid, label=REPORTED, confidence=conf, verified=verified, page=page,
                    method="Financial & Litigation Agent (DeepSeek) + page quote verification", boundary=f["basis"])
    legal = []
    for item in res.get("legal_disclosures", []):
        verified, page, conf = _verify(pages, item["page"], item["quote"])
        # spec §10 guard: only explicit climate attribution counts as climate litigation
        if item["category"] == "climate_litigation" and not item["climate_related_explicit"]:
            item["category"] = "other_legal"
        item.update({"page": page, "verified": verified, "confidence": conf, "origin": "annual_report",
                     "source_title": doc["title"], "source_url": doc["source_url"]})
        item["evidence_id"] = save_evidence(
            "company", company["_id"], claim=item["description"], quote=item["quote"], source_title=doc["title"],
            url=doc["source_url"], page=page, document_id=str(doc["_id"]), value=item.get("amount"),
            unit=item.get("amount_unit"), label=REPORTED, confidence=conf, verified=verified,
            agent="financial_litigation")
        legal.append(item)
    return legal, res.get("data_gaps", [])


def _download_pages(url):
    """Returns (pages, sha256); parsed text is cached so re-runs skip the download."""
    pages, digest, _ = D.cached_pages(url, lambda: nse.download(url))
    return pages, digest


# ---------------------------------------------------------------- pipeline

def ensure_company(symbol):
    eq = nse.get_equity(symbol)
    if not eq:
        raise AgentError(f"{symbol} is not an NSE-listed equity symbol.")
    slug = slugify(eq["name"])
    # atomic upsert — concurrent research jobs for the same company must not race on insert
    return companies_collection.find_one_and_update(
        {"_id": slug},
        {"$setOnInsert": {
            "slug": slug, "name": eq["name"], "aliases": [eq["symbol"]], "country": "India",
            "listing": {"nse_symbol": eq["symbol"], "isin": eq["isin"], "listed_on": eq.get("listed_on")},
            "status": "new", "created_at": _now(), "updated_at": _now(),
        }},
        upsert=True, return_document=ReturnDocument.AFTER,
    )


def run_company_research(job, symbol):
    from services.company_rating import rebuild_company_intelligence

    job.step("resolve", "Company Resolver — NSE listing")
    company = ensure_company(symbol)
    companies_collection.update_one({"_id": company["_id"]}, {"$set": {"status": "researching"}})
    job.step("resolve", "Company Resolver — NSE listing", "done", f"{company['name']} ({symbol})")

    job.step("discover", "Document Discovery Agent — NSE filings")
    try:
        brsr = nse.brsr_filings(symbol)
    except nse.NseError as e:
        brsr = []
        job.step("discover", "Document Discovery Agent — NSE filings", "running", f"BRSR list unavailable: {e}")
    try:
        reports = nse.annual_reports(symbol)
    except nse.NseError as e:
        reports = []
    found = brsr + reports
    docs = [_store_document(company, d) for d in found]
    job.step("discover", "Document Discovery Agent — NSE filings", "done",
             f"{len([d for d in found if d['document_type'] == 'brsr'])} BRSR, {len(reports)} annual reports")
    if not found:
        companies_collection.update_one({"_id": company["_id"]}, {"$set": {"status": "no_filings", "last_researched_at": _now()}})
        rebuild_company_intelligence(company["_id"])
        return {"company_id": company["_id"], "slug": company["slug"], "documents": 0}

    by_type = {}
    for d in sorted(docs, key=lambda x: x.get("reporting_period") or "", reverse=True):
        by_type.setdefault(d["document_type"], []).append(d)

    # 1) XBRL — two latest filings give up to three fiscal years of exact values
    profile = {}
    xbrl_docs = by_type.get("brsr_xbrl", [])[:2]
    job.step("xbrl", "BRSR XBRL Parser — exact tagged values")
    n_facts = 0
    xbrl_issues = []
    for d in xbrl_docs:
        try:
            raw = nse.download(d["source_url"])
            parsed = ingest_xbrl(job, company, d, raw)
            n_facts += len(parsed["facts"])
            xbrl_issues += parsed["validation_issues"]
            profile = profile or parsed["profile"]
            company_documents_collection.update_one({"_id": d["_id"]}, {"$set": {"status": "parsed", "document_hash": D.sha256(raw)}})
        except Exception as e:
            company_documents_collection.update_one({"_id": d["_id"]}, {"$set": {"status": "failed", "error": str(e)[:300]}})
    job.step("xbrl", "BRSR XBRL Parser — exact tagged values", "done" if n_facts else "failed",
             f"{n_facts} facts from {len(xbrl_docs)} filings" if n_facts else "no XBRL facts parsed")

    gaps, legal, extras_all = [], [], {"targets": [], "carbon_credits": [], "scope3_categories": [], "transition_actions": []}

    # 2) BRSR PDF narrative
    for d in by_type.get("brsr", [])[:1]:
        label = f"Carbon Narrative Agent — {d['title']}"
        job.step("narrative", label)
        try:
            pages, digest = _download_pages(d["source_url"])
            company_documents_collection.update_one({"_id": d["_id"]}, {"$set": {"status": "parsed", "page_count": len(pages), "document_hash": digest}})
            res = extract_brsr_narrative(job, company, d, pages)
            if res:
                n, extras, g = _save_narrative(company, d, pages, res)
                for k in extras_all:
                    extras_all[k] += extras.get(k, [])
                gaps += g
                job.step("narrative", label, "done",
                         f"{len(extras['targets'])} targets, {len(extras['carbon_credits'])} credit disclosures, {n} metrics")
            else:
                job.step("narrative", label, "done", "no climate narrative pages found")
        except (AgentError, D.DocumentError, nse.NseError) as e:
            job.step("narrative", label, "failed", str(e)[:200])

    # 3) Annual report — financial context + legal / environmental matters
    legal_reviewed = False
    for d in by_type.get("annual_report", [])[:1]:
        label = f"Financial & Litigation Agent — {d['title']}"
        job.step("financial", label)
        try:
            pages, digest = _download_pages(d["source_url"])
            company_documents_collection.update_one({"_id": d["_id"]}, {"$set": {"status": "parsed", "page_count": len(pages), "document_hash": digest}})
            res = extract_financial_legal(job, company, d, pages)
            if res:
                items, g = _save_financial_legal(company, d, pages, res)
                legal += items
                gaps += g
            legal_reviewed = True
            job.step("financial", label, "done", f"{len(legal)} legal/environmental disclosures")
        except (AgentError, D.DocumentError, nse.NseError) as e:
            job.step("financial", label, "failed", str(e)[:200])

    update = {
        "targets": extras_all["targets"], "carbon_credits": extras_all["carbon_credits"],
        "scope3_categories": extras_all["scope3_categories"], "transition_actions": extras_all["transition_actions"],
        "legal_disclosures": legal, "legal_reviewed": legal_reviewed,
        "data_gaps": sorted(set(gaps)) + [f"Filing check — {i}" for i in xbrl_issues],
        "status": "ready", "last_researched_at": _now(), "updated_at": _now(),
    }
    if profile:
        update.update({
            "legal_name": profile.get("name"), "cin": profile.get("cin"), "website": profile.get("website"),
            "headquarters": profile.get("corporate_office") or profile.get("registered_office"),
            "reporting_boundary": profile.get("reporting_boundary"), "fiscal_year_end": profile.get("fy_end"),
            "business_activities": profile.get("activities"),
            "industry": (profile.get("activities") or [None])[0],
            "assurance": {"assured": bool(profile.get("ghg_assured")), "provider_text": profile.get("ghg_assurance_text"),
                          "verified": True, "source_url": xbrl_docs[0]["source_url"] if xbrl_docs else None,
                          "source_title": xbrl_docs[0]["title"] if xbrl_docs else None},
        })
    companies_collection.update_one({"_id": company["_id"]}, {"$set": update})

    job.step("rating", "KPIs & Sylithe Company Carbon Rating")
    rating = rebuild_company_intelligence(company["_id"])
    job.step("rating", "KPIs & Sylithe Company Carbon Rating", "done",
             f"{rating['grade']} ({rating['overall_score']})" if rating.get("grade") else "grade withheld — insufficient data")
    return {"company_id": company["_id"], "slug": company["slug"], "documents": len(found)}
