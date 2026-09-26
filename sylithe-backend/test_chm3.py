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

    pixel_array = ee.Image.pixelLonLat().addBands(masked_chm).toArray()
    
    sampled = pixel_array.reduceRegion(
        reducer=ee.Reducer.toList(),
        geometry=aoi,
        scale=3,
        maxPixels=1e9
    ).getInfo()
    
    # It will return a single key "array"
    arr_key = list(sampled.keys())[0]
    points = sampled.get(arr_key, [])
    
    valid = [p for p in points if p[2] >= 2]
    
    print(f"Total points: {len(points)}, Valid: {len(valid)}")
    if len(valid) > 0:
        print(f"First valid point: lon={valid[0][0]}, lat={valid[0][1]}, height={valid[0][2]}")
except Exception as e:
    print(f"Error: {e}")
