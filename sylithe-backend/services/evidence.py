"""
Common evidence layer (spec §29–30, §52) shared by company and project agents.

Every stored fact carries: value, unit, period, source document, url, page,
verbatim quote, how it was obtained, a data label and a confidence level.
"""
import hashlib
from datetime import datetime, timezone

from db import evidence_collection

# Spec §52 labels
REPORTED = "Reported"
CALCULATED = "Calculated"
ESTIMATED = "Estimated"
MODEL_ESTIMATE = "Model estimate"
INFERENCE = "Inference"
NOT_FOUND = "Data not found"

# Spec §30 confidence
HIGH, MEDIUM, LOW = "High", "Medium", "Low"


def evidence_id(subject_id, url, page, quote):
    h = hashlib.sha256(f"{subject_id}|{url}|{page}|{quote}".encode()).hexdigest()[:16]
    return f"ev_{h}"


def save_evidence(subject_type, subject_id, *, claim, quote, source_title, url, page=None,
                  document_id=None, value=None, unit=None, period=None, label=REPORTED,
                  confidence=HIGH, verified=True, method="document_extraction", agent=None):
    eid = evidence_id(subject_id, url, page, quote or claim)
    doc = {
        "evidence_id": eid,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "claim": claim,
        "quote": quote,
        "value": value,
        "unit": unit,
        "period": period,
        "source_title": source_title,
        "url": url,
        "page": page,
        "document_id": document_id,
        "label": label,
        "confidence": confidence,
        "verified": verified,
        "extraction_method": method,
        "agent": agent,
        "retrieved_at": datetime.now(timezone.utc),
    }
    evidence_collection.update_one({"evidence_id": eid}, {"$set": doc}, upsert=True)
    return eid


def get_evidence(ids):
    if not ids:
        return {}
    return {e["evidence_id"]: e for e in evidence_collection.find({"evidence_id": {"$in": list(ids)}}, {"_id": 0})}


# ---- JSON-schema helpers for strict agent tools ----

def obj(props, required=None):
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


def arr(items):
    return {"type": "array", "items": items}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


STR = {"type": "string"}
NUM = {"type": "number"}
INT = {"type": "integer"}
BOOL = {"type": "boolean"}


def enum(*values):
    return {"type": "string", "enum": list(values)}
