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
    "coordinates": [[[78.9629, 20.5937], [78.97, 20.5937], [78.97, 20.6], [78.9629, 20.6], [78.9629, 20.5937]]]
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
        scale=5,
        maxPixels=1e9
    ).getInfo()
    
    lons = sampled.get('longitude', [])
    lats = sampled.get('latitude', [])
    # Find the band name
    band_keys = [k for k in sampled.keys() if k not in ['longitude', 'latitude']]
    if band_keys:
        b_name = band_keys[0]
        vals = sampled.get(b_name, [])
        print(f"Sampled {len(vals)} points using reduceRegion toList")
        if len(vals) > 0:
            print(f"First point: lat={lats[0]}, lon={lons[0]}, val={vals[0]}")
    else:
        print("No band found")
except Exception as e:
    print(f"Error: {e}")
