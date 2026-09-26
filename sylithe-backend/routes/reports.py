"""
LULC report generation.

Provides Google Earth Engine thumbnail images (satellite + LULC classified)
for the free-tier LULC PDF report, and enforces a lifetime quota of
FREE_LULC_REPORTS per user.

The PDF itself is assembled client-side; this endpoint supplies the two
map images (which cannot be captured in the browser because Google + GEE
tiles taint the canvas) and the quota accounting.
"""
import base64
import threading
import urllib.request

from flask import Blueprint, request, jsonify
import ee

from utils.auth import require_auth

reports_bp = Blueprint('reports', __name__)

FREE_LULC_REPORTS = 3  # lifetime, per user

# Users exempt from the export quota (unlimited exports).
from config import UNLIMITED_EMAILS

_gee_ready = False


def _init_gee():
    global _gee_ready
    from services.gee_init import init_gee as _shared_init
    if _shared_init():
        _gee_ready = True


threading.Thread(target=_init_gee, daemon=True).start()


def _ensure_gee():
    """True if Earth Engine is usable; probes/retries if our flag is unset
    (the init thread can lose a startup race against other blueprints)."""
    global _gee_ready
    if _gee_ready:
        return True
    try:
        ee.Number(1).getInfo()
        _gee_ready = True
        return True
    except Exception:
        pass
    _init_gee()
    return _gee_ready


# ESA WorldCover class → colour (matches the dashboard LULC palette)
_WORLDCOVER_PALETTE = [
    '006400',  # 10 Trees
    'ffbb22',  # 20 Shrubland
    'ffff4c',  # 30 Grassland
    'f096ff',  # 40 Cropland
    'fa0000',  # 50 Built-up
    'b4b4b4',  # 60 Bare / sparse
    'f0f0f0',  # 70 Snow & ice
    '0064c8',  # 80 Water
    '0096a0',  # 90 Herbaceous wetland
    '00cf75',  # 95 Mangroves
    'fae6a0',  # 100 Moss & lichen
]


def _strip_z(coords):
    if not isinstance(coords, list):
        return coords
    if coords and isinstance(coords[0], (int, float)):
        return coords[:2]
    return [_strip_z(c) for c in coords]


def _to_aoi(geojson):
    t = geojson.get('type')
    if t == 'FeatureCollection':
        feats = []
        for feat in geojson.get('features', []):
            g = (feat or {}).get('geometry') or {}
            if g.get('type') and 'coordinates' in g:
                try:
                    feats.append(ee.Feature(ee.Geometry({
                        'type': g['type'], 'coordinates': _strip_z(g['coordinates'])
                    })))
                except Exception:
                    pass
        if not feats:
            raise ValueError("No valid geometries found in FeatureCollection")
        return ee.FeatureCollection(feats).geometry()
    if t == 'Feature':
        return ee.Geometry(geojson['geometry'])
    return ee.Geometry(geojson)


def _thumb_to_data_url(url):
    """Fetch a GEE thumbnail URL server-side and return a base64 data URL."""
    with urllib.request.urlopen(url, timeout=60) as resp:
        raw = resp.read()
    return "data:image/png;base64," + base64.b64encode(raw).decode('ascii')


def _build_images(geojson):
    aoi = _to_aoi(geojson)
    region = aoi.bounds()

    # 1. Satellite RGB — recent Sentinel-2 cloud-light median, clipped to AOI
    s2 = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(aoi)
        .filterDate('2023-01-01', '2025-12-31')
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        .median()
        .clip(aoi)
    )
    sat_url = s2.getThumbURL({
        'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000,
        'region': region, 'dimensions': 900, 'format': 'png',
    })

    # 2. LULC classified — ESA WorldCover, clipped to AOI
    lc = ee.ImageCollection('ESA/WorldCover/v200').first().clip(aoi)
    lulc_url = lc.getThumbURL({
        'min': 10, 'max': 100, 'palette': _WORLDCOVER_PALETTE,
        'region': region, 'dimensions': 900, 'format': 'png',
    })

    images = {
        'satellite': _thumb_to_data_url(sat_url),
        'lulc':      _thumb_to_data_url(lulc_url),
    }

    # Visualised Sentinel-2 RGB base used to blend disturbance overlays so the
    # NDVI / deforestation / fire pages always carry an attractive GEE layer.
    rgb = s2.visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)

    # 3. NDVI — Sentinel-2 vegetation index (red→green palette)
    try:
        ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI').clip(aoi)
        ndvi_url = ndvi.getThumbURL({
            'min': 0, 'max': 0.8,
            'palette': ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],
            'region': region, 'dimensions': 900, 'format': 'png',
        })
        images['ndvi'] = _thumb_to_data_url(ndvi_url)
    except Exception:
        pass

    # 4. Deforestation — Hansen tree-cover loss (red) blended over the RGB base
    try:
        hansen = ee.Image('UMD/hansen/global_forest_change_2025_v1_13').clip(aoi)
        loss = hansen.select('lossyear').gt(0).selfMask()
        loss_vis = loss.visualize(palette=['#e11d48'])
        defor_url = rgb.blend(loss_vis).getThumbURL({
            'region': region, 'dimensions': 900, 'format': 'png',
        })
        images['deforestation'] = _thumb_to_data_url(defor_url)
    except Exception:
        pass

    # 5. Fire — MODIS burned area (orange) blended over the RGB base
    try:
        burn = (ee.ImageCollection('MODIS/061/MCD64A1')
                .filterDate('2008-01-01', '2025-01-01')
                .select('BurnDate').max().clip(aoi))
        burn_vis = burn.gt(0).selfMask().visualize(palette=['#f97316'])
        fire_url = rgb.blend(burn_vis).getThumbURL({
            'region': region, 'dimensions': 900, 'format': 'png',
        })
        images['fire'] = _thumb_to_data_url(fire_url)
    except Exception:
        pass

    return images


@reports_bp.route('/free/lulc-report/quota', methods=['GET', 'OPTIONS'])
@require_auth
def lulc_report_quota():
    from db import lulc_reports_collection
    email = (request.current_user.get('email') or '').lower()
    if email in UNLIMITED_EMAILS:
        return jsonify({"status": "success", "used": 0, "limit": None, "remaining": 9999, "unlimited": True})
    used = lulc_reports_collection.count_documents({'email': email})
    return jsonify({
        "status": "success",
        "used": used,
        "limit": FREE_LULC_REPORTS,
        "remaining": max(0, FREE_LULC_REPORTS - used),
        "unlimited": False,
    })


@reports_bp.route('/free/lulc-report', methods=['POST', 'OPTIONS'])
@require_auth
def lulc_report():
    if not _ensure_gee():
        return jsonify({"status": "error", "message": "Report engine is warming up. Please try again in a moment."}), 503

    from db import lulc_reports_collection
    from datetime import datetime

    email = (request.current_user.get('email') or '').lower()
    unlimited = email in UNLIMITED_EMAILS
    used = lulc_reports_collection.count_documents({'email': email})
    if not unlimited and used >= FREE_LULC_REPORTS:
        return jsonify({
            "status": "limit_reached",
            "message": f"You've used all {FREE_LULC_REPORTS} free LULC reports.",
            "used": used, "limit": FREE_LULC_REPORTS, "remaining": 0,
        }), 429

    data = request.get_json(silent=True) or {}
    geojson = data.get('geojson')
    if not geojson:
        return jsonify({"status": "error", "message": "Missing geojson"}), 400

    try:
        images = _build_images(geojson)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to render report images: {e}"}), 500

    # Record the run (consumes one lifetime slot)
    lulc_reports_collection.insert_one({
        'email': email,
        'project_name': (data.get('project_name') or '')[:200],
        'area_ha': data.get('area_ha'),
        'created_at': datetime.utcnow(),
    })
    used += 1

    return jsonify({
        "status": "success",
        "images": images,
        "used": used,
        "limit": None if unlimited else FREE_LULC_REPORTS,
        "remaining": 9999 if unlimited else max(0, FREE_LULC_REPORTS - used),
        "unlimited": unlimited,
    })


# ── Generic free-tier feature quotas (lifetime, per user) ─────────────────────
FREE_FEATURE_LIMIT = 3  # lifetime per action, per user
FEATURE_ACTIONS = {"aoi_import", "land_assess", "land_history"}


def _usage_snapshot(email, unlimited):
    from db import feature_usage_collection
    out = {}
    for action in FEATURE_ACTIONS:
        used = 0 if unlimited else feature_usage_collection.count_documents({"email": email, "action": action})
        out[action] = {
            "used": used,
            "remaining": 9999 if unlimited else max(0, FREE_FEATURE_LIMIT - used),
        }
    return out


@reports_bp.route('/free/usage', methods=['GET', 'OPTIONS'])
@require_auth
def free_usage():
    """Lifetime usage counts for the gated free-tier actions."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    email = (request.current_user.get('email') or '').lower()
    unlimited = email in UNLIMITED_EMAILS
    return jsonify({
        "status": "success",
        "unlimited": unlimited,
        "limit": None if unlimited else FREE_FEATURE_LIMIT,
        "usage": _usage_snapshot(email, unlimited),
    })


@reports_bp.route('/free/usage/consume', methods=['POST', 'OPTIONS'])
@require_auth
def free_usage_consume():
    """Atomically consume one unit of a free-tier action. Returns 429 when the
    lifetime limit is reached so the client can block + prompt to Request."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    from datetime import datetime, timezone
    from db import feature_usage_collection
    email = (request.current_user.get('email') or '').lower()
    action = ((request.get_json(silent=True) or {}).get('action') or '').strip()
    if action not in FEATURE_ACTIONS:
        return jsonify({"status": "error", "message": "Unknown action"}), 400

    unlimited = email in UNLIMITED_EMAILS
    used = 0 if unlimited else feature_usage_collection.count_documents({"email": email, "action": action})
    if not unlimited and used >= FREE_FEATURE_LIMIT:
        return jsonify({
            "status": "limit_reached", "action": action,
            "used": used, "remaining": 0, "limit": FREE_FEATURE_LIMIT,
        }), 429

    feature_usage_collection.insert_one({
        "email": email, "action": action, "created_at": datetime.now(timezone.utc),
    })
    used = used if unlimited else used + 1
    return jsonify({
        "status": "success", "action": action,
        "used": used,
        "remaining": 9999 if unlimited else max(0, FREE_FEATURE_LIMIT - used),
        "unlimited": unlimited,
    })
