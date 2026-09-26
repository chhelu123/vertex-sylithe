# services/gee_init.py
#
# Shared Earth Engine initialiser. Works both locally (file path) and on
# hosted platforms like Render (where you provide the service-account JSON
# as an environment variable instead of a file on disk).
#
# Credential sources, in priority order:
#   1. GEE_SERVICE_ACCOUNT_JSON  — full JSON key as a string (best for Render)
#   2. GEE_SERVICE_ACCOUNT_PATH  — path to a JSON key file
#   3. GOOGLE_APPLICATION_CREDENTIALS — path to a JSON key file

import ee
import os
import json
import tempfile

_GEE_INITIALIZED = False
_KEY_FILE = None  # resolved on-disk path to the key (may be a temp file)


def _resolve_key_file():
    """Return a path to a service-account JSON key file, materialising the
    GEE_SERVICE_ACCOUNT_JSON env var to a temp file if needed."""
    global _KEY_FILE
    if _KEY_FILE and os.path.exists(_KEY_FILE):
        return _KEY_FILE

    raw = os.environ.get('GEE_SERVICE_ACCOUNT_JSON')
    if raw:
        try:
            json.loads(raw)  # validate
            tf = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
            tf.write(raw)
            tf.close()
            _KEY_FILE = tf.name
            return _KEY_FILE
        except Exception as e:
            print(f"[gee] GEE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}")

    path = os.environ.get('GEE_SERVICE_ACCOUNT_PATH') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if path:
        path = os.path.abspath(path)
        if os.path.exists(path):
            _KEY_FILE = path
            return _KEY_FILE
        print(f"[gee] credential file not found at {path}")
    return None


def init_gee():
    """Initialise Earth Engine. Returns True on success, False otherwise.
    Safe to call repeatedly (no-op once initialised)."""
    global _GEE_INITIALIZED
    if _GEE_INITIALIZED:
        return True
    try:
        key_path = _resolve_key_file()
        if key_path:
            with open(key_path, 'r', encoding='utf-8') as f:
                sa = json.load(f)
            ee.Initialize(
                ee.ServiceAccountCredentials(sa['client_email'], key_path),
                project=sa.get('project_id'),
            )
            print(f"[gee] initialized as {sa['client_email']}")
        else:
            # Last resort — relies on a default project being configured.
            ee.Initialize()
            print("[gee] initialized with default credentials")
        _GEE_INITIALIZED = True
        return True
    except Exception as e:
        print(f"[gee] Earth Engine initialization failed: {e}")
        return False


def is_ready():
    return _GEE_INITIALIZED
