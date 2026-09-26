"""Gunicorn config — auto-loaded when gunicorn starts in this directory.

The Sylithe AI report analysis uses deepseek-v4-pro (a reasoning model) which
can take ~60–90s per request. The gunicorn default worker timeout is 30s, so
without this the request is killed and the report falls back to static text.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "180"))
graceful_timeout = 180
keepalive = 5
