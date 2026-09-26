import threading
from flask import Blueprint, request, jsonify
import ee
import os
from datetime import datetime

free_tier_bp = Blueprint('free_tier', __name__)

_gee_ready = False

FREE_AREA_LIMIT_HA = 500
FREE_SCANS_PER_MONTH = 3

# Dynamic World class definitions (class_id → (name, hex_color))
_DW_CLASSES = {
    0: ('Water',              '#419BDF'),
    1: ('Trees',              '#397D49'),
    2: ('Grass',              '#88B053'),
    3: ('Flooded Vegetation', '#7A87C6'),
    4: ('Crops',              '#E49635'),
    5: ('Shrub & Scrub',      '#DFC35A'),
    6: ('Built Area',         '#C4281B'),
    7: ('Bare Ground',        '#A59B8F'),
    8: ('Snow & Ice',         '#B39FE1'),
}


def _init_gee():
    global _gee_ready
    from services.gee_init import init_gee as _shared_init
    if _shared_init():
        _gee_ready = True


# Run in background thread so server cold-start is not blocked
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
            g = feat.get('geometry', {})
            if g.get('type') and 'coordinates' in g:
                try:
                    feats.append(ee.Feature(ee.Geometry({
                        'type': g['type'],
                        'coordinates': _strip_z(g['coordinates'])
                    })))
                except Exception:
                    pass
        if not feats:
            raise ValueError("No valid geometries found in FeatureCollection")
        return ee.FeatureCollection(feats).geometry()
    elif t == 'Feature':
        return ee.Geometry(geojson['geometry'])
    else:
        return ee.Geometry(geojson)


@free_tier_bp.route('/free/scan', methods=['POST'])
def free_scan():
    if not _ensure_gee():
        return jsonify({"status": "error", "message": "Analysis engine is still warming up. Please wait a moment and try again."}), 503

    data = request.get_json(silent=True)
    if not data or 'geojson' not in data:
        return jsonify({"status": "error", "message": "Missing geojson"}), 400

    geojson    = data['geojson']
    user_email = data.get('email', '').strip().lower()

    # ── Usage limit ───────────────────────────────────────────
    if user_email:
        try:
            from db import free_scans_collection
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            used = free_scans_collection.count_documents({
                'email': user_email,
                'created_at': {'$gte': month_start}
            })
            if used >= FREE_SCANS_PER_MONTH:
                return jsonify({
                    "status": "limit_reached",
                    "message": f"You've used all {FREE_SCANS_PER_MONTH} free scans this month.",
                    "used": used,
                    "limit": FREE_SCANS_PER_MONTH
                }), 429
        except Exception:
            pass

    try:
        aoi = _to_aoi(geojson)

        # ── Area guard ────────────────────────────────────────
        area_m2  = float(aoi.area(maxError=1).getInfo())
        total_ha = round(area_m2 / 10000, 2)
        if total_ha > FREE_AREA_LIMIT_HA:
            return jsonify({
                "status": "area_exceeded",
                "message": f"Free scan is limited to {FREE_AREA_LIMIT_HA} ha. Your area is {total_ha:.0f} ha.",
                "area_ha": total_ha,
                "limit_ha": FREE_AREA_LIMIT_HA
            }), 400

        # ── 1. LULC — Dynamic World (10 m, updated weekly) ───
        dw_label = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(aoi)
            .filterDate('2023-07-01', '2025-06-01')
            .select('label')
            .mode()
            .clip(aoi)
        )
        dw_hist   = dw_label.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=aoi, scale=10, maxPixels=1e9
        ).getInfo().get('label', {})

        total_px  = max(sum(float(v) for v in dw_hist.values()), 1)
        lulc      = {}
        for cid, (cname, ccolor) in _DW_CLASSES.items():
            px = float(dw_hist.get(str(cid), 0))
            lulc[cname] = {
                'ha':    round(px * 100 / 10000, 2),
                'pct':   round(px / total_px * 100, 1),
                'color': ccolor,
            }

        dw_tile_url = dw_label.getMapId({
            'min': 0, 'max': 8,
            'palette': [_DW_CLASSES[i][1] for i in range(9)]
        })['tile_fetcher'].url_format

        # ── 2. Forest — Hansen GFC 2023 ───────────────────────
        hansen    = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')
        tc2000    = hansen.select('treecover2000')
        loss      = hansen.select('loss')
        lossyear  = hansen.select('lossyear')

        fc_result = tc2000.gte(30).And(loss.eq(0)).multiply(100).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi, scale=30, maxPixels=1e9
        ).getInfo()
        forest_pct = round(float(list(fc_result.values())[0] or 0), 1)

        loss_area = (
            lossyear.gte(13).And(loss.eq(1))
            .multiply(ee.Image.pixelArea())
            .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=30, maxPixels=1e9)
            .getInfo()
        )
        loss_ha  = round(float(list(loss_area.values())[0] or 0) / 10000, 2)
        loss_pct = round(loss_ha / total_ha * 100, 1) if total_ha > 0 else 0
        defor_risk = 'high' if loss_pct > 10 else ('medium' if loss_pct > 3 else 'low')

        # ── 3. Carbon — Spawn 2020 (NASA/ORNL) ───────────────
        try:
            bio       = ee.Image('NASA/ORNL/biomass_carbon_density/v1')
            bio_stats = bio.select(['agb', 'bgb']).reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
                geometry=aoi, scale=300, maxPixels=1e9
            ).getInfo()
            mean_agb = float(bio_stats.get('agb_mean') or 0)
            mean_bgb = float(bio_stats.get('bgb_mean') or 0)
            std_agb  = float(bio_stats.get('agb_stdDev') or mean_agb * 0.25)
        except Exception:
            mean_agb = 80 if forest_pct > 50 else (40 if forest_pct > 20 else 15)
            mean_bgb = mean_agb * 0.26
            std_agb  = mean_agb * 0.25

        # (AGB + BGB) MgC/ha × 3.667 = tCO₂e/ha
        co2_ph_mid  = round((mean_agb + mean_bgb) * 3.667, 1)
        co2_ph_low  = max(0.0, round((mean_agb + mean_bgb - std_agb) * 3.667, 1))
        co2_ph_high = round((mean_agb + mean_bgb + std_agb) * 3.667, 1)

        total_co2_mid  = round(co2_ph_mid  * total_ha)
        total_co2_low  = round(co2_ph_low  * total_ha)
        total_co2_high = round(co2_ph_high * total_ha)

        restorable_pct = (
            lulc.get('Crops', {}).get('pct', 0) +
            lulc.get('Grass', {}).get('pct', 0) +
            lulc.get('Shrub & Scrub', {}).get('pct', 0) +
            lulc.get('Bare Ground', {}).get('pct', 0)
        )
        seq_rate_low  = 3.5 if restorable_pct > 40 else 2.0
        seq_rate_high = 9.0 if restorable_pct > 40 else 5.5
        annual_seq_low  = round(total_ha * seq_rate_low)
        annual_seq_high = round(total_ha * seq_rate_high)

        # ── 4. Eligibility ────────────────────────────────────
        trees_pct  = lulc.get('Trees', {}).get('pct', 0)
        crops_pct  = lulc.get('Crops', {}).get('pct', 0)
        grass_pct  = lulc.get('Grass', {}).get('pct', 0)
        shrub_pct  = lulc.get('Shrub & Scrub', {}).get('pct', 0)
        built_pct  = lulc.get('Built Area', {}).get('pct', 0)
        flood_pct  = lulc.get('Flooded Vegetation', {}).get('pct', 0)
        water_pct  = lulc.get('Water', {}).get('pct', 0)

        eligible_types = []
        score = 0

        if forest_pct >= 30 and loss_pct > 1:
            eligible_types.append('REDD+')
            score += 40
        if forest_pct >= 10 or trees_pct >= 10:
            eligible_types.append('IFM')
            score += 25
        if (crops_pct + grass_pct + shrub_pct) >= 25:
            eligible_types.append('ARR')
            eligible_types.append('Agroforestry')
            score += 30
        if flood_pct >= 5 or water_pct >= 15:
            eligible_types.append('Blue Carbon')
            score += 20

        score = min(score, 95)

        if built_pct > 50:
            verdict = 'not_eligible'
            reason  = 'Land is predominantly built-up. Carbon projects require natural or agricultural land.'
        elif total_ha < 5:
            verdict = 'low_potential'
            reason  = 'Area is very small. Most carbon methodologies require a minimum of 10 ha.'
        elif eligible_types:
            verdict = 'eligible' if score >= 40 else 'potentially_eligible'
            top2    = eligible_types[:2]
            reason  = f"Land characteristics are well-suited for {' & '.join(top2)}."
        else:
            verdict = 'low_potential'
            reason  = 'Limited carbon project potential based on current land cover.'

        # ── 5. Log usage ──────────────────────────────────────
        if user_email:
            try:
                from db import free_scans_collection
                free_scans_collection.insert_one({
                    'email':       user_email,
                    'area_ha':     total_ha,
                    'eligibility': verdict,
                    'created_at':  datetime.utcnow()
                })
            except Exception:
                pass

        return jsonify({
            "status": "success",
            "results": {
                "area_ha":      total_ha,
                "lulc":         lulc,
                "lulc_tile_url": dw_tile_url,
                "forest": {
                    "cover_pct":          forest_pct,
                    "loss_ha_10yr":       loss_ha,
                    "loss_pct_10yr":      loss_pct,
                    "deforestation_risk": defor_risk
                },
                "carbon": {
                    "co2_per_ha":      co2_ph_mid,
                    "total_co2_low":   total_co2_low,
                    "total_co2_mid":   total_co2_mid,
                    "total_co2_high":  total_co2_high,
                    "annual_seq_low":  annual_seq_low,
                    "annual_seq_high": annual_seq_high,
                },
                "eligibility": {
                    "verdict":        verdict,
                    "score":          score,
                    "reason":         reason,
                    "eligible_types": eligible_types,
                    "defor_risk":     defor_risk
                }
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
