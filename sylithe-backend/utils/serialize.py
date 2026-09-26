"""JSON-safe conversion for Mongo documents (ObjectId, datetime)."""
from datetime import datetime

from bson import ObjectId


def clean(value):
    if isinstance(value, dict):
        return {("id" if k == "_id" else k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
