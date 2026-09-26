"""
Company KPIs (spec §11) and the Sylithe Company Carbon Rating (spec §12, §53).

Pure code over stored, evidence-linked metrics — no LLM. Every KPI carries
current / previous / change % / target / progress / source / period / confidence,
and every rating dimension carries its score, reason and evidence ids.
A single overall grade is only published when enough dimensions are scored with
adequate data confidence; otherwise the rating says "Insufficient data".
"""
from datetime import datetime, timezone

from db import companies_collection, company_metrics_collection, company_ratings_collection
from services.evidence import HIGH, MEDIUM, LOW, CALCULATED, REPORTED, NOT_FOUND, INFERENCE

METHODOLOGY_VERSION = "Sylithe Company Carbon Rating v0.1"

DIMENSION_WEIGHTS = {
    "disclosure_quality": 15,
    "emissions_trajectory": 20,
    "carbon_intensity": 15,
    "renewable_transition": 15,
    "target_credibility": 15,
    "carbon_credit_use": 5,
    "climate_legal_risk": 5,
    "data_confidence": 10,
}
MIN_DIMENSIONS_FOR_GRADE = 5
GRADES = [(80, "A", "Leader"), (65, "B", "Advanced"), (50, "C", "Developing"), (35, "D", "Lagging"), (0, "E", "Weak")]

_DOC_RANK = {"brsr_xbrl": 0, "brsr": 1, "sustainability_report": 2, "esg_report": 2, "climate_report": 2,
             "integrated_report": 3, "annual_report": 4}
_CONF_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}

KPI_DEFS = [
    ("scope1", "Scope 1 emissions", "scope1_tco2e", "tCO2e", "lower"),
    ("scope2", "Scope 2 emissions", None, "tCO2e", "lower"),
    ("scope3", "Scope 3 emissions", "scope3_tco2e", "tCO2e", "lower"),
    ("total_emissions", "Total emissions (Scope 1+2)", None, "tCO2e", "lower"),
    ("emissions_intensity", "Emissions intensity (revenue)", "emissions_intensity_revenue", None, "lower"),
    ("renewable_pct", "Renewable energy share", None, "%", "higher"),
    ("total_energy", "Total energy consumption", "total_energy_gj", "GJ", "lower"),
    ("energy_intensity", "Energy intensity (revenue)", "energy_intensity_revenue", None, "lower"),
    ("waste_recovery", "Waste recycled / recovered", None, "%", "higher"),
    ("water_intensity", "Water intensity (revenue)", "water_intensity_revenue", None, "lower"),
    ("water_withdrawal", "Water withdrawal", "water_withdrawal_kl", "kL", "lower"),
    ("carbon_reduction", "Reduction vs baseline", None, "%", "higher"),
    ("carbon_credits", "Carbon credits retired", None, "tCO2e", None),
    ("net_zero_progress", "Net-zero / reduction target progress", None, "%", "higher"),
    ("disclosure_score", "Climate disclosure score", None, "/100", "higher"),
]


def _best_by_period(company_id, metric):
    """One value per period, preferring verified, higher-confidence, BRSR-first sources."""
    # values that failed plausibility checks stay in the evidence store but never feed KPIs or ratings
    rows = list(company_metrics_collection.find({"company_id": company_id, "metric": metric,
                                                 "validation_issue": {"$in": [None, ""]}}, {"_id": 0}))
    best = {}
    for r in rows:
        key = r.get("period") or "unknown"
        rank = (not r.get("verified"), _CONF_RANK.get(r.get("confidence"), 3), _DOC_RANK.get(r.get("document_type"), 4))
        if key not in best or rank < best[key][0]:
            best[key] = (rank, r)
    return {p: v[1] for p, v in best.items()}


def _series(company_id, metric):
    s = _best_by_period(company_id, metric)
    return [s[p] for p in sorted(s) if p != "unknown"]


def _val(row):
    if row is None:
        return None
    return row["value_norm"] if row.get("value_norm") is not None else row.get("value")


def _pct_change(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def _src(row):
    if not row:
        return None
    return {"title": row.get("source_title"), "url": row.get("source_url"), "page": row.get("page"),
            "evidence_id": row.get("evidence_id")}


def _kpi(key, label, unit, direction, cur_row=None, prev_row=None, cur=None, prev=None, period=None,
         prev_period=None, confidence=None, label_state=None, target=None, progress=None, sources=None, note=None):
    if cur_row is not None:
        cur = _val(cur_row)
        period = period or cur_row.get("period")
        confidence = confidence or cur_row.get("confidence")
        label_state = label_state or cur_row.get("label")
        unit = unit or cur_row.get("unit_norm") or cur_row.get("unit")
        sources = sources or [_src(cur_row)]
    if prev_row is not None:
        prev = _val(prev_row)
        prev_period = prev_period or prev_row.get("period")
    return {
        "key": key, "label": label, "unit": unit, "direction": direction,
        "current": cur, "period": period, "previous": prev, "previous_period": prev_period,
        "change_pct": _pct_change(cur, prev),
        "target": target, "progress_pct": progress,
        "confidence": confidence if cur is not None else None,
        "status": label_state if cur is not None else NOT_FOUND,
        "sources": [s for s in (sources or []) if s],
        "note": note,
    }


def _last_two(series):
    return (series[-1] if series else None), (series[-2] if len(series) > 1 else None)


def _combine(a, b, label="Calculated"):
    """Sum two period-aligned rows (e.g. Scope 1 + Scope 2)."""
    if a is None or b is None:
        return None
    va, vb = _val(a), _val(b)
    if va is None or vb is None or a.get("unit_norm") != "tCO2e" or b.get("unit_norm") != "tCO2e":
        return None
    conf = max((a.get("confidence"), b.get("confidence")), key=lambda c: _CONF_RANK.get(c, 3))
    return {"value_norm": round(va + vb, 2), "unit_norm": "tCO2e", "period": a["period"], "confidence": conf,
            "label": label, "sources": [_src(a), _src(b)]}


def _scope2_series(cid):
    """
    One Scope 2 basis for the whole series — never mix location- and market-based values across periods.
    Pick the basis covering the most periods; ties prefer the BRSR-tagged total (the official filing figure).
    """
    candidates = [_series(cid, m) for m in ("scope2_tco2e", "scope2_market_tco2e", "scope2_location_tco2e")]
    best = max(candidates, key=len)  # max() keeps the first on ties → BRSR total, then market, then location
    return best


def _ratio_series(cid, part, whole):
    parts = {r["period"]: r for r in _series(cid, part)}
    out = []
    for w in _series(cid, whole):
        p = parts.get(w["period"])
        if p and _val(w) and p.get("unit_norm") == w.get("unit_norm") and _val(p) <= _val(w) * 1.05:
            out.append({"value_norm": round(_val(p) / _val(w) * 100, 2), "period": w["period"],
                        "confidence": max((p["confidence"], w["confidence"]), key=lambda c: _CONF_RANK.get(c, 3)),
                        "label": CALCULATED, "sources": [_src(p), _src(w)]})
    return out


def _pct_series(cid, direct_metric, part, whole):
    direct = {r["period"]: {**r, "sources": [_src(r)]} for r in _series(cid, direct_metric) if 0 <= (_val(r) or 0) <= 100}
    for r in _ratio_series(cid, part, whole):
        direct.setdefault(r["period"], r)
    return [direct[p] for p in sorted(direct)]


def _from_derived(key, label, unit, direction, series):
    cur, prev = _last_two(series)
    if not cur:
        return _kpi(key, label, unit, direction)
    return _kpi(key, label, unit, direction, cur=cur["value_norm"], prev=prev["value_norm"] if prev else None,
                period=cur["period"], prev_period=prev["period"] if prev else None,
                confidence=cur["confidence"], label_state=cur["label"], sources=cur.get("sources"))


def _target_progress(company, total_series):
    """Progress toward the first emissions target that has a base year we hold data for."""
    by_period = {r["period"]: r for r in total_series}
    for t in company.get("targets") or []:
        if t.get("type") not in ("emissions_reduction", "net_zero", "carbon_neutral"):
            continue
        from services.company_agents import normalize_period
        base_p = normalize_period(t.get("base_year"))
        base = by_period.get(base_p)
        cur = total_series[-1] if total_series else None
        if not base or not cur or cur["period"] == base_p:
            continue
        base_v, cur_v = base["value_norm"], cur["value_norm"]
        if t.get("type") == "emissions_reduction" and t.get("target_value") is not None and "%" in (t.get("target_unit") or ""):
            target_abs = base_v * (1 - t["target_value"] / 100)
        elif t.get("type") in ("net_zero", "carbon_neutral"):
            target_abs = 0.0
        else:
            continue
        if base_v == target_abs:
            continue
        progress = round((base_v - cur_v) / (base_v - target_abs) * 100, 1)
        reduction = round((base_v - cur_v) / base_v * 100, 1) if base_v else None
        return {"target": t, "progress": progress, "reduction_pct": reduction, "base_period": base_p,
                "current_period": cur["period"], "confidence": cur["confidence"],
                "sources": cur.get("sources", []) + [{"title": t.get("source_title"), "url": t.get("source_url"),
                                                      "page": t.get("page"), "evidence_id": t.get("evidence_id")}]}
    return None


def compute_kpis(company):
    cid = company["_id"]
    s1 = _series(cid, "scope1_tco2e")
    s2 = _scope2_series(cid)
    s1_by = {r["period"]: r for r in s1}
    total = [c for c in (_combine(s1_by.get(r["period"]), r) for r in s2) if c]
    re_pct = _pct_series(cid, "renewable_energy_pct", "renewable_energy_gj", "total_energy_gj")
    waste_pct = _pct_series(cid, "waste_recovery_pct", "waste_recovered_t", "waste_generated_t")
    progress = _target_progress(company, total)

    kpis = []
    for key, label, metric, unit, direction in KPI_DEFS:
        if metric:
            cur, prev = _last_two(_series(cid, metric))
            kpis.append(_kpi(key, label, unit, direction, cur_row=cur, prev_row=prev))
        elif key == "scope2":
            cur, prev = _last_two(s2)
            k = _kpi(key, label, unit, direction, cur_row=cur, prev_row=prev)
            if cur:
                k["note"] = {"scope2_market_tco2e": "market-based", "scope2_location_tco2e": "location-based"}.get(
                    cur["metric"], "as reported in BRSR (basis not specified)")
            kpis.append(k)
        elif key == "total_emissions":
            kpis.append(_from_derived(key, label, unit, direction, total))
        elif key == "renewable_pct":
            kpis.append(_from_derived(key, label, unit, direction, re_pct))
        elif key == "waste_recovery":
            kpis.append(_from_derived(key, label, unit, direction, waste_pct))
        elif key == "carbon_reduction":
            if progress and progress["reduction_pct"] is not None:
                kpis.append(_kpi(key, label, unit, direction, cur=progress["reduction_pct"], period=progress["current_period"],
                                 confidence=progress["confidence"], label_state=CALCULATED, sources=progress["sources"],
                                 note=f"vs base {progress['base_period']}"))
            else:
                kpis.append(_kpi(key, label, unit, direction))
        elif key == "carbon_credits":
            retired = [c for c in company.get("carbon_credits") or [] if c["activity"] == "retired" and c.get("quantity_tco2e")]
            if retired:
                kpis.append(_kpi(key, label, unit, direction, cur=sum(c["quantity_tco2e"] for c in retired),
                                 confidence=min((c["confidence"] for c in retired), key=lambda c: -_CONF_RANK.get(c, 3)),
                                 label_state=REPORTED, period=retired[0].get("vintage"),
                                 sources=[{"title": c["source_title"], "url": c["source_url"], "page": c["page"],
                                           "evidence_id": c["evidence_id"]} for c in retired]))
            else:
                kpis.append(_kpi(key, label, unit, direction))
        elif key == "net_zero_progress":
            if progress:
                t = progress["target"]
                kpis.append(_kpi(key, label, unit, direction, cur=progress["progress"], period=progress["current_period"],
                                 confidence=progress["confidence"], label_state=CALCULATED, progress=progress["progress"],
                                 target=f"{t.get('description')}", sources=progress["sources"]))
            else:
                kpis.append(_kpi(key, label, unit, direction))
        elif key == "disclosure_score":
            kpis.append(None)  # filled after rating
    return kpis, {"total": total, "renewable": re_pct, "scope1": s1, "scope2": s2}


# ---------------------------------------------------------------- rating

def _dim(key, label, score, reason, evidence=None, confidence=None, state=None):
    return {"key": key, "label": label, "score": None if score is None else round(max(0, min(100, score)), 1),
            "reason": reason, "evidence_ids": [e for e in (evidence or []) if e],
            "confidence": confidence, "status": state or (NOT_FOUND if score is None else CALCULATED)}


def _ev(kpi):
    return [s.get("evidence_id") for s in (kpi or {}).get("sources", []) if s]


def compute_rating(company, kpis):
    k = {x["key"]: x for x in kpis if x}
    dims = []

    checklist = {
        "Scope 1": k["scope1"]["current"] is not None,
        "Scope 2": k["scope2"]["current"] is not None,
        "Scope 3": k["scope3"]["current"] is not None,
        "Energy": k["total_energy"]["current"] is not None,
        "Renewable share": k["renewable_pct"]["current"] is not None,
        "Water": k["water_withdrawal"]["current"] is not None or k["water_intensity"]["current"] is not None,
        "Waste": k["waste_recovery"]["current"] is not None,
        "Emissions intensity": k["emissions_intensity"]["current"] is not None,
        "Two-year history": k["total_emissions"]["previous"] is not None,
        "Climate targets": bool(company.get("targets")),
        "External assurance": bool((company.get("assurance") or {}).get("assured")),
    }
    present = [n for n, ok in checklist.items() if ok]
    missing = [n for n, ok in checklist.items() if not ok]
    dims.append(_dim("disclosure_quality", "Disclosure quality", len(present) / len(checklist) * 100,
                     f"{len(present)}/{len(checklist)} disclosure items found. Missing: {', '.join(missing) or 'none'}.",
                     confidence=HIGH))

    te = k["total_emissions"]
    if te["change_pct"] is not None:
        dims.append(_dim("emissions_trajectory", "Emissions trajectory", 60 - te["change_pct"] * 4,
                         f"Scope 1+2 changed {te['change_pct']:+.1f}% from {te['previous_period']} to {te['period']}.",
                         _ev(te), te["confidence"]))
    else:
        dims.append(_dim("emissions_trajectory", "Emissions trajectory", None, "Two comparable periods of Scope 1+2 not found."))

    ei = k["emissions_intensity"]
    if ei["change_pct"] is not None:
        dims.append(_dim("carbon_intensity", "Carbon intensity trend", 60 - ei["change_pct"] * 4,
                         f"Revenue emissions intensity changed {ei['change_pct']:+.1f}% ({ei['previous_period']} → {ei['period']}). "
                         "Sector benchmarks are not yet applied (v0.1).", _ev(ei), ei["confidence"]))
    else:
        dims.append(_dim("carbon_intensity", "Carbon intensity trend", None, "Two periods of emissions intensity not found."))

    rp = k["renewable_pct"]
    if rp["current"] is not None:
        extra = f", {rp['change_pct']:+.1f}% vs {rp['previous_period']}" if rp["change_pct"] is not None else ""
        dims.append(_dim("renewable_transition", "Renewable-energy transition", rp["current"] * 1.2,
                         f"Renewables supply {rp['current']:.1f}% of energy in {rp['period']}{extra}.", _ev(rp), rp["confidence"]))
    else:
        dims.append(_dim("renewable_transition", "Renewable-energy transition", None, "Renewable share not disclosed."))

    targets = company.get("targets") or []
    sbti = company.get("sbti") or {}
    sbti_status = (sbti.get("near_term_status") or "").lower()
    if sbti_status:
        # the SBTi dashboard is authoritative for validation status; disclosed wording alone is not
        targets = [dict(t, sbti_status="validated" if "validated" in sbti_status or "targets set" in sbti_status
                        else "committed" if sbti_status.startswith("commit") and "removed" not in sbti_status
                        else "not_mentioned") for t in targets] or ([{"type": "other", "sbti_status": "validated", "verified": True}]
                                                                     if "validated" in sbti_status else [])
    if targets:
        score, parts, evs = 0, [], []
        if any(t["type"] == "net_zero" and t.get("target_year") for t in targets):
            score += 30; parts.append("dated net-zero target")
        if any(t["type"] == "emissions_reduction" and t.get("base_year") and t.get("target_year") for t in targets):
            score += 30; parts.append("interim reduction target with base year")
        if any(t.get("sbti_status") == "validated" for t in targets):
            score += 30; parts.append("SBTi-validated")
        elif any(t.get("sbti_status") == "committed" for t in targets):
            score += 15; parts.append("SBTi commitment")
        if any(t["type"] == "renewable_energy" for t in targets):
            score += 10; parts.append("renewable-energy target")
        evs = [t.get("evidence_id") for t in targets]
        conf = HIGH if all(t.get("verified") for t in targets) else MEDIUM
        sbti_note = ""
        if sbti_status:
            sbti_note = f" SBTi dashboard: {sbti.get('near_term_status')}" + (f" ({sbti.get('status_reason')})" if sbti.get("status_reason") else "") + "."
        dims.append(_dim("target_credibility", "Climate target credibility", score,
                         f"Found: {', '.join(parts) or 'targets without base/target years'}.{sbti_note}", evs, conf))
    else:
        dims.append(_dim("target_credibility", "Climate target credibility", None, "No climate targets found in disclosures."))

    credits = company.get("carbon_credits") or []
    if credits:
        detailed = [c for c in credits if c.get("registry") and c.get("project")]
        score = 70 if len(detailed) == len(credits) else 40
        dims.append(_dim("carbon_credit_use", "Carbon-credit quality & use", score,
                         f"{len(credits)} carbon-credit disclosures; {len(detailed)} name both registry and project. "
                         "Project-level quality can be checked in Project Ratings.", [c.get("evidence_id") for c in credits], MEDIUM))
    else:
        dims.append(_dim("carbon_credit_use", "Carbon-credit quality & use", None, "No carbon-credit use disclosed."))

    legal = company.get("legal_disclosures") or []
    climate_cases = [x for x in legal if x.get("category") == "climate_litigation" and x.get("climate_related_explicit")]
    env_cases = [x for x in legal if x.get("category") in ("environmental_proceeding", "environmental_penalty")]
    if climate_cases:
        dims.append(_dim("climate_legal_risk", "Climate & environmental legal exposure", 30,
                         f"{len(climate_cases)} explicitly climate-related legal matter(s) found.",
                         [x.get("evidence_id") for x in climate_cases], MEDIUM, REPORTED))
    elif env_cases:
        dims.append(_dim("climate_legal_risk", "Climate & environmental legal exposure", 60,
                         f"{len(env_cases)} environmental proceeding(s)/penalty(ies); none explicitly climate-related.",
                         [x.get("evidence_id") for x in env_cases], MEDIUM, REPORTED))
    elif company.get("legal_reviewed"):
        dims.append(_dim("climate_legal_risk", "Climate & environmental legal exposure", 90,
                         "No climate or environmental proceedings found in the annual-report pages reviewed. "
                         "Absence of evidence is not proof of absence.", confidence=LOW, state=INFERENCE))
    else:
        dims.append(_dim("climate_legal_risk", "Climate & environmental legal exposure", None,
                         "Annual report could not be reviewed for legal disclosures."))

    valued = [x for x in kpis if x and x["current"] is not None]
    if valued:
        high = sum(1 for x in valued if x["confidence"] == HIGH)
        dc = high / len(valued) * 100
        dims.append(_dim("data_confidence", "Data confidence", dc,
                         f"{high}/{len(valued)} KPI values are High confidence (XBRL-tagged, or quote verified on the cited page).", confidence=HIGH))
    else:
        dims.append(_dim("data_confidence", "Data confidence", 0, "No KPI values could be extracted.", confidence=HIGH))

    scored = [d for d in dims if d["score"] is not None]
    data_conf = next(d for d in dims if d["key"] == "data_confidence")["score"]
    overall, grade, band, status = None, None, None, "insufficient_data"
    if len(scored) >= MIN_DIMENSIONS_FOR_GRADE and data_conf >= 50:
        wsum = sum(DIMENSION_WEIGHTS[d["key"]] for d in scored)
        overall = round(sum(d["score"] * DIMENSION_WEIGHTS[d["key"]] for d in scored) / wsum, 1)
        grade, band = next((g, b) for t, g, b in GRADES if overall >= t)
        status = "rated"
    confidence = HIGH if (data_conf >= 75 and len(scored) >= 7) else MEDIUM if data_conf >= 50 else LOW
    disclosure = next(d for d in dims if d["key"] == "disclosure_quality")
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": status,
        "overall_score": overall,
        "grade": grade,
        "band": band,
        "confidence": confidence,
        "dimensions": dims,
        "dimensions_scored": len(scored),
        "weights": DIMENSION_WEIGHTS,
        "disclosure_score": disclosure["score"],
        "note": None if status == "rated" else
            f"Overall grade withheld: {len(scored)} of {len(dims)} dimensions scored and data confidence "
            f"{data_conf:.0f}/100 (needs ≥{MIN_DIMENSIONS_FOR_GRADE} dimensions and ≥50 confidence).",
    }


def rebuild_company_intelligence(company_id):
    """Recompute KPIs + rating from stored metrics; appends a new rating version (history preserved)."""
    from services.company_agents import revalidate_stored_xbrl
    issues = revalidate_stored_xbrl(company_id)
    if issues:
        gaps = [g for g in (companies_collection.find_one({"_id": company_id}, {"data_gaps": 1}) or {}).get("data_gaps", [])
                if not g.startswith("Filing check")]
        companies_collection.update_one({"_id": company_id}, {"$set": {"data_gaps": gaps + [f"Filing check — {i}" for i in issues]}})
    company = companies_collection.find_one({"_id": company_id})
    from services.sbti import lookup as sbti_lookup
    try:
        company["sbti"] = sbti_lookup((company.get("listing") or {}).get("isin"), company.get("legal_name") or company.get("name"))
    except Exception:  # dashboard unreachable — keep whatever we had
        pass
    kpis, series = compute_kpis(company)
    rating = compute_rating(company, kpis)
    idx = next(i for i, x in enumerate(kpis) if x is None)
    kpis[idx] = _kpi("disclosure_score", "Climate disclosure score", "/100", "higher",
                     cur=rating["disclosure_score"], confidence=HIGH, label_state=CALCULATED,
                     note="Share of core climate disclosures found (methodology v0.1)")
    now = datetime.now(timezone.utc)
    company_ratings_collection.insert_one({"company_id": company_id, **rating, "created_at": now})
    trend = [{"period": r["period"], "total_tco2e": r["value_norm"]} for r in series["total"]]
    from services.company_pathway import compute_pathway
    pathway = compute_pathway(company, kpis, series["total"])
    companies_collection.update_one({"_id": company_id}, {"$set": {
        "kpis": kpis, "rating": {k: v for k, v in rating.items()}, "emissions_trend": trend,
        "pathway": pathway, "sbti": company.get("sbti"), "kpis_updated_at": now,
    }})
    return rating
