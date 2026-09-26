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
    
    # Let's get the projection and type of the band
    info = meta_chm.getInfo()
    print("Band types:", info['bands'])
    
    # Get a few sample values without rounding
    pixel_array = ee.Image.pixelLonLat().addBands(meta_chm).toArray()
    sampled = pixel_array.reduceRegion(
        reducer=ee.Reducer.toList(),
        geometry=aoi,
        scale=3,
        maxPixels=100
    ).getInfo()
    
    arr_key = list(sampled.keys())[0]
    points = sampled.get(arr_key, [])
    
    valid = [p for p in points if p[2] > 0]
    for i in range(min(10, len(valid))):
        print(valid[i][2])
except Exception as e:
    print(f"Error: {e}")
