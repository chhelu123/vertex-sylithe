"""
Emissions pathway & carbon suggestion for a company (deterministic, no LLM).

For Scope 1+2 it answers:
  1. How much is the company emitting?          (disclosed, per period)
  2. How much should it emit?                     (1.5°C-aligned pathway, and its own target where computable)
  3. What is the gap, and what should it do?      (reduction levers from its own data + matched carbon projects
                                                   for residual / beyond-value-chain action)

Benchmark: SBTi absolute contraction approach — a minimum 4.2% linear annual reduction of Scope 1+2 from the
base year for 1.5°C alignment; long-term net zero means ≥90% reduction by 2050 at the latest.
Carbon credits never count toward these reduction targets; they are suggested only for residual emissions and
beyond-value-chain mitigation.
"""
from db import registry_projects_collection
from services.methodology_kb import METHODOLOGY_NOTES

PATHWAY_VERSION = "Sylithe Emissions Pathway v0.1"
ACA_RATE_1_5C = 0.042          # per year, linear from base year (Scope 1+2)
NET_ZERO_MIN_REDUCTION = 0.90  # long-term: at least 90% below base year
NET_ZERO_LATEST = 2050
SOURCES = [
    {"title": "SBTi Corporate Near-Term Criteria (1.5°C: ≥4.2% linear annual reduction, Scope 1+2)",
     "url": "https://sciencebasedtargets.org/resources/files/SBTi-criteria.pdf"},
    {"title": "SBTi Target Dashboard (company commitment & target status, updated weekly)",
     "url": "https://sciencebasedtargets.org/target-dashboard"},
    {"title": "SBTi Corporate Net-Zero Standard (≥90% reduction by 2050; credits do not count toward targets)",
     "url": "https://sciencebasedtargets.org/resources/files/Net-Zero-Standard.pdf"},
]

# Credits suggested for residual emissions: removals first, then high-integrity avoidance.
REMOVAL_CATEGORIES = ["forest", "biomass-cdr", "agriculture", "land-use", "alkalinity-cdr", "air-capture"]
AVOIDANCE_CATEGORIES = ["ghg-management", "fuel-switching", "energy-efficiency"]
# Methodologies with cited class-level integrity concerns in the knowledge base are not suggested.
_FLAGGED = {p for p, notes in METHODOLOGY_NOTES.items()
            if any("will not receive" in n["finding"] or "over-credited" in n["finding"] or "did not significantly" in n["finding"]
                   for n in notes)}
_GOOD_GRADES = {"AAA", "AA", "A", "BBB"}


def _year(period):
    """FY2025-26 → 2026 (fiscal year end), CY2025 → 2025."""
    if not period:
        return None
    p = str(period)
    if p.startswith("FY") and "-" in p:
        return int(p[2:6]) + 1
    if p.startswith("CY"):
        return int(p[2:6])
    return None


def _target_path(targets, base_year, base_value):
    """Linear path implied by the company's own target, when base and target can be resolved."""
    for t in targets or []:
        ty = t.get("target_year")
        try:
            ty = int(str(ty)[:4]) if ty else None
        except ValueError:
            ty = None
        if not ty or ty <= base_year:
            continue
        if t.get("type") in ("net_zero", "carbon_neutral"):
            end_value = base_value * (1 - NET_ZERO_MIN_REDUCTION)
            label = f"Company target: {t['type'].replace('_', ' ')} by {ty} (≥90% cut assumed)"
        elif t.get("type") == "emissions_reduction" and t.get("target_value") is not None and "%" in (t.get("target_unit") or ""):
            end_value = base_value * (1 - float(t["target_value"]) / 100)
            label = f"Company target: −{t['target_value']}% by {ty}"
        else:
            continue
        slope = (end_value - base_value) / (ty - base_year)
        return {"label": label, "target_year": ty, "end_value": end_value,
                "fn": (lambda y, s=slope, e=end_value, t=ty: e if y >= t else max(0.0, base_value + s * (y - base_year))),
                "evidence_id": t.get("evidence_id"), "assumption": "Linear path from the latest disclosed base period"}
    return None


def _sbti_path(sbti, actual_by_year):
    """Path from an SBTi-validated Scope 1+2 near-term target, when base-year emissions are disclosed."""
    t = (sbti or {}).get("scope12_near_term")
    if not t or "validated" not in (sbti.get("near_term_status") or "").lower():
        return None, None
    info = {"label": f"SBTi-validated: −{t['reduction_pct']:g}% Scope 1+2 by {t['target_year']} from {t['base_year']}",
            "wording": t["wording"], "target_year": t["target_year"], "base_year": t["base_year"],
            "reduction_pct": t["reduction_pct"], "source": sbti.get("source")}
    base_value = actual_by_year.get(t["base_year"])
    if base_value is None:
        info["note"] = (f"Base-year ({t['base_year']}) emissions are not in the filings Sylithe has read, "
                        "so the target line cannot be drawn in tonnes.")
        return None, info
    end_value = base_value * (1 - t["reduction_pct"] / 100)
    slope = (end_value - base_value) / (t["target_year"] - t["base_year"])
    fn = lambda y: end_value if y >= t["target_year"] else base_value + slope * (y - t["base_year"])
    return {"label": info["label"], "target_year": t["target_year"], "end_value": end_value, "fn": fn,
            "evidence_id": None, "assumption": "SBTi target applied to disclosed base-year emissions"}, info


def _levers(kpis, sbti=None):
    """Reduction levers ranked from the company's own disclosed profile."""
    k = {x["key"]: x for x in kpis if x}
    out = []
    status = (sbti or {}).get("near_term_status")
    if status and "removed" in status.lower():
        out.append({"lever": "Renew the SBTi commitment and submit targets for validation",
                    "why": f"The SBTi dashboard lists the company as '{status}'"
                           + (f" ({sbti.get('status_reason')})." if sbti.get("status_reason") else "."),
                    "addresses": "Governance"})
    elif not status:
        out.append({"lever": "Commit to the Science Based Targets initiative",
                    "why": "The company does not appear on the SBTi Target Dashboard.", "addresses": "Governance"})
    s1, s2 = k.get("scope1", {}).get("current"), k.get("scope2", {}).get("current")
    re_pct = k.get("renewable_pct", {}).get("current")
    total = (s1 or 0) + (s2 or 0)
    if s2 and total and s2 / total >= 0.2 and (re_pct is None or re_pct < 60):
        out.append({"lever": "Renewable electricity (PPAs, open access, on-site solar)",
                    "why": f"Scope 2 is {s2 / total:.0%} of Scope 1+2 and renewables supply "
                           f"{'an undisclosed share' if re_pct is None else f'{re_pct:.0f}%'} of energy.",
                    "addresses": "Scope 2"})
    if re_pct is not None and re_pct < 25:
        out.append({"lever": "Raise the renewable share of total energy",
                    "why": f"Renewables are only {re_pct:.1f}% of energy consumption.", "addresses": "Scope 1 & 2"})
    if s1 and total and s1 / total >= 0.6:
        out.append({"lever": "Fuel switching & process efficiency in direct operations",
                    "why": f"Scope 1 (fuel combustion and process emissions) is {s1 / total:.0%} of Scope 1+2.",
                    "addresses": "Scope 1"})
    ch = k.get("total_emissions", {}).get("change_pct")
    if ch is not None and ch > 0:
        out.append({"lever": "Set an interim absolute-reduction target with a base year",
                    "why": f"Scope 1+2 rose {ch:+.1f}% in the latest year; a dated, base-year target makes progress measurable.",
                    "addresses": "Governance"})
    if k.get("scope3", {}).get("current") is None:
        out.append({"lever": "Measure and disclose Scope 3",
                    "why": "Scope 3 is not disclosed; for most companies it is the largest share of the footprint.",
                    "addresses": "Scope 3"})
    return out


def match_projects(country, quantity, limit=5):
    """
    Registry projects that could cover `quantity` tCO2e of residual emissions:
    same country first, removals before avoidance, flagged methodologies excluded,
    Sylithe-rated projects (≥ BBB) ranked first, then by credits still unretired.
    """
    if not quantity or quantity <= 0:
        return []
    fields = {"_id": 0, "project_id": 1, "name": 1, "category": 1, "country": 1, "registry": 1, "protocol": 1,
              "issued": 1, "retired": 1, "latest_rating": 1, "proponent": 1, "last_issuance_at": 1}
    results = []
    for categories, kind in ((REMOVAL_CATEGORIES, "removal"), (AVOIDANCE_CATEGORIES, "avoidance")):
        q = {"category": {"$in": categories}, "issued": {"$gt": 0}, "status": {"$nin": ["canceled", "inactive"]}}
        if country:
            q["country"] = country
        for p in registry_projects_collection.find(q, fields).sort("issued", -1).limit(400):
            if set(x.lower() for x in p.get("protocol") or []) & _FLAGGED:
                continue
            available = (p.get("issued") or 0) - (p.get("retired") or 0)
            if available <= 0:
                continue
            r = p.get("latest_rating") or {}
            if r.get("grade") and r["grade"] not in _GOOD_GRADES:
                continue
            p.update({"kind": kind, "available": available, "covers_gap": available >= quantity,
                      "grade": r.get("grade"), "rating_confidence": r.get("confidence")})
            results.append(p)
        if len(results) >= limit * 3:
            break
    results.sort(key=lambda p: (
        0 if p["kind"] == "removal" else 1,
        0 if p["grade"] in _GOOD_GRADES else 1,
        0 if p["covers_gap"] else 1,
        -(p["available"]),
    ))
    return results[:limit]


def compute_pathway(company, kpis, total_series):
    """total_series: [{period, value_norm, ...}] of Scope 1+2 (tCO2e), oldest first."""
    series = [(r["period"], _year(r["period"]), r["value_norm"]) for r in total_series if _year(r["period"])]
    if not series:
        return {"version": PATHWAY_VERSION, "status": "insufficient_data",
                "note": "Scope 1+2 emissions were not found, so a pathway cannot be computed.", "sources": SOURCES}
    base_period, base_year, base_value = series[0]
    latest_period, latest_year, latest_value = series[-1]
    actual_by_year = {y: v for _, y, v in series}
    own, sbti_info = _sbti_path(company.get("sbti"), actual_by_year)
    if not own:
        own = _target_path(company.get("targets"), base_year, base_value)
    aca = lambda y: max(0.0, base_value * (1 - ACA_RATE_1_5C * (y - base_year)))

    rows = []
    actual = {y: v for _, y, v in series}
    horizon = sorted(set(actual) | {2030, 2035, 2040, NET_ZERO_LATEST} | ({own["target_year"]} if own else set()))
    horizon = [y for y in horizon if y >= base_year]
    for y in horizon:
        allowed = aca(y) if y < NET_ZERO_LATEST else base_value * (1 - NET_ZERO_MIN_REDUCTION)
        a = actual.get(y)
        rows.append({
            "year": y, "period": next((p for p, yy, _ in series if yy == y), None),
            "actual": a, "pathway_1_5c": round(allowed, 1),
            "company_target": round(own["fn"](y), 1) if own else None,
            "gap": round(a - allowed, 1) if a is not None else None,
            "status": None if a is None else ("on track" if a <= allowed else "above pathway"),
        })

    gap_now = latest_value - aca(latest_year)
    required_cut_2030 = latest_value - aca(2030)
    years_left = max(1, 2030 - latest_year)
    needed_rate = required_cut_2030 / latest_value / years_left if latest_value else None
    residual_2050 = base_value * (1 - NET_ZERO_MIN_REDUCTION)

    credit_need = max(gap_now, 0.0)
    matched = match_projects(company.get("country"), credit_need or residual_2050)
    return {
        "version": PATHWAY_VERSION,
        "status": "computed",
        "scope": "Scope 1+2",
        "base_period": base_period, "base_value": base_value,
        "latest_period": latest_period, "latest_value": latest_value,
        "rows": rows,
        "company_target": {k: v for k, v in (own or {}).items() if k != "fn"} or None,
        "gap_latest": round(gap_now, 1),
        "on_track": gap_now <= 0,
        "required_cut_by_2030": round(max(required_cut_2030, 0), 1),
        "required_annual_rate_to_2030": round(needed_rate * 100, 2) if needed_rate and needed_rate > 0 else 0,
        "residual_at_net_zero": round(residual_2050, 1),
        "levers": _levers(kpis, company.get("sbti")),
        "sbti": ({"status": company["sbti"].get("near_term_status"), "classification": company["sbti"].get("near_term_classification"),
                  "net_zero_status": company["sbti"].get("net_zero_status"), "net_zero_year": company["sbti"].get("net_zero_year"),
                  "status_reason": company["sbti"].get("status_reason"), "target": sbti_info,
                  "matched_by": company["sbti"].get("matched_by"), "source": company["sbti"].get("source")}
                 if company.get("sbti") else {"status": "Not on SBTi dashboard", "source": "https://sciencebasedtargets.org/target-dashboard"}),
        "credit_suggestion": {
            "quantity_tco2e": round(credit_need, 1),
            "basis": ("Current gap above the 1.5°C pathway" if credit_need > 0
                      else "On track: sized for residual emissions at net zero instead"),
            "sizing_tco2e": round(credit_need or residual_2050, 1),
            "projects": matched,
            "rule": "Credits do not count toward science-based reduction targets. Use them for residual emissions "
                    "and beyond-value-chain mitigation, after cutting emissions. Removals are preferred.",
        },
        "assumptions": [
            f"Base year = earliest disclosed Scope 1+2 period ({base_period}); SBTi recommends a base year of 2015 or later with verified data.",
            "1.5°C pathway = linear 4.2% of base-year emissions per year (SBTi absolute contraction approach).",
            "Net zero = at least 90% below base year by 2050.",
            "Matched projects exclude methodologies with cited class-level integrity concerns and Sylithe grades below BBB.",
        ],
        "sources": SOURCES,
    }
