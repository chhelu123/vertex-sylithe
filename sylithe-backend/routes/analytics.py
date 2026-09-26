from flask import Blueprint, request, jsonify
import ee
import os
import json

GEE_KEY_PATH = os.path.join(os.path.dirname(__file__), '..', 'gee-key.json')

def strip_z_coords(coords):
    if not isinstance(coords, list):
        return coords
    if len(coords) > 0 and isinstance(coords[0], (int, float)):
        return coords[:2]
    return [strip_z_coords(c) for c in coords]

# Create the blueprint
analytics_bp = Blueprint('analytics', __name__)

def _ensure_gee():
    # Shared initialiser — supports GEE_SERVICE_ACCOUNT_JSON (Render) and file
    # paths, and probes whether EE is already live (initialised by any module).
    from services.gee_init import init_gee
    if init_gee():
        return True
    try:
        ee.Number(1).getInfo()
        return True
    except Exception:
        return False

@analytics_bp.route('/analytics', methods=['POST'])
def get_analytics():
    """
    Expects a GeoJSON FeatureCollection or geometry and a 'metric' type.
    Returns histogram / boxplot statistics.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    metric = data.get('metric', 'ndvi') # ndvi, temperature, precipitation
    
    # Safely parse year as an integer
    year_raw = data.get('year', 2024)
    try:
        if isinstance(year_raw, str):
            year = int(year_raw.replace('FY ', '').replace('FY', '').strip())
        else:
            year = int(year_raw)
    except (ValueError, TypeError):
        year = 2024
        
    geojson = data.get('geojson')
    
    if not geojson:
        return jsonify({"error": "Missing 'geojson' bounds"}), 400

    if not _ensure_gee():
        return jsonify({
            "error": "Google Earth Engine Authentication Failed",
            "message": "GEE service account credentials are not configured on the server.",
        }), 401

    try:
        # Convert GeoJSON to EE geometry robustly
        if geojson.get('type') == 'FeatureCollection':
            features = []
            err_msgs = []
            for feat in geojson.get('features', []):
                geom_dict = feat.get('geometry')
                # Rebuild dict strictly to avoid EE rejecting "bbox" or other extra keys
                geom_type = geom_dict.get('type')
                
                # Handle KML GeometryCollections
                if geom_type == 'GeometryCollection':
                    clean_geoms = []
                    for g in geom_dict.get('geometries', []):
                        g_type = g.get('type')
                        if g_type and 'coordinates' in g:
                            clean_geoms.append({
                                'type': g_type,
                                'coordinates': strip_z_coords(g.get('coordinates'))
                            })
                    
                    for g in clean_geoms:
                        try:
                            features.append(ee.Feature(ee.Geometry(g)))
                        except Exception as e: 
                            err_msgs.append(f"{str(e)} -> {str(g)[:200]}")
                else:
                    if geom_type and 'coordinates' in geom_dict:
                        clean_geom = {
                            'type': geom_type,
                            'coordinates': strip_z_coords(geom_dict.get('coordinates'))
                        }
                        try:
                            features.append(ee.Feature(ee.Geometry(clean_geom)))
                        except Exception as e:
                            err_msgs.append(f"{str(e)} -> {str(clean_geom)[:200]}")
                        
            if not features:
                return jsonify({
                    "error": "No valid geometry features found", 
                    "message": f"Earth Engine rejected the standardized geometries: {err_msgs[:3]}" if err_msgs else "The uploaded KML contains no internal geometric arrays."
                }), 400
            
            # Use bounded convex hull to prevent multi-polygon rejection in reducers
            geometry = ee.FeatureCollection(features).geometry().bounds()
            
        elif geojson.get('type') == 'Feature':
            try:
                geometry = ee.Geometry(geojson.get('geometry')).bounds()
            except:
                return jsonify({"error": "Invalid Geometry", "message": "Feature geometry is invalid."}), 400
        else:
            try:
                geometry = ee.Geometry(geojson).bounds()
            except:
                return jsonify({"error": "Invalid Geometry", "message": "Raw geometry is invalid."}), 400
            
        # Set up a date range for the year
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = ee.Date.fromYMD(year, 12, 31)

        if metric == 'ndvi':
            collection = ee.ImageCollection('COPERNICUS/S2_SR') \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                
            def add_ndvi(image):
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                return image.addBands(ndvi)
                
            ndvi_col = collection.map(add_ndvi).select('NDVI')
            median_ndvi = ndvi_col.median()
            
            # --- 6-Month Trend ---
            def get_monthly_ndvi(month):
                m_start = ee.Date.fromYMD(year, month, 1)
                m_end = m_start.advance(1, 'month')
                m_median = ndvi_col.filterDate(m_start, m_end).median()
                
                # Check if image has bands (is not empty)
                mean_val = ee.Algorithms.If(
                    m_median.bandNames().size().gt(0),
                    m_median.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geometry,
                        scale=10,
                        maxPixels=1e9,
                        bestEffort=True
                    ).get('NDVI'),
                    0
                )
                return ee.Feature(None, {'month': month, 'avg': mean_val})

            months = ee.List(list(range(1, 13)))
            trend_features = ee.FeatureCollection(months.map(get_monthly_ndvi)).getInfo()
            
            trend = []
            month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for f in trend_features['features']:
                m_idx = int(f['properties']['month'])
                val = f['properties'].get('avg')
                # If val is strictly numeric, round it, else 0. Handles None or empty dates gracefully.
                trend.append({
                    "month": month_names[m_idx],
                    "value": round(val, 3) if isinstance(val, (int, float)) else 0
                })

            # --- Pixel Distribution ---
            histogram = median_ndvi.reduceRegion(
                reducer=ee.Reducer.histogram(20),
                geometry=geometry,
                scale=10,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()
            
            raw_hist = format_ee_histogram(histogram, 'NDVI')
            total_pixels = sum([b['count'] for b in raw_hist])
            if total_pixels == 0: total_pixels = 1
            
            vh = sum([b['count'] for b in raw_hist if b['bin'] >= 0.8])
            h = sum([b['count'] for b in raw_hist if 0.6 <= b['bin'] < 0.8])
            mod = sum([b['count'] for b in raw_hist if 0.4 <= b['bin'] < 0.6])
            low = sum([b['count'] for b in raw_hist if b['bin'] < 0.4])
            
            distribution = [
                {"label": "Very High (>0.8)", "pct": round((vh/total_pixels)*100, 2), "amount": vh, "color": "#16a34a"},
                {"label": "High (0.6-0.8)", "pct": round((h/total_pixels)*100, 2), "amount": h, "color": "#4ade80"},
                {"label": "Moderate (0.4-0.6)", "pct": round((mod/total_pixels)*100, 2), "amount": mod, "color": "#fbbf24"},
                {"label": "Low (<0.4)", "pct": round((low/total_pixels)*100, 2), "amount": low, "color": "#ef4444"},
            ]

            return jsonify({
                "status": "success",
                "metric": "NDVI",
                "trend": trend,
                "distribution": distribution
            })
            
        elif metric == 'temperature':
            # MODIS 8-day LST (1km resolution)
            lst_col = ee.ImageCollection("MODIS/061/MOD11A2") \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date) \
                .select('LST_Day_1km')
                
            # Convert Kelvin -> Celsius: (val * 0.02) - 273.15
            def to_celsius(image):
                celsius = image.multiply(0.02).subtract(273.15).rename('TempC')
                return image.addBands(celsius)
                
            temp_col = lst_col.map(to_celsius).select('TempC')
            median_temp = temp_col.median()
            
            # --- 6-Month Trend ---
            def get_monthly_temp(month):
                m_start = ee.Date.fromYMD(year, month, 1)
                m_end = m_start.advance(1, 'month')
                m_median = temp_col.filterDate(m_start, m_end).median()
                
                mean_val = ee.Algorithms.If(
                    m_median.bandNames().size().gt(0),
                    m_median.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geometry,
                        scale=1000,
                        maxPixels=1e9,
                        bestEffort=True
                    ).get('TempC'),
                    0
                )
                return ee.Feature(None, {'month': month, 'avg': mean_val})

            months = ee.List(list(range(1, 13)))
            trend_features = ee.FeatureCollection(months.map(get_monthly_temp)).getInfo()
            
            trend = []
            month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for f in trend_features['features']:
                m_idx = int(f['properties']['month'])
                val = f['properties'].get('avg')
                trend.append({
                    "month": month_names[m_idx],
                    "value": round(val, 1) if isinstance(val, (int, float)) else 0
                })

            # --- Pixel Distribution ---
            histogram = median_temp.reduceRegion(
                reducer=ee.Reducer.histogram(20),
                geometry=geometry,
                scale=1000,
                maxPixels=1e9,
                bestEffort=True
            ).getInfo()
            
            raw_hist = format_ee_histogram(histogram, 'TempC')
            total_pixels = sum([b['count'] for b in raw_hist])
            if total_pixels == 0: total_pixels = 1
            
            vh = sum([b['count'] for b in raw_hist if b['bin'] >= 35])
            h = sum([b['count'] for b in raw_hist if 25 <= b['bin'] < 35])
            mod = sum([b['count'] for b in raw_hist if 15 <= b['bin'] < 25])
            low = sum([b['count'] for b in raw_hist if b['bin'] < 15])
            
            distribution = [
                {"label": "Very Hot (>35°C)", "pct": round((vh/total_pixels)*100, 2), "amount": vh, "color": "#ef4444"},
                {"label": "Hot (25-35°C)", "pct": round((h/total_pixels)*100, 2), "amount": h, "color": "#f97316"},
                {"label": "Warm (15-25°C)", "pct": round((mod/total_pixels)*100, 2), "amount": mod, "color": "#fbbf24"},
                {"label": "Cool (<15°C)", "pct": round((low/total_pixels)*100, 2), "amount": low, "color": "#3b82f6"},
            ]

            return jsonify({
                "status": "success",
                "metric": "Temperature",
                "trend": trend,
                "distribution": distribution
            })
            
        elif metric == 'landcover':
            # Google Dynamic World V1 (10m resolution, up to current year)
            dataset = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1") \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date)
                
            # Use mode to get the most frequent classification over the year
            image = dataset.select('label').mode()
            
            # Reduce with frequencyHistogram
            freq = ee.Algorithms.If(
                dataset.size().gt(0),
                image.reduceRegion(
                    reducer=ee.Reducer.frequencyHistogram(),
                    geometry=geometry,
                    scale=10,
                    maxPixels=1e9,
                    bestEffort=True
                ),
                ee.Dictionary({'label': {}})
            ).getInfo()
            
            class_counts = freq.get('label', {})
            total_pixels = sum(class_counts.values())
            if total_pixels == 0: total_pixels = 1
            
            # Mapping Dynamic World classes to human-readable names and colors
            dw_classes = {
                '0': {'name': 'Water', 'color': '#419BDF'},
                '1': {'name': 'Trees', 'color': '#397D49'},
                '2': {'name': 'Grass', 'color': '#88B053'},
                '3': {'name': 'Flooded vegetation', 'color': '#7A87C6'},
                '4': {'name': 'Crops', 'color': '#E49635'},
                '5': {'name': 'Shrub & Scrub', 'color': '#DFC35A'},
                '6': {'name': 'Built-up', 'color': '#C4281B'},
                '7': {'name': 'Bare', 'color': '#A59B8F'},
                '8': {'name': 'Snow & Ice', 'color': '#B39FE1'}
            }
            
            distribution = []
            for class_val, count in class_counts.items():
                meta = dw_classes.get(str(int(float(class_val))), {'name': 'Unknown', 'color': '#cccccc'})
                distribution.append({
                    "label": meta['name'],
                    "amount": round(count),
                    "pct": round((count / total_pixels) * 100, 2),
                    "color": meta['color']
                })
                
            # Sort by percentage descending
            distribution = sorted(distribution, key=lambda x: x['pct'], reverse=True)

            # Generate Tile URL for Leaflet
            viz = {
                'min': 0,
                'max': 8,
                'palette': ['419BDF', '397D49', '88B053', '7A87C6', 'E49635', 'DFC35A', 'C4281B', 'A59B8F', 'B39FE1']
            }
            map_info = image.clip(geometry).getMapId(viz)
            tile_url = map_info['tile_fetcher'].url_format

            return jsonify({
                "status": "success",
                "metric": "Land Cover",
                "distribution": distribution,
                "tile_url": tile_url
            })
            
        else:
            return jsonify({"error": "Metric not supported"}), 400
            
    except Exception as e:
        print(f"GEE Execution Error: {e}")
        return jsonify({
            "error": "Failed to compute GEE analytics",
            "message": "Computation failed on Earth Engine servers.",
            "details": str(e)
        }), 500


def format_ee_percentiles(ee_result, band_name):
    """Format GEE percentile output to a standard BoxPlot structure"""
    try:
        # ee_result might look like: {'NDVI': {'p0': 0.1, 'p25': 0.3, ...}} or flat keys depending on reducer
        return {
            "min": ee_result.get(f'{band_name}_p0', 0),
            "q1": ee_result.get(f'{band_name}_p25', 0),
            "median": ee_result.get(f'{band_name}_p50', 0),
            "q3": ee_result.get(f'{band_name}_p75', 0),
            "max": ee_result.get(f'{band_name}_p100', 0)
        }
    except:
        return None

def format_ee_histogram(ee_result, band_name):
    """Format GEE histogram output for Recharts"""
    try:
        hist_dict = ee_result.get(band_name, {})
        bucket_means = hist_dict.get('bucketMeans', [])
        histogram = hist_dict.get('histogram', [])
        
        formatted = []
        for i in range(len(bucket_means)):
            formatted.append({
                "bin": round(bucket_means[i], 2),
                "count": histogram[i]
            })
        return formatted
    except:
        return []
