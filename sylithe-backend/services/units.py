"""Unit normalisation for disclosed metrics (deterministic, no LLM)."""
import re

# canonical unit per metric family
CANONICAL = {
    "emissions": "tCO2e",
    "energy": "GJ",
    "water": "kL",
    "waste": "t",
    "money_inr": "INR crore",
    "percent": "%",
}

_EMISSIONS = {"tco2e": 1, "tco2": 1, "t": 1, "tonnes": 1, "tonne": 1, "metric tonnes": 1,
              "ktco2e": 1e3, "kt": 1e3, "thousand tonnes": 1e3,
              # "MT"/"MTCO2e" is ambiguous in Indian filings (metric vs million tonnes) — the extraction
              # agent is told to write units explicitly, so only unambiguous spellings are mapped here.
              "million tco2e": 1e6, "million tonnes": 1e6, "million tonnes co2e": 1e6,
              "lakh tco2e": 1e5, "metric tonnes co2e": 1, "tonnes co2e": 1,
              "kgco2e": 1e-3, "kg": 1e-3}
_ENERGY = {"gj": 1, "gigajoule": 1, "gigajoules": 1, "tj": 1e3, "terajoule": 1e3, "terajoules": 1e3, "pj": 1e6,
           "mj": 1e-3, "mwh": 3.6, "gwh": 3600, "kwh": 0.0036, "million gj": 1e6, "lakh gj": 1e5, "crore gj": 1e7}
_WATER = {"kl": 1, "kilolitre": 1, "kilolitres": 1, "kiloliter": 1, "kiloliters": 1, "m3": 1, "m³": 1, "cubic metre": 1,
          "ml": 1e3, "megalitre": 1e3, "megalitres": 1e3, "million litres": 1e3, "litres": 1e-3, "liters": 1e-3,
          "lakh kl": 1e5, "million kl": 1e6, "million m3": 1e6, "crore kl": 1e7}
_WASTE = {"t": 1, "tonnes": 1, "tonne": 1, "mt": 1, "metric tonnes": 1, "kg": 1e-3, "kt": 1e3, "thousand tonnes": 1e3,
          "lakh tonnes": 1e5, "million tonnes": 1e6}
_INR = {"inr crore": 1, "₹ crore": 1, "rs crore": 1, "crore": 1, "cr": 1, "₹ cr": 1, "rs. crore": 1,
        "inr lakh": 0.01, "₹ lakh": 0.01, "lakh": 0.01, "rs lakh": 0.01,
        "inr million": 0.1, "₹ million": 0.1, "inr mn": 0.1, "million inr": 0.1,
        "inr billion": 100, "₹ billion": 100, "inr bn": 100,
        "inr": 1e-7, "₹": 1e-7, "rs": 1e-7}

FAMILY = {
    "scope1_tco2e": "emissions", "scope2_tco2e": "emissions", "scope2_location_tco2e": "emissions", "scope2_market_tco2e": "emissions",
    "scope3_tco2e": "emissions",
    "total_energy_gj": "energy", "renewable_energy_gj": "energy", "electricity_consumption_gj": "energy",
    "water_withdrawal_kl": "water", "water_consumption_kl": "water",
    "waste_generated_t": "waste", "waste_recovered_t": "waste",
    "revenue_inr_cr": "money_inr", "ebitda_inr_cr": "money_inr", "pat_inr_cr": "money_inr", "capex_inr_cr": "money_inr",
    "environmental_capex_inr_cr": "money_inr", "sustainability_expenditure_inr_cr": "money_inr",
    "csr_spend_inr_cr": "money_inr", "legal_professional_fees_inr_cr": "money_inr",
    "carbon_credit_spend_inr_cr": "money_inr", "renewable_investment_inr_cr": "money_inr",
    "environmental_penalties_inr_cr": "money_inr",
    "renewable_energy_pct": "percent", "waste_recovery_pct": "percent",
}
_TABLES = {"emissions": _EMISSIONS, "energy": _ENERGY, "water": _WATER, "waste": _WASTE, "money_inr": _INR}


def _clean(unit):
    u = (unit or "").lower().replace("co₂", "co2").replace("per annum", "").replace("(", " ").replace(")", " ")
    u = re.sub(r"\s+", " ", u).strip().strip(".")
    return u


def normalise(metric, value, unit):
    """
    Convert a disclosed value to the metric's canonical unit.
    Returns (value, canonical_unit, converted: bool). Unknown units are returned unchanged
    so nothing is silently mis-scaled.
    """
    family = FAMILY.get(metric)
    if value is None or family is None:
        return value, unit, False
    if family == "percent":
        return value, "%", False
    canon = CANONICAL[family]
    table = _TABLES[family]
    u = _clean(unit)
    if u in table:
        return round(value * table[u], 4), canon, table[u] != 1
    # try progressively: strip trailing words like 'co2e', 'e'
    for key in sorted(table, key=len, reverse=True):
        if u.startswith(key + " ") or u == key:
            return round(value * table[key], 4), canon, table[key] != 1
    return value, unit, False
