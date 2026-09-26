"""
Methodology knowledge base for project ratings (spec §15 Agent 2, §53) — versioned, analyst-authored.

Two layers, like Calyx's programme → methodology → project structure:
  CATEGORY_PROFILES  structural facts per project category (is reversal risk relevant, typical risk drivers)
  METHODOLOGY_NOTES  specific, cited findings about individual methodologies

Only findings with a checked public source belong in METHODOLOGY_NOTES (accessed 2026-09-26).
Everything else is phrased as a structural risk driver, never as a claim about a specific project.
"""

KB_VERSION = "Sylithe Methodology Notes v0.1"

CATEGORY_PROFILES = {
    "forest": {
        "reversal_relevant": True, "leakage_relevance": "high",
        "drivers": ["Baseline deforestation/growth assumptions drive crediting volume",
                    "Reversal risk from fire, drought, pests and land-use change; buffer pool contribution matters",
                    "Activity-shifting and market leakage for avoided-deforestation and harvest changes"],
    },
    "land-use": {
        "reversal_relevant": True, "leakage_relevance": "medium",
        "drivers": ["Soil/biomass carbon measurement uncertainty", "Reversal risk from management change"],
    },
    "agriculture": {
        "reversal_relevant": True, "leakage_relevance": "medium",
        "drivers": ["Model-based soil carbon estimates carry high uncertainty",
                    "Practice adoption and continuation must be monitored"],
    },
    "renewable-energy": {
        "reversal_relevant": False, "leakage_relevance": "low",
        "drivers": ["Additionality is the central risk: grid-connected renewables are often financially viable without carbon revenue",
                    "Baseline uses grid emission factors (combined margin)"],
    },
    "energy-efficiency": {
        "reversal_relevant": False, "leakage_relevance": "low",
        "drivers": ["Usage/adoption rates and baseline fuel-use assumptions drive crediting",
                    "Rebound effects and device stacking"],
    },
    "fuel-switching": {
        "reversal_relevant": False, "leakage_relevance": "low",
        "drivers": ["Baseline fuel assumptions and fraction of non-renewable biomass where applicable"],
    },
    "ghg-management": {
        "reversal_relevant": False, "leakage_relevance": "low",
        "drivers": ["Destruction/capture volumes are usually metered (lower quantification risk)",
                    "Additionality depends on whether regulation already requires capture"],
    },
    "biomass-cdr": {
        "reversal_relevant": True, "leakage_relevance": "medium",
        "drivers": ["Durability of stored carbon (e.g. biochar stability) and feedstock sustainability"],
    },
    "alkalinity-cdr": {"reversal_relevant": False, "leakage_relevance": "low", "drivers": ["MRV of dissolution/weathering rates"]},
    "air-capture": {"reversal_relevant": False, "leakage_relevance": "low", "drivers": ["Storage permanence and energy source lifecycle emissions"]},
    "unknown": {"reversal_relevant": None, "leakage_relevance": "unknown", "drivers": ["Project category not classified in registry data"]},
}

_ICVCM_RE = {
    "finding": "ICVCM ruled in 2024 that credits from current renewable-energy methodologies including ACM0002 and "
               "AMS-I.D will not receive the Core Carbon Principles (CCP) label, citing additionality concerns.",
    "source": "Integrity Council for the Voluntary Carbon Market (ICVCM)",
    "url": "https://icvcm.org/carbon-credits-from-current-renewable-energy-methodologies-will-not-receive-high-integrity-ccp-label/",
    "affects": ["additionality", "methodology"],
}
_COOKSTOVE = {
    "finding": "Gill-Wiehl, Kammen & Haya (2024, Nature Sustainability) estimated that a sample of cookstove offset projects "
               "was over-credited about 9.2x across five cookstove methodologies, driven by fraction of non-renewable biomass, "
               "stove adoption/usage, fuel consumption and stacking assumptions. Only Gold Standard's separate metered & "
               "measured methodology came close to their estimates (about 1.5x). This finding applies to this project's "
               "methodology as a class-level risk; this methodology is NOT the metered & measured one.",
    "source": "Nature Sustainability (2024) 'Pervasive over-crediting from cookstove offset methodologies'",
    "url": "https://www.nature.com/articles/s41893-023-01259-6",
    "affects": ["baseline", "monitoring", "methodology"],
}
_REDD = {
    "finding": "West et al. (2023, Science) found that most sampled voluntary REDD+ projects did not significantly reduce "
               "deforestation relative to synthetic controls, and that ex-ante baselines tended to be overstated.",
    "source": "Science (2023) 'Action needed to make carbon offsets from forest conservation work for climate change mitigation'",
    "url": "https://www.science.org/doi/10.1126/science.ade3535",
    "affects": ["baseline", "additionality", "methodology"],
}

METHODOLOGY_NOTES = {
    "acm0002": [_ICVCM_RE],
    "ams-i-d": [_ICVCM_RE],
    "gs-tpddtec": [_COOKSTOVE],
    "gs-kitchen-cookstoves": [_COOKSTOVE],
    "ams-ii-g": [_COOKSTOVE],
    "vmr0006": [_COOKSTOVE],
    "vm0007": [_REDD],
    "vm0009": [_REDD],
    "vm0015": [_REDD],
    "vm0006": [_REDD],
    "vm0048": [{
        "finding": "ICVCM approved Verra's consolidated REDD+ methodology VM0048 as meeting the Core Carbon Principles.",
        "source": "ICVCM — 'Integrity Council approves three REDD+ methodologies'",
        "url": "https://icvcm.org/integrity-council-approves-three-redd-methodologies/",
        "affects": ["methodology", "baseline"],
    }],
    "vm0047": [{
        "finding": "ICVCM approved Verra's ARR methodology VM0047 (v1.0 and v1.1) as meeting the Core Carbon Principles.",
        "source": "Verra — 'ICVCM approves updated version of Verra's ARR methodology'",
        "url": "https://verra.org/icvcm-approves-updated-version-of-verras-afforestation-reforestation-and-revegetation-methodology/",
        "affects": ["methodology"],
    }],
}


def profile_for(category):
    return CATEGORY_PROFILES.get(category or "unknown", CATEGORY_PROFILES["unknown"])


def notes_for(protocols):
    out = []
    seen = set()
    for p in protocols or []:
        for n in METHODOLOGY_NOTES.get(p.lower(), []):
            if n["url"] not in seen:
                seen.add(n["url"])
                out.append({**n, "protocol": p})
    return out
