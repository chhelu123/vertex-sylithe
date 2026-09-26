"""
Background jobs for long agent pipelines.

Pipelines run in a daemon thread so the HTTP request returns immediately;
progress lives in Mongo (`jobs`) so any gunicorn worker can answer polling.
"""
import logging
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

from db import jobs_collection

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


class Job:
    def __init__(self, job_id):
        self.id = job_id

    def step(self, key, label, status="running", detail=None):
        """Create or update a named pipeline step (shown live in the UI)."""
        entry = {"key": key, "label": label, "status": status, "detail": detail, "updated_at": _now()}
        res = jobs_collection.update_one(
            {"_id": self.id, "steps.key": key},
            {"$set": {"steps.$": entry, "updated_at": _now()}},
        )
        if res.matched_count == 0:
            jobs_collection.update_one({"_id": self.id}, {"$push": {"steps": entry}, "$set": {"updated_at": _now()}})

    def add_cost(self, usd):
        jobs_collection.update_one({"_id": self.id}, {"$inc": {"cost_usd": usd}})


STALE_AFTER = timedelta(minutes=20)


def active_job(subject_type, subject_id, kind):
    # a job whose worker died (restart/deploy) stops updating — mark it failed so it can be re-run
    jobs_collection.update_many(
        {"status": "running", "updated_at": {"$lt": _now() - STALE_AFTER}},
        {"$set": {"status": "failed", "error": "worker stopped before the job finished"}},
    )
    return jobs_collection.find_one(
        {"subject_type": subject_type, "subject_id": subject_id, "kind": kind, "status": "running"},
        sort=[("created_at", -1)],
    )


def start_job(kind, subject_type, subject_id, fn, *args, requested_by=None):
    """Run fn(job, *args) in the background. Returns the job id (reuses a running one)."""
    running = active_job(subject_type, subject_id, kind)
    if running:
        return running["_id"]
    job_id = uuid.uuid4().hex
    try:
        jobs_collection.insert_one({
            "_id": job_id, "kind": kind, "subject_type": subject_type, "subject_id": subject_id,
            "status": "running", "steps": [], "cost_usd": 0.0, "result": None, "error": None,
            "requested_by": requested_by, "created_at": _now(), "updated_at": _now(),
        })
    except DuplicateKeyError:
        # another request started the same job a moment ago (unique index on running jobs)
        return active_job(subject_type, subject_id, kind)["_id"]

    def runner():
        job = Job(job_id)
        try:
            result = fn(job, *args)
            jobs_collection.update_one({"_id": job_id}, {"$set": {"status": "done", "result": result, "updated_at": _now()}})
        except Exception as e:
            logger.error(f"job {kind} {subject_id} failed: {e}\n{traceback.format_exc()}")
            jobs_collection.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": str(e), "updated_at": _now()}})

    threading.Thread(target=runner, daemon=True, name=f"job-{kind}-{job_id[:8]}").start()
    return job_id


def get_job(job_id):
    job = jobs_collection.find_one({"_id": job_id})
    if not job:
        return None
    job["id"] = job.pop("_id")
    return job
