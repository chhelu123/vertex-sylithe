"""
Emission factors for the company carbon calculator (Scope 1 fuels, Scope 2 electricity).

Versioned and cited. Calculations are deterministic code; the LLM only extracts activity data.
Scope 1 factors are CO2-only IPCC 2006 defaults (CH4/N2O excluded, ~<1% for most stationary fuels) —
results are labelled "Estimated". Company-specific fuel NCVs should replace defaults where known.
"""

FACTORS_VERSION = "Sylithe EF set v0.1 (2026-09)"

IPCC_2006 = {
    "source": "2006 IPCC Guidelines for National GHG Inventories, Vol. 2 Energy, Ch. 1, Tables 1.2 (NCV) and 1.4 (CO2 EF)",
    "url": "https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf",
}
CEA_V21 = {
    "source": "Central Electricity Authority, CO2 Baseline Database for the Indian Power Sector, Version 21.0 (FY 2024-25)",
    "url": "https://cea.nic.in/wp-content/uploads/baseline/2025/12/User_Guide_V_21.0.pdf",
}

# fuel → (kg CO2 per TJ, NCV TJ per Gg (= GJ per t), density kg/L or None)
FUELS = {
    "diesel":      {"label": "Diesel / gas oil",        "ef_kg_tj": 74100, "ncv_gj_t": 43.0, "density": 0.832},
    "petrol":      {"label": "Petrol / motor gasoline", "ef_kg_tj": 69300, "ncv_gj_t": 44.3, "density": 0.745},
    "lpg":         {"label": "LPG",                     "ef_kg_tj": 63100, "ncv_gj_t": 47.3, "density": None},
    "natural_gas": {"label": "Natural gas",             "ef_kg_tj": 56100, "ncv_gj_t": 48.0, "density": None},
    "coal":        {"label": "Coal (other bituminous)", "ef_kg_tj": 94600, "ncv_gj_t": 25.8, "density": None},
    "fuel_oil":    {"label": "Residual fuel oil",       "ef_kg_tj": 77400, "ncv_gj_t": 40.4, "density": 0.94},
    "kerosene":    {"label": "Kerosene",                "ef_kg_tj": 71900, "ncv_gj_t": 43.8, "density": 0.80},
}
DENSITY_NOTE = "Litre→kg uses typical densities (assumption; replace with supplier density where available)."

GRID_EF_T_PER_MWH = 0.710  # CEA V21.0 all-India weighted average, FY2024-25

ACTIVITY_TYPES = ["electricity_grid", "electricity_renewable"] + list(FUELS)

_MASS = {"kg": 1e-3, "kgs": 1e-3, "t": 1, "tonne": 1, "tonnes": 1, "mt": 1, "metric tonnes": 1}
_ENERGY_GJ = {"gj": 1, "tj": 1000, "mj": 1e-3, "mmbtu": 1.055056}
_VOLUME_L = {"l": 1, "litre": 1, "litres": 1, "liter": 1, "liters": 1, "kl": 1000, "kilolitre": 1000, "kilolitres": 1000}
_ELEC_MWH = {"kwh": 1e-3, "mwh": 1, "gwh": 1000, "units": 1e-3}


class FactorError(Exception):
    pass


def calculate_line(activity_type, quantity, unit):
    """Returns dict with scope, tco2e, factor description, source — or raises FactorError."""
    u = (unit or "").strip().lower()
    if activity_type in ("electricity_grid", "electricity_renewable"):
        if u not in _ELEC_MWH:
            raise FactorError(f"unit '{unit}' not supported for electricity (use kWh, MWh, GWh)")
        mwh = quantity * _ELEC_MWH[u]
        if activity_type == "electricity_renewable":
            return {"scope": "Scope 2", "tco2e": 0.0, "mwh": mwh,
                    "factor": "0 tCO2/MWh (market-based, only with contractual instruments e.g. RECs/PPAs)",
                    "source": "GHG Protocol Scope 2 Guidance — market-based method",
                    "url": "https://ghgprotocol.org/scope-2-guidance"}
        return {"scope": "Scope 2", "tco2e": round(mwh * GRID_EF_T_PER_MWH, 4), "mwh": mwh,
                "factor": f"{GRID_EF_T_PER_MWH} tCO2/MWh (location-based)", **CEA_V21}
    f = FUELS.get(activity_type)
    if not f:
        raise FactorError(f"unknown activity type '{activity_type}'")
    if u in _ENERGY_GJ:
        gj = quantity * _ENERGY_GJ[u]
        note = ""
    elif u in _MASS:
        gj = quantity * _MASS[u] * f["ncv_gj_t"]
        note = f"NCV {f['ncv_gj_t']} GJ/t"
    elif u in _VOLUME_L and f["density"]:
        gj = quantity * _VOLUME_L[u] * f["density"] / 1000 * f["ncv_gj_t"]
        note = f"density {f['density']} kg/L, NCV {f['ncv_gj_t']} GJ/t. {DENSITY_NOTE}"
    else:
        raise FactorError(f"unit '{unit}' not supported for {f['label']}")
    tco2 = gj * f["ef_kg_tj"] / 1e6  # (GJ / 1000 → TJ) × kg/TJ, then kg / 1000 → t
    return {"scope": "Scope 1", "tco2e": round(tco2, 4), "gj": round(gj, 3),
            "factor": f"{f['ef_kg_tj']:,} kg CO2/TJ ({f['label']}). {note}".strip(), **IPCC_2006}
