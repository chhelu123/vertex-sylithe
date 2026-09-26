import threading
import re
import json
import requests
from flask import Blueprint, request, jsonify
import ee
import os

chm_bp = Blueprint('chm', __name__)

_gee_ready = False

def strip_z_coords(coords):
    if not isinstance(coords, list):
        return coords
    if len(coords) > 0 and isinstance(coords[0], (int, float)):
        return coords[:2]
    return [strip_z_coords(c) for c in coords]

def init_gee():
    global _gee_ready
    # Shared initialiser supports a JSON env var (Render) as well as file paths.
    from services.gee_init import init_gee as _shared_init
    if _shared_init():
        _gee_ready = True

# Run in background thread so server cold-start is not blocked
threading.Thread(target=init_gee, daemon=True).start()


def _ensure_gee():
    """
    Returns True if Earth Engine is usable.

    The per-module init thread can lose a startup race against other
    blueprints that also call ee.Initialize(), leaving _gee_ready False
    even though EE is initialized globally. So if our flag isn't set, probe
    EE directly and, if still not ready, attempt a synchronous init.
    """
    global _gee_ready
    if _gee_ready:
        return True
    try:
        ee.Number(1).getInfo()  # already initialised by some other thread?
        _gee_ready = True
        return True
    except Exception:
        pass
    init_gee()  # retry our own init synchronously
    return _gee_ready

def run_chm_inference(geojson, year):
    try:
        if geojson.get('type') == 'FeatureCollection':
            features = []
            last_geom_error = None
            for feat in geojson.get('features', []):
                if feat is None:
                    continue
                geom_dict = feat.get('geometry') if isinstance(feat, dict) else None
                if not geom_dict:
                    continue
                geom_type = geom_dict.get('type')

                if geom_type == 'GeometryCollection':
                    for g in geom_dict.get('geometries', []):
                        g_type = g.get('type')
                        if g_type and 'coordinates' in g:
                            try:
                                features.append(ee.Feature(ee.Geometry({
                                    'type': g_type,
                                    'coordinates': strip_z_coords(g.get('coordinates'))
                                })))
                            except Exception as e:
                                last_geom_error = str(e)
                else:
                    if geom_type and 'coordinates' in geom_dict:
                        try:
                            features.append(ee.Feature(ee.Geometry({
                                'type': geom_type,
                                'coordinates': strip_z_coords(geom_dict.get('coordinates'))
                            })))
                        except Exception as e:
                            last_geom_error = str(e)

            if not features:
                detail = f" ({last_geom_error})" if last_geom_error else ""
                return {"status": "error", "message": f"No valid geometries found in FeatureCollection.{detail}"}
            
            aoi = ee.FeatureCollection(features).geometry()
            
        elif geojson.get('type') == 'Feature':
            aoi = ee.Geometry(geojson.get('geometry'))
        else:
            aoi = ee.Geometry(geojson)
        
        # --- LULC FILTERING ---
        lc = ee.ImageCollection("ESA/WorldCover/v200").first().clip(aoi)
        
        strict_mask = lc.eq(10).Or(lc.eq(95))
        
        # Stats Calculation
        lc_stats = lc.reduceRegion(ee.Reducer.frequencyHistogram(), aoi, 10, maxPixels=1e9).getInfo().get('Map', {})
        total_px = sum(float(v) for v in lc_stats.values())
        
        # Reforestation suitability pixels: Cropland (40), Grassland (30/20), Bareland (60)
        suitable_px = float(lc_stats.get('40', 0)) + float(lc_stats.get('30', 0)) + float(lc_stats.get('20', 0)) + float(lc_stats.get('60', 0))
        suitability_pct = (suitable_px / total_px * 100) if total_px > 0 else 0

        # Maintain older code LULC structures for frontend sidebar logic
        def to_ha(px): return round((float(px) * 100) / 10000, 2)
        def get_tile(val, color):
            # `val` may be a single class id or a list of ids (e.g. grass+shrub),
            # so the overlay matches the area calculation for combined classes.
            vals = val if isinstance(val, (list, tuple)) else [val]
            mask = lc.eq(vals[0])
            for v in vals[1:]:
                mask = mask.Or(lc.eq(v))
            return mask.updateMask(mask).getMapId({'palette': [color]})['tile_fetcher'].url_format
        
        # Handle Deforestation for the selected year
        def get_actual_ha(mask):
            try:
                area_res = mask.multiply(ee.Image.pixelArea()).reduceRegion(
                    reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e9
                ).getInfo()
                return round(float(list(area_res.values())[0]) / 10000, 2) if area_res else 0.0
            except: return 0.0

        try:
            s2_2018 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate('2018-01-01', '2018-12-31').median()
            ndvi_2018 = s2_2018.normalizedDifference(['B8', 'B4'])
            s2_curr = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate(f"{year}-01-01", f"{year}-12-31").filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median()
            ndvi_curr = s2_curr.normalizedDifference(['B8','B4']).rename('NDVI')
            deforestation_mask = ndvi_2018.subtract(ndvi_curr).gt(0.25).And(lc.eq(10))
            defor_ha = get_actual_ha(deforestation_mask)
            defor_tile = deforestation_mask.updateMask(deforestation_mask).getMapId({'palette': ['#9133bd']})['tile_fetcher'].url_format if defor_ha > 0 else ""
        except:
            deforestation_mask = ee.Image(0).selfMask()
            defor_ha = 0
            defor_tile = ""

        # Precompute Burn Masks for all years 2012 to 2022 (multi-band image for fast single-call area reduction)
        burn_stats = {}
        burn_tiles = {}
        burn_masks = []
        
        for y in range(2012, 2023):
            try:
                # Reverting strictly to the original Sentinel-2 NBR median() logic used in the codebase
                # Because Sentinel-2 SR data only begins in 2017, years 2012-2016 will safely fall back to 0.
                s2_y = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate(f"{y}-01-01", f"{y}-12-31").filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median()
                nbr = s2_y.normalizedDifference(['B8', 'B12'])
                bmask = nbr.lt(-0.1).unmask(0).rename(str(y))
                burn_masks.append(bmask)
            except:
                burn_masks.append(ee.Image(0).rename(str(y)))

        try:
            multi_burn = ee.Image(burn_masks).clip(aoi)
            # S2 resolution is 20m
            area_multi = multi_burn.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e9
            ).getInfo()
            
            for y in range(2012, 2023):
                val = area_multi.get(str(y))
                b_ha = round(float(val) / 10000, 2) if val else 0.0
                burn_stats[str(y)] = b_ha
                if b_ha > 0:
                    y_mask = multi_burn.select(str(y))
                    y_mask = y_mask.updateMask(y_mask.gt(0))
                    burn_tiles[f"burn_layer_{y}"] = y_mask.getMapId({'palette': ['#4ca1df']})['tile_fetcher'].url_format
                else:
                    burn_tiles[f"burn_layer_{y}"] = ""
        except:
            for y in range(2012, 2023):
                burn_stats[str(y)] = 0
                burn_tiles[f"burn_layer_{y}"] = ""

        # Use actual geodesic AOI area (not LULC pixel count, which over-counts edge pixels)
        try:
            actual_area_m2 = aoi.area(maxError=1).getInfo()
            total_ha = round(float(actual_area_m2) / 10000, 2)
        except:
            total_ha = to_ha(total_px)  # fallback if area() call fails

        # --- CANOPY HEIGHT META V2 ---
        model_prediction = None
        chm_tiles = {}
        try:
            # Try ImageCollection first, if fails try Image
            try:
                meta_chm = ee.ImageCollection('projects/meta-forest-monitoring-okw37/assets/CanopyHeight').mosaic().clip(aoi)
            except:
                meta_chm = ee.Image('projects/meta-forest-monitoring-okw37/assets/CanopyHeight').clip(aoi)

            chm_mask = meta_chm.gt(0)
            masked_chm = meta_chm.updateMask(chm_mask)

            chm_stats = masked_chm.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
                geometry=aoi,
                scale=1,
                maxPixels=1e9
            ).getInfo()

            if chm_stats:
                band_keys = list(chm_stats.keys())
                b_name = 'cover_code' if 'cover_code_mean' in chm_stats else (band_keys[0].replace('_mean', '').replace('_max', '') if band_keys else "b1")
                
                avg_h = round(chm_stats.get(f"{b_name}_mean", 0) or 0, 1)
                max_h = round(chm_stats.get(f"{b_name}_max", 0) or 0, 1)

                max_h_int = int(max_h)
                max_bucket = ((max_h_int // 5) + 1) * 5
                if max_bucket == 0: max_bucket = 5
                steps = max_bucket // 5

                hist = masked_chm.reduceRegion(
                    reducer=ee.Reducer.fixedHistogram(0, max_bucket, steps),
                    geometry=aoi,
                    scale=1,
                    maxPixels=1e9
                ).getInfo()

                hist_data = hist.get(b_name, [])
                palette_ext = ['#c7e9b4', '#41b6c4', '#1d91c0', '#225ea8', '#0c2c84', '#081d58', '#041031', '#02091c', '#01040d', '#000000']
                
                distribution = {}
                for i, row in enumerate(hist_data):
                    min_v = int(row[0])
                    max_v = min_v + 5
                    count = int(row[1])
                    label = f"{min_v}-{max_v}m"
                    color = palette_ext[i % len(palette_ext)]
                    distribution[label] = { "count": count, "color": color, "min_v": min_v, "max_v": max_v }
                
                distribution = {k: v for k, v in reversed(list(distribution.items()))}

                total_tree_pixels = sum(int(v["count"]) for v in distribution.values())
                # CHM histogram computed at scale=1 (1m resolution), so 1 pixel = 1m² = 0.0001 ha
                tree_chm_ha = round(total_tree_pixels * 0.0001, 2)

                # Fetch CHM points for frontend tree clustering
                points_list = []
                try:
                    # The most robust method: combine lat/lon and CHM height into a 1D Array per pixel.
                    # This guarantees that coordinates and heights stay perfectly tied together (no scrambling),
                    # and uses reduceRegion which bypasses the memory limits of sample().
                    pixel_array = ee.Image.pixelLonLat().addBands(masked_chm).toArray()
                    
                    sampled = pixel_array.reduceRegion(
                        reducer=ee.Reducer.toList(),
                        geometry=aoi,
                        scale=3, # Scale 3m reduces point count by 9x to keep payload light
                        maxPixels=1e9
                    ).getInfo()
                    
                    if sampled:
                        arr_key = list(sampled.keys())[0]
                        points = sampled.get(arr_key, [])
                        
                        for p in points:
                            if len(p) >= 3 and p[2] >= 2:
                                # p is [longitude, latitude, height]
                                # We need to append [lat, lon, height] to match frontend ChmMap.jsx
                                points_list.append([p[1], p[0], round(p[2], 2)])
                except Exception as e:
                    print("Point extraction error:", e)

                model_prediction = {
                    "avg": avg_h,
                    "max": max_h,
                    "points": points_list,
                    "distribution": distribution,
                    "total_tree_pixels": total_tree_pixels,
                    "tree_chm_ha": tree_chm_ha
                }
                
                for lbl, info in distribution.items():
                    bucket_mask = masked_chm.gte(info["min_v"]).And(masked_chm.lt(info["max_v"]))
                    chm_tiles[lbl] = bucket_mask.updateMask(bucket_mask).getMapId({'palette': [info['color']]})['tile_fetcher'].url_format
                # Single combined tree layer (all CHM > 0) in dark green — no overlap with LULC
                chm_tiles['tree_chm'] = masked_chm.getMapId({'min': 0, 'max': 30, 'palette': ['#1a5c2a']})['tile_fetcher'].url_format
                # CHM v2 canopy layer — only trees taller than 1 m, shaded by height
                tree_1m = meta_chm.updateMask(meta_chm.gt(1))
                chm_tiles['tree_canopy_1m'] = tree_1m.getMapId({
                    'min': 1, 'max': 30,
                    'palette': ['#bbf7d0', '#4ade80', '#16a34a', '#15803d', '#14532d']
                })['tile_fetcher'].url_format
        except Exception as e:
            print("Meta CHM Error:", e)

        # --- OFFICIAL REGISTERED FOREST (EC JRC Global Forest Cover 2020, V3) ---
        # Authoritative 10 m forest map used to support the EU Deforestation
        # Regulation. Band 'Map' == 1 marks officially-recognised forest land.
        official_forest_tile = ""
        official_forest_ha = 0.0
        try:
            gfc2020 = ee.Image('JRC/GFC2020/V3').select('Map').clip(aoi)
            forest_mask = gfc2020.eq(1)
            official_forest_tile = forest_mask.updateMask(forest_mask).getMapId(
                {'palette': ['#0b3d2e']}
            )['tile_fetcher'].url_format
            forest_area = forest_mask.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(), geometry=aoi, scale=10, maxPixels=1e9
            ).getInfo()
            official_forest_ha = round(float(list(forest_area.values())[0] or 0) / 10000, 2)
        except Exception as e:
            print("GFC2020 official forest layer error:", e)

        return {
            "status": "success",
            "results": {
                "total_area_ha": total_ha,
                "eligibility": {"percentage": round(suitability_pct, 1)},
                "model_prediction": model_prediction,
                "official_forest_ha": official_forest_ha,
                "lulc": {
                    "cropland": to_ha(lc_stats.get('40', 0)), 
                    "grass": to_ha(lc_stats.get('30', 0)) + to_ha(lc_stats.get('20', 0)),
                    "bare": to_ha(lc_stats.get('60', 0)), 
                    "burn": burn_stats,
                    "trees": to_ha(lc_stats.get('10', 0)), 
                    "water": to_ha(lc_stats.get('80', 0)), 
                    "mangroves": to_ha(lc_stats.get('90', 0)) + to_ha(lc_stats.get('95', 0)),
                    "ice_snow": to_ha(lc_stats.get('70', 0)),
                    "urban": to_ha(lc_stats.get('50', 0)),
                    "clouds": 0,
                    "defor": get_actual_ha(deforestation_mask)
                },
                "tiles": {
                    **chm_tiles,
                    **burn_tiles,
                    # Canonical LULC palette — kept in sync with the frontend
                    # legend (ChmSidebar ClassificationRow + LULC Snapshot).
                    "trees": get_tile(10, "#397D49"),
                    "mangroves": get_tile([95, 90], "#7A87C6"),
                    "water": get_tile(80, "#419BDF"),
                    "ice_snow": get_tile(70, "#B39FE1"),
                    "cropland": get_tile(40, "#E49635"),
                    "grass": get_tile([30, 20], "#88B053"),
                    "bare": get_tile(60, "#A59B8F"),
                    "urban": get_tile(50, "#C4281B"),
                    "official_forest": official_forest_tile,
                    "defor_layer": deforestation_mask.updateMask(deforestation_mask).getMapId({'palette': ['#9133bd']})['tile_fetcher'].url_format if deforestation_mask else ""
                }
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@chm_bp.route('/predict', methods=['POST'])
def predict_chm():
    if not _ensure_gee():
        return jsonify({"status": "error", "message": "Analysis engine is still warming up. Please wait a moment and try again."}), 503

    data = request.json
    if not data or 'geojson' not in data:
        return jsonify({"status": "error", "message": "Missing geojson"}), 400

    year = data.get('year', 2023)
    geojson = data.get('geojson')

    result = run_chm_inference(geojson, year)
    return jsonify(result)


def _aoi_from_geojson(geojson):
    """Parse a GeoJSON (FeatureCollection / Feature / Geometry) into an ee geometry."""
    if geojson.get('type') == 'FeatureCollection':
        feats = []
        for feat in geojson.get('features', []):
            g = (feat or {}).get('geometry') or {}
            if g.get('type') and 'coordinates' in g:
                try:
                    feats.append(ee.Feature(ee.Geometry({
                        'type': g['type'], 'coordinates': strip_z_coords(g['coordinates'])
                    })))
                except Exception:
                    pass
        if not feats:
            raise ValueError("No valid geometries found in FeatureCollection")
        return ee.FeatureCollection(feats).geometry()
    if geojson.get('type') == 'Feature':
        return ee.Geometry(geojson['geometry'])
    return ee.Geometry(geojson)


@chm_bp.route('/land-history', methods=['POST', 'OPTIONS'])
def land_history():
    """
    Open-data land history for a plot, assembled from public GEE datasets:
      • Deforestation by year — UMD/Hansen Global Forest Change (2001-2023)
      • Fire by year          — MODIS/061/MCD64A1 burned area (2001-2023)
      • Vegetation (NDVI)      — Sentinel-2 yearly mean (2017+)
      • Rainfall              — CHIRPS yearly total (2010+)
    Each dataset uses a single multi-band reduceRegion for efficiency.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if not _ensure_gee():
        return jsonify({"status": "error", "message": "Analysis engine is still warming up. Please try again in a moment."}), 503

    data = request.json or {}
    geojson = data.get('geojson')
    if not geojson:
        return jsonify({"status": "error", "message": "Missing geojson"}), 400

    try:
        aoi = _aoi_from_geojson(geojson)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    out = {"deforestation": [], "fire": [], "ndvi": [], "rainfall": []}
    px_area = ee.Image.pixelArea()

    # ── Deforestation by year (Hansen GFC 2025 v1.13 → loss to 2024) ─
    try:
        try:
            hansen = ee.Image('UMD/hansen/global_forest_change_2025_v1_13')
            max_loss_year = 25  # lossyear 1..24 => 2001..2024
        except Exception:
            hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')
            max_loss_year = 24
        loss_by_year = px_area.addBands(hansen.select('lossyear'))
        grouped = loss_by_year.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='year'),
            geometry=aoi, scale=30, maxPixels=1e9
        ).getInfo()
        gmap = {int(g['year']): float(g['sum']) for g in grouped.get('groups', [])}
        for y in range(1, max_loss_year):
            out['deforestation'].append({"year": 2000 + y, "loss_ha": round(gmap.get(y, 0) / 10000, 2)})
    except Exception as e:
        print("land-history deforestation:", e)

    # ── Fire by year (MODIS MCD64A1 burned area) ─────────────────────
    try:
        def burn_band(y):
            b = (ee.ImageCollection('MODIS/061/MCD64A1')
                 .filterDate(f'{y}-01-01', f'{y}-12-31').select('BurnDate')
                 .max().gt(0).unmask(0))
            return b.multiply(px_area).rename(str(y))
        years_f = list(range(2001, 2025))  # through 2024
        multi_fire = ee.Image([burn_band(y) for y in years_f])
        res_f = multi_fire.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=500, maxPixels=1e9).getInfo()
        for y in years_f:
            out['fire'].append({"year": y, "burn_ha": round(float(res_f.get(str(y)) or 0) / 10000, 2)})
    except Exception as e:
        print("land-history fire:", e)

    # ── Vegetation greening (Sentinel-2 yearly mean NDVI) ────────────
    try:
        def ndvi_band(y):
            col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                   .filterBounds(aoi).filterDate(f'{y}-01-01', f'{y}-12-31')
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median())
            return col.normalizedDifference(['B8', 'B4']).rename(str(y))
        years_n = list(range(2018, 2027))  # through 2026 (current year, partial)
        multi_ndvi = ee.Image([ndvi_band(y) for y in years_n])
        res_n = multi_ndvi.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e9).getInfo()
        for y in years_n:
            v = res_n.get(str(y))
            if v is not None:
                out['ndvi'].append({"year": y, "ndvi": round(float(v), 3)})
    except Exception as e:
        print("land-history ndvi:", e)

    # ── Rainfall (CHIRPS yearly total, mm) ───────────────────────────
    try:
        def rain_band(y):
            return (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                    .filterDate(f'{y}-01-01', f'{y}-12-31').sum().rename(str(y)))
        years_r = list(range(2014, 2024))
        multi_rain = ee.Image([rain_band(y) for y in years_r])
        res_r = multi_rain.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=5000, maxPixels=1e9).getInfo()
        for y in years_r:
            v = res_r.get(str(y))
            if v is not None:
                out['rainfall'].append({"year": y, "mm": round(float(v), 1)})
    except Exception as e:
        print("land-history rainfall:", e)

    # ── Land-cover change 2015→present (Google Dynamic World, 10 m) ──
    # Per-year land-cover composition (ha) split into the 9 Dynamic World
    # classes so the UI can show eligible vs ineligible land change over time.
    out['lulc_timeseries'] = []
    # Dynamic World class id → key
    DW = {0: 'water', 1: 'trees', 2: 'grass', 3: 'flooded', 4: 'crops',
          5: 'shrub', 6: 'built', 7: 'bare', 8: 'snow'}
    try:
        dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(aoi)
        years_dw = list(range(2016, 2026))  # full calendar years (2015 is partial)
        series = []
        for y in years_dw:
            label = dw.filterDate(f'{y}-01-01', f'{y}-12-31').select('label').mode().clip(aoi)
            hist = label.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(), geometry=aoi, scale=10, maxPixels=1e9
            ).getInfo().get('label') or {}
            if not hist:
                continue
            row = {"year": y}
            for cid, key in DW.items():
                px = float(hist.get(str(cid), 0))
                row[key] = round(px * 0.01, 1)  # 10 m pixel = 100 m² = 0.01 ha
            series.append(row)
        out['lulc_timeseries'] = series
    except Exception as e:
        print("land-history lulc_timeseries (Dynamic World):", e)

    # ── Site & carbon profile (single-value open-data metrics) ──────
    site = {}
    try:
        area_ha = float(aoi.area(maxError=1).getInfo()) / 10000
        site['area_ha'] = round(area_ha, 1)
    except Exception:
        area_ha = 0

    # Biomass carbon — ESA CCI Above-Ground Biomass v6 (2022, latest); falls
    # back to NASA/ORNL (2010). AGB is dry biomass (Mg/ha) → carbon via the
    # IPCC 0.47 carbon fraction; BGB estimated with a 0.26 root-to-shoot ratio.
    def _set_biomass(agb_carbon, bgb_carbon, year, source):
        per_ha = round((agb_carbon + bgb_carbon) * 3.667, 1)
        site['biomass'] = {
            'agb_mgc_ha': round(agb_carbon, 1), 'bgb_mgc_ha': round(bgb_carbon, 1),
            'tco2e_per_ha': per_ha, 'total_tco2e': round(per_ha * area_ha),
            'year': year, 'source': source,
        }
    try:
        agb_img = ee.Image('ESA/CCI/Above_Ground_Biomass/V6_0/2022')
        agb_dry = float(agb_img.select('agb').reduceRegion(
            reducer=ee.Reducer.mean(), geometry=aoi, scale=100, maxPixels=1e9).getInfo().get('agb') or 0)
        if agb_dry <= 0:
            raise ValueError('ESA CCI AGB returned 0')
        carbon_agb = agb_dry * 0.47
        _set_biomass(carbon_agb, carbon_agb * 0.26, 2022, 'ESA CCI Biomass v6')
    except Exception as e:
        print('site biomass (ESA CCI):', e)
        try:
            bio = ee.ImageCollection('NASA/ORNL/biomass_carbon_density/v1').mosaic().select(['agb', 'bgb'])
            bs = bio.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=300, maxPixels=1e9).getInfo()
            _set_biomass(float(bs.get('agb') or 0), float(bs.get('bgb') or 0), 2010, 'NASA/ORNL Biomass')
        except Exception as e2:
            print('site biomass (ORNL):', e2)

    # Soil organic carbon (OpenLandMap, 0 cm, g/kg)
    try:
        soc = ee.Image('OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02').select('b0')
        sv = soc.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=250, maxPixels=1e9).getInfo()
        site['soil_organic_carbon_gkg'] = round(float(list(sv.values())[0] or 0), 1)
    except Exception as e:
        print('site soc:', e)

    # Terrain — Copernicus GLO-30 DEM (recent TanDEM-X) + slope
    try:
        glo = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM')
        dem = glo.mosaic().setDefaultProjection(glo.first().projection())
        slope = ee.Terrain.slope(dem)
        tv = dem.rename('elev').addBands(slope.rename('slope')).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=aoi, scale=30, maxPixels=1e9).getInfo()
        site['terrain'] = {'elevation_m': round(float(tv.get('elev') or 0)), 'slope_deg': round(float(tv.get('slope') or 0), 1),
                           'year': 2015, 'source': 'Copernicus GLO-30'}
    except Exception as e:
        print('site terrain:', e)

    # Population — JRC GHSL latest available epoch (2025 → 2020 fallback)
    try:
        pop_year = 2025
        try:
            pop = ee.Image('JRC/GHSL/P2023A/GHS_POP/2025')
            pv = pop.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e9).getInfo()
        except Exception:
            pop_year = 2020
            pop = ee.Image('JRC/GHSL/P2023A/GHS_POP/2020')
            pv = pop.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=100, maxPixels=1e9).getInfo()
        site['population'] = round(float(list(pv.values())[0] or 0))
        site['population_year'] = pop_year
    except Exception as e:
        print('site population:', e)

    # Surface water occurrence (JRC GSW, %)
    try:
        gsw = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence')
        wv = gsw.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=30, maxPixels=1e9).getInfo()
        site['water_occurrence_pct'] = round(float(list(wv.values())[0] or 0), 1)
    except Exception as e:
        print('site water:', e)

    # Nighttime lights (VIIRS, development proxy) — latest full year
    try:
        ntl = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG').filterDate('2024-01-01', '2024-12-31').select('avg_rad').mean()
        nv = ntl.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=500, maxPixels=1e9).getInfo()
        site['nighttime_lights'] = round(float(list(nv.values())[0] or 0), 2)
        site['nighttime_lights_year'] = 2024
    except Exception as e:
        print('site ntl:', e)

    # Protected-area overlap (WDPA)
    try:
        wdpa = ee.FeatureCollection('WCMC/WDPA/current/polygons').filterBounds(aoi)
        site['protected_area'] = int(wdpa.size().getInfo()) > 0
    except Exception as e:
        print('site wdpa:', e)

    out['site_profile'] = site
    return jsonify({"status": "success", "history": out})


@chm_bp.route('/land-summary', methods=['POST', 'OPTIONS'])
def land_summary():
    """Sylithe AI — expert 5-point carbon-project analysis + rating (DeepSeek)."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    from config import DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        return jsonify({"status": "error", "message": "AI summary is not configured."}), 503

    data = request.get_json(silent=True) or {}
    hist = data.get('history') or {}
    project = data.get('project') or {}
    try:
        psy = int(data.get('project_start_year') or project.get('start_year') or 0) or None
    except Exception:
        psy = None

    # Build a compact, factual brief from the plot's open-data history.
    facts = []
    lc = hist.get('lulc_timeseries') or []
    if lc:
        first, last = lc[0], lc[-1]
        for k, label in [('trees', 'tree cover'), ('crops', 'cropland'), ('grass', 'grassland'),
                         ('shrub', 'shrub/scrub'), ('built', 'built-up'), ('water', 'water')]:
            a, b = first.get(k, 0), last.get(k, 0)
            facts.append(f"{label}: {a} ha ({first.get('year')}) -> {b} ha ({last.get('year')}) [{'+' if b - a >= 0 else ''}{round(b - a, 1)} ha]")

    # ── Project start year: baseline (pre-project) vs crediting period ──
    if psy and lc:
        def _at(y):
            c = [r for r in lc if r.get('year', 0) <= y]
            return c[-1] if c else lc[0]
        sLC, lLC = _at(psy), lc[-1]
        facts.insert(0, f"PROJECT START YEAR = {psy}. Baseline period = before {psy}; project/crediting period = {psy} to {lLC.get('year')}.")
        for k, label in [('trees', 'tree cover'), ('crops', 'cropland'), ('shrub', 'shrub'), ('built', 'built-up')]:
            a, b = sLC.get(k, 0), lLC.get(k, 0)
            facts.append(f"PROJECT-PERIOD change since start ({psy}->{lLC.get('year')}) {label}: {a} -> {b} ha [{'+' if b - a >= 0 else ''}{round(b - a, 1)} ha]")
        pre = [r for r in lc if r.get('year', 0) < psy]
        if len(pre) >= 2:
            a, b = pre[0].get('trees', 0), pre[-1].get('trees', 0)
            facts.append(f"BASELINE pre-project tree-cover trend ({pre[0].get('year')}->{pre[-1].get('year')}): {a} -> {b} ha [{'+' if b - a >= 0 else ''}{round(b - a, 1)} ha] — KEY for additionality (was the land already reforesting without a project?)")

    defor = hist.get('deforestation') or []
    if defor:
        facts.append(f"deforestation since 2008: {round(sum(d.get('loss_ha', 0) for d in defor), 1)} ha total")
        if psy:
            db = round(sum(d.get('loss_ha', 0) for d in defor if d.get('year', 0) < psy), 1)
            da = round(sum(d.get('loss_ha', 0) for d in defor if d.get('year', 0) >= psy), 1)
            facts.append(f"deforestation: {db} ha BEFORE {psy} (baseline) vs {da} ha SINCE {psy} (project period)")
    fire = hist.get('fire') or []
    if fire:
        facts.append(f"burned area since 2008: {round(sum(d.get('burn_ha', 0) for d in fire), 1)} ha total")
    ndvi = hist.get('ndvi') or []
    if len(ndvi) >= 2:
        facts.append(f"mean NDVI: {ndvi[0].get('ndvi')} ({ndvi[0].get('year')}) -> {ndvi[-1].get('ndvi')} ({ndvi[-1].get('year')})")
    sp = hist.get('site_profile') or {}
    # Present land-cover composition (latest Dynamic World year)
    if lc:
        cur = lc[-1]
        tot = sum(cur.get(k, 0) for k in ['trees', 'crops', 'grass', 'shrub', 'bare', 'flooded', 'built', 'water', 'snow']) or 1
        restorable = cur.get('crops', 0) + cur.get('grass', 0) + cur.get('shrub', 0) + cur.get('bare', 0)
        facts.append(f"CURRENT land cover ({cur.get('year')}): trees {cur.get('trees',0)} ha, cropland {cur.get('crops',0)} ha, grass {cur.get('grass',0)} ha, shrub {cur.get('shrub',0)} ha, built {cur.get('built',0)} ha, water {cur.get('water',0)} ha")
        facts.append(f"restorable/plantable land (crop+grass+shrub+bare): ~{round(restorable,1)} ha ({round(restorable/tot*100)}% of area)")
    if sp.get('biomass'):
        b = sp['biomass']
        facts.append(f"standing carbon stock: {b.get('total_tco2e')} tCO2e total, {b.get('tco2e_per_ha')} tCO2e/ha ({b.get('year')})")
    if sp.get('soil_organic_carbon_gkg') is not None:
        facts.append(f"soil organic carbon: {sp.get('soil_organic_carbon_gkg')} g/kg (topsoil)")
    if sp.get('terrain'):
        facts.append(f"terrain: {sp['terrain'].get('elevation_m')} m elevation, {sp['terrain'].get('slope_deg')}° mean slope")
    rain = hist.get('rainfall') or []
    if rain:
        facts.append(f"mean annual rainfall: ~{round(sum(d.get('mm',0) for d in rain)/len(rain))} mm/yr")
    if sp.get('protected_area') is not None:
        facts.append(f"protected-area (WDPA) overlap: {'yes' if sp['protected_area'] else 'no'}")
    if sp.get('population') is not None:
        facts.append(f"population within boundary: {sp['population']}")
    if not facts:
        return jsonify({"status": "error", "message": "Not enough data to summarise."}), 400

    ptype = project.get('type', 'nature-based (ARR / REDD+ / Agroforestry)')
    area = sp.get('area_ha') or project.get('area_ha', '?')

    system_prompt = (
        "You are Sylithe AI — a world-leading forest-carbon geospatial analyst and one of the most respected "
        "experts in nature-based carbon project assessment. You specialise in Afforestation/Reforestation/"
        "Revegetation (ARR, Verra VM0047), Reducing Emissions from Deforestation & Degradation (REDD+, Verra "
        "VM0048 / VM0007) and Agroforestry, and you evaluate plots against Verra VCS and Gold Standard "
        "requirements: additionality, baseline, permanence & non-permanence risk buffer, leakage, MRV and "
        "co-benefits. You translate satellite/geospatial evidence into sharp, decision-grade verdicts that carbon "
        "project developers and credit buyers trust. Be specific, quantitative, and honest about risks."
    )
    user_prompt = (
        f"PLOT: {ptype} candidate, {area} ha. Geospatial evidence below (Dynamic World, Meta CHM, Hansen GFC, "
        f"MODIS, Sentinel-2, ESA CCI Biomass, JRC, OpenLandMap):\n"
        + "\n".join(f"- {f}" for f in facts) +
        "\n\nAs Sylithe AI, rate this plot like a carbon-ratings agency (e.g. Sylvera) and analyse it end-to-end.\n"
        "Return ONLY a JSON object with EXACTLY this shape:\n"
        "{\n"
        '  "rating": {\n'
        '    "grade": "<one of: AAA, AA, A, BBB, BB, B, C, D>",\n'
        '    "score": <integer 0-100>,\n'
        '    "verdict": "<2-4 word label, e.g. Strong candidate / Moderate potential / High risk>",\n'
        '    "dimensions": [\n'
        '      {"name": "Carbon Potential", "score": <0-100>},\n'
        '      {"name": "Additionality", "score": <0-100>},\n'
        '      {"name": "Permanence", "score": <0-100>},\n'
        '      {"name": "Co-benefits & Leakage", "score": <0-100>}\n'
        "    ]\n"
        "  },\n"
        '  "points": [ {"text": "<insight <=26 words>", "type": "<strength|risk|neutral>"}, ... EXACTLY 5 ... ]\n'
        "}\n\n"
        + (f"PROJECT START YEAR = {psy}. Anchor your analysis to this date: assess the BASELINE from the period BEFORE "
           f"{psy} and PROJECT PERFORMANCE from the change SINCE {psy} to present. Additionality is WEAKER if the land "
           f"was already reforesting/improving before {psy}, and STRONGER if it was stable/degrading before {psy} but "
           f"improved after. Reflect this in the Additionality score and the verdict.\n" if psy else "") +
        "The 5 points must collectively cover: (1) land-use trajectory comparing baseline (pre-start) vs project period "
        "(since start) & the most material change; (2) carbon stock & realistic sequestration / crediting potential; "
        "(3) best-fit methodology (ARR VM0047 / REDD+ VM0048 / Agroforestry) and why; (4) additionality & baseline "
        "strength judged against the project start year; (5) overall verdict (strong/moderate/weak) with the key "
        "permanence or leakage risk and the single most important next step. "
        "Tag each point 'strength' (positive/favourable), 'risk' (a concern/red flag) or 'neutral' (factual). "
        "Be specific to the numbers. Output valid JSON only — no markdown, no preamble."
    )

    def _norm_grade(g):
        g = str(g or '').upper().strip()
        return g if g in {'AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'D'} else 'B'

    try:
        r = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.45, 'max_tokens': 900,
                'response_format': {'type': 'json_object'},
            }, timeout=50)
        r.raise_for_status()
        content = r.json()['choices'][0]['message']['content']
        parsed = json.loads(content)
        raw_points = parsed.get('points') or []
        points = []
        for p in raw_points[:5]:
            if isinstance(p, dict) and p.get('text'):
                t = str(p.get('type', 'neutral')).lower()
                points.append({'text': p['text'].strip(), 'type': t if t in ('strength', 'risk', 'neutral') else 'neutral'})
            elif isinstance(p, str) and p.strip():
                points.append({'text': p.strip(), 'type': 'neutral'})
        rating = parsed.get('rating') or {}
        rating = {
            'grade': _norm_grade(rating.get('grade')),
            'score': max(0, min(100, int(rating.get('score') or 0))),
            'verdict': str(rating.get('verdict') or '')[:40],
            'dimensions': [
                {'name': str(d.get('name', ''))[:40], 'score': max(0, min(100, int(d.get('score') or 0)))}
                for d in (rating.get('dimensions') or []) if isinstance(d, dict)
            ][:4],
        }
        if not points:
            raise ValueError('empty summary')
        return jsonify({"status": "success", "rating": rating, "points": points})
    except Exception as e:
        print(f"[land-summary] DeepSeek error: {e}")
        return jsonify({"status": "error", "message": "Could not generate AI summary."}), 502


def _report_facts(hist, scan, project):
    """Build a rich, factual brief from the plot's open-data record for the
    in-depth PDF report analysis."""
    facts = []
    lc = hist.get('lulc_timeseries') or []
    if lc:
        first, last = lc[0], lc[-1]
        facts.append(f"OBSERVATION WINDOW: {first.get('year')} -> {last.get('year')} (Dynamic World 10 m LULC).")
        for k, label in [('trees', 'tree cover'), ('crops', 'cropland'), ('grass', 'grassland'),
                         ('shrub', 'shrub/scrub'), ('bare', 'bare ground'), ('built', 'built-up'), ('water', 'water')]:
            a, b = first.get(k, 0), last.get(k, 0)
            if a or b:
                facts.append(f"{label}: {a} ha ({first.get('year')}) -> {b} ha ({last.get('year')}) [{'+' if b - a >= 0 else ''}{round(b - a, 1)} ha]")
        cur = last
        tot = sum(cur.get(k, 0) for k in ['trees', 'crops', 'grass', 'shrub', 'bare', 'flooded', 'built', 'water', 'snow']) or 1
        restorable = cur.get('crops', 0) + cur.get('grass', 0) + cur.get('shrub', 0) + cur.get('bare', 0)
        facts.append(f"RESTORABLE/PLANTABLE land (crop+grass+shrub+bare): ~{round(restorable, 1)} ha ({round(restorable / tot * 100)}% of area).")
    # in-app eligibility verdict + LULC composition
    elig = (scan or {}).get('eligibility') or {}
    if elig:
        facts.append(f"SYLITHE eligibility verdict: {elig.get('verdict', 'n/a')} (score {elig.get('score', 'n/a')}/100).")
    forest = (scan or {}).get('forest') or {}
    if forest:
        facts.append(f"tree cover {forest.get('cover_pct', '?')}%, deforestation risk {forest.get('deforestation_risk', 'low')}.")
    defor = hist.get('deforestation') or []
    if defor:
        facts.append(f"deforestation since 2008: {round(sum(d.get('loss_ha', 0) for d in defor), 1)} ha total (Hansen GFC).")
    fire = hist.get('fire') or []
    if fire:
        facts.append(f"burned area since 2008: {round(sum(d.get('burn_ha', 0) for d in fire), 1)} ha total (MODIS).")
    ndvi = hist.get('ndvi') or []
    if len(ndvi) >= 2:
        vals = [d.get('ndvi', 0) for d in ndvi if d.get('ndvi') is not None]
        facts.append(f"mean NDVI: {ndvi[0].get('ndvi')} ({ndvi[0].get('year')}) -> {ndvi[-1].get('ndvi')} ({ndvi[-1].get('year')}); range {min(vals)}-{max(vals)}.")
    rain = hist.get('rainfall') or []
    if rain:
        facts.append(f"mean annual rainfall: ~{round(sum(d.get('mm', 0) for d in rain) / len(rain))} mm/yr (CHIRPS).")
    sp = hist.get('site_profile') or {}
    if sp.get('terrain'):
        facts.append(f"terrain: {sp['terrain'].get('elevation_m')} m elevation, {sp['terrain'].get('slope_deg')}° mean slope.")
    if sp.get('soil_organic_carbon_gkg') is not None:
        facts.append(f"soil organic carbon: {sp.get('soil_organic_carbon_gkg')} g/kg (topsoil).")
    if sp.get('protected_area') is not None:
        facts.append(f"protected-area (WDPA) overlap: {'yes' if sp['protected_area'] else 'no'}.")
    if sp.get('population') is not None:
        facts.append(f"population within boundary: {sp['population']}.")
    return facts


@chm_bp.route('/report-analysis', methods=['POST', 'OPTIONS'])
def report_analysis():
    """Sylithe AI — in-depth, multi-paragraph carbon-expert analysis used to
    enrich the Forest Carbon Diligence PDF report (unlocked LULC + satellite
    sections only). Returns structured prose per section."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    from config import DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        return jsonify({"status": "error", "message": "AI analysis is not configured."}), 503

    data = request.get_json(silent=True) or {}
    hist = data.get('history') or {}
    scan = data.get('scan') or {}
    project = data.get('project') or {}
    facts = _report_facts(hist, scan, project)
    if not facts:
        return jsonify({"status": "error", "message": "Not enough data to analyse."}), 400

    ptype = project.get('type', 'nature-based (ARR / REDD+ / Agroforestry)')
    area = (hist.get('site_profile') or {}).get('area_ha') or scan.get('area_ha') or project.get('area_ha', '?')
    pname = project.get('name', 'this plot')

    system_prompt = (
        "You are Sylithe AI — a world-leading forest-carbon geospatial analyst and one of the most respected "
        "experts in nature-based carbon project assessment (ARR / Verra VM0047, REDD+ / Verra VM0048, "
        "Agroforestry), evaluating plots against Verra VCS and Gold Standard requirements: additionality, "
        "baseline, permanence & non-permanence risk buffer, leakage, MRV and co-benefits. You write the "
        "analytical narrative inside a professional carbon diligence report. Your prose is precise, "
        "quantitative, decision-grade and honest about risk. You ONLY interpret land-use/land-cover and "
        "open satellite evidence (you do NOT quote carbon-credit volumes or final biomass tonnages — those "
        "live in locked premium sections). Write in confident third-person report style, never first person, "
        "no markdown, no bullet symbols."
    )
    user_prompt = (
        f"PROJECT: {pname} — {ptype} candidate, {area} ha.\n"
        f"GEOSPATIAL EVIDENCE (Dynamic World, Hansen GFC, MODIS, Sentinel-2 NDVI, CHIRPS, GLO-30 DEM, OpenLandMap, WDPA):\n"
        + "\n".join(f"- {f}" for f in facts) +
        "\n\nWrite the analytical narrative for the report's unlocked LULC + satellite sections. "
        "Return ONLY a JSON object with EXACTLY these string fields (each a flowing analytical paragraph, "
        "NOT bullet points, lengths as noted):\n"
        "{\n"
        '  "executive": "<5-7 sentences: overall diligence read of the plot from the satellite record — what the land is, its trajectory, headline opportunity and the single biggest risk>",\n'
        '  "boundary": "<4-5 sentences: site-context analysis — terrain/elevation/slope, rainfall envelope, location and protected-area context, and what it means for accessibility, growth potential and project risk>",\n'
        '  "lulc": "<4-6 sentences: interpret the present land-cover composition and what each dominant class means for ARR vs REDD+ vs agroforestry suitability>",\n'
        '  "breakdown": "<4-5 sentences: class-by-class read of the land-cover composition — the dominant classes, their share, and what the mix implies for the creditable activity>",\n'
        '  "eligibility_split": "<4-5 sentences: analyse the eligible vs ineligible split — what drives the creditable area, the role of existing tree cover, and what is excluded and why>",\n'
        '  "change": "<5-7 sentences: in-depth read of the multi-year land-cover change — direction, drivers, what it implies for the Verra baseline scenario and additionality>",\n'
        '  "ndvi": "<4-5 sentences: vegetation-vigour trajectory from NDVI and what it signals about productivity, stress or recovery>",\n'
        '  "deforestation": "<4-5 sentences: deforestation/degradation history and its implication for REDD+ baseline, leakage and permanence>",\n'
        '  "fire": "<3-4 sentences: fire-disturbance exposure and its effect on the non-permanence risk buffer>",\n'
        '  "climate": "<3-4 sentences: rainfall/terrain growth envelope and species/establishment implications>",\n'
        '  "eligibility_outlook": "<4-6 sentences: best-fit Verra methodology and an honest eligibility outlook grounded in the evidence>",\n'
        '  "strengths": ["<short phrase>", "... 3-4 items, each a genuine evidence-backed strength ..."],\n'
        '  "concerns": ["<short phrase>", "... 2-3 items, each a real risk/red-flag ..."],\n'
        '  "next_steps": ["<short imperative>", "... 3 concrete diligence next steps ..."]\n'
        "}\n"
        "Be specific to the numbers above. Output valid JSON only — no markdown, no preamble."
    )

    try:
        r = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'deepseek-v4-pro',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.5, 'max_tokens': 8000,
                'response_format': {'type': 'json_object'},
            }, timeout=160)
        r.raise_for_status()
        parsed = json.loads(r.json()['choices'][0]['message']['content'])

        def _s(k):
            v = parsed.get(k)
            return v.strip() if isinstance(v, str) and v.strip() else None

        def _l(k):
            v = parsed.get(k)
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

        analysis = {
            'executive': _s('executive'),
            'boundary': _s('boundary'),
            'lulc': _s('lulc'),
            'breakdown': _s('breakdown'),
            'eligibility_split': _s('eligibility_split'),
            'change': _s('change'),
            'ndvi': _s('ndvi'),
            'deforestation': _s('deforestation'),
            'fire': _s('fire'),
            'climate': _s('climate'),
            'eligibility_outlook': _s('eligibility_outlook'),
            'strengths': _l('strengths')[:4],
            'concerns': _l('concerns')[:3],
            'next_steps': _l('next_steps')[:3],
        }
        if not any(analysis.values()):
            raise ValueError('empty analysis')
        return jsonify({"status": "success", "analysis": analysis})
    except Exception as e:
        print(f"[report-analysis] DeepSeek error: {e}")
        return jsonify({"status": "error", "message": "Could not generate AI analysis."}), 502
