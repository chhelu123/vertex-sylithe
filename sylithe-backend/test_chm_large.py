import ee
import json
import os
from dotenv import load_dotenv

load_dotenv()

if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.environ.get('GEE_SERVICE_ACCOUNT_PATH'):
    if os.environ.get('GEE_SERVICE_ACCOUNT_PATH') and not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.environ.get('GEE_SERVICE_ACCOUNT_PATH')
    with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
        project_id = json.load(f).get('project_id')
    ee.Initialize(project=project_id)
else:
    ee.Initialize()

geojson = {
    "type": "Polygon",
    "coordinates": [[[78.96, 20.59], [78.98, 20.59], [78.98, 20.61], [78.96, 20.61], [78.96, 20.59]]]
}
aoi = ee.Geometry(geojson)

try:
    meta_chm = ee.ImageCollection('projects/meta-forest-monitoring-okw37/assets/CanopyHeight').mosaic().clip(aoi)
    chm_mask = meta_chm.gt(0)
    masked_chm = meta_chm.updateMask(chm_mask)

    pixel_coords = ee.Image.pixelLonLat().addBands(masked_chm)
    sampled = pixel_coords.reduceRegion(
        reducer=ee.Reducer.toList(),
        geometry=aoi,
        scale=3,
        maxPixels=1e9
    ).getInfo()
    
    lons = sampled.get('longitude', [])
    lats = sampled.get('latitude', [])
    
    band_keys = [k for k in sampled.keys() if k not in ['longitude', 'latitude']]
    if band_keys:
        b_name_sample = band_keys[0]
        vals = sampled.get(b_name_sample, [])
        valid_count = sum(1 for v in vals if v and v >= 2)
        print(f"Sampled {len(vals)} points, {valid_count} >= 2m")
except Exception as e:
    print(f"Error: {e}")
