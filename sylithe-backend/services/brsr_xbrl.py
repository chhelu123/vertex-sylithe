"""
BRSR XBRL parser (SEBI `in-capmkt` taxonomy) — deterministic, zero LLM tokens.

Each tagged fact becomes a metric with the XBRL element as its evidence pointer,
so Scope 1/2, energy, water and waste values are exact ("Reported", High confidence).

Unit note: the SEBI taxonomy's unit `Non-SI:MtCO2e` denotes *metric tonnes* of CO2e
(e.g. Reliance FY2025-26 Scope 1 = 36,350,070), not million tonnes.
"""
import re
import xml.etree.ElementTree as ET

NS_XBRLI = "http://www.xbrl.org/2003/instance"

# element → (metric, scale, canonical unit). Scale converts per-INR intensities to per ₹ crore
# and INR amounts to ₹ crore for readability.
FACT_MAP = {
    "TotalScope1Emissions": ("scope1_tco2e", 1, "tCO2e"),
    "TotalScope2Emissions": ("scope2_tco2e", 1, "tCO2e"),
    "TotalScope3Emissions": ("scope3_tco2e", 1, "tCO2e"),
    "TotalScope1AndScope2EmissionsIntensityPerRupeeOfTurnover": ("emissions_intensity_revenue", 1e7, "tCO2e per ₹ crore revenue"),
    "TotalScope1AndScope2EmissionsIntensityInTermOfPhysicalOutput": ("emissions_intensity_physical", 1, "tCO2e per unit output (as reported)"),
    "TotalEnergyConsumedFromRenewableAndNonRenewableSources": ("total_energy_gj", 1, "GJ"),
    "TotalEnergyConsumedFromRenewableSources": ("renewable_energy_gj", 1, "GJ"),
    "EnergyIntensityPerRupeeOfTurnover": ("energy_intensity_revenue", 1e7, "GJ per ₹ crore revenue"),
    "TotalVolumeOfWaterWithdrawal": ("water_withdrawal_kl", 1, "kL"),
    "TotalVolumeOfWaterConsumption": ("water_consumption_kl", 1, "kL"),
    "WaterIntensityPerRupeeOfTurnover": ("water_intensity_revenue", 1e7, "kL per ₹ crore revenue"),
    "TotalWasteGenerated": ("waste_generated_t", 1, "t"),
    "TotalWasteRecovered": ("waste_recovered_t", 1, "t"),
    "RevenueFromOperations": ("revenue_inr_cr", 1e-7, "INR crore"),
}
ELECTRICITY_PARTS = ("TotalElectricityConsumptionFromRenewableSources", "TotalElectricityConsumptionFromNonRenewableSources")

PROFILE_TAGS = {
    "NameOfTheCompany": "name", "CorporateIdentityNumber": "cin", "WebsiteOfCompany": "website",
    "AddressOfRegisteredOfficeOfCompany": "registered_office", "AddressOfCorporateOfficeOfCompany": "corporate_office",
    "ReportingBoundary": "reporting_boundary", "DateOfEndOfFinancialYear": "fy_end",
}
ASSURANCE_TAG = "NameOfTheExternalAgencyThatUndertookIndependentAssessmentOrEvaluationOrAssuranceForGreenHouseGasEmissionsExplanatoryTextBlock"
ASSURED_FLAG = "WhetherAnyIndicateIfAnyIndependentAssessmentOrEvaluationOrAssuranceHasBeenCarriedOutByAnExternalAgencyForGreenHouseGasEmissions"


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _period_label(start, end):
    """2025-04-01..2026-03-31 → FY2025-26 (Indian FY); otherwise CYyyyy."""
    if start and end and start[5:10] == "04-01" and end[5:10] == "03-31":
        return f"FY{start[:4]}-{end[2:4]}"
    return f"CY{end[:4]}" if end else None


def parse(xml_bytes):
    """Returns {"profile": {...}, "facts": [ {metric, value, unit, period, element, context, raw} ], "activities": [...]}"""
    root = ET.fromstring(xml_bytes)
    contexts = {}
    for ctx in root.iter(f"{{{NS_XBRLI}}}context"):
        cid = ctx.get("id")
        has_dim = ctx.find(f".//{{{NS_XBRLI}}}scenario") is not None
        start = ctx.findtext(f".//{{{NS_XBRLI}}}startDate")
        end = ctx.findtext(f".//{{{NS_XBRLI}}}endDate") or ctx.findtext(f".//{{{NS_XBRLI}}}instant")
        contexts[cid] = {"period": _period_label(start, end), "dimensional": has_dim}

    profile, facts, activities = {}, [], []
    elec = {}
    for el in root:
        name = _local(el.tag)
        text = (el.text or "").strip()
        ctx = contexts.get(el.get("contextRef") or "", {})
        if name in PROFILE_TAGS and text and not ctx.get("dimensional"):
            profile.setdefault(PROFILE_TAGS[name], text)
        elif name == ASSURANCE_TAG and text:
            profile["ghg_assurance_text"] = text[:600]
        elif name == ASSURED_FLAG and text:
            profile["ghg_assured"] = text.lower() == "true"
        elif name == "DescriptionOfMainActivity" and text:
            activities.append(text)
        if not text or ctx.get("dimensional") or not ctx.get("period"):
            continue
        if name in FACT_MAP:
            metric, scale, unit = FACT_MAP[name]
            try:
                raw_value = float(text)
            except ValueError:
                continue
            facts.append({
                "metric": metric, "value": round(raw_value * scale, 6), "unit": unit, "period": ctx["period"],
                "element": f"in-capmkt:{name}", "context": el.get("contextRef"), "unit_ref": el.get("unitRef"),
                "raw": f'<in-capmkt:{name} contextRef="{el.get("contextRef")}" unitRef="{el.get("unitRef")}">{text}</in-capmkt:{name}>',
            })
        elif name in ELECTRICITY_PARTS:
            try:
                elec.setdefault(ctx["period"], []).append((name, float(text), el.get("contextRef")))
            except ValueError:
                pass
    for period, parts in elec.items():
        if len(parts) == 2:
            facts.append({
                "metric": "electricity_consumption_gj", "value": parts[0][1] + parts[1][1], "unit": "GJ",
                "period": period, "element": " + ".join(f"in-capmkt:{p[0]}" for p in parts), "context": parts[0][2],
                "unit_ref": "Gigajoule", "calculated": True,
                "raw": " + ".join(f"{p[0]}={p[1]:g}" for p in parts),
            })
    profile["activities"] = list(dict.fromkeys(re.sub(r"\s+", " ", a) for a in activities))[:6]
    return {"profile": profile, "facts": facts}
