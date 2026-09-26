import ee
import json
import os

try:
    sa_path = os.environ.get('GEE_SERVICE_ACCOUNT_PATH') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_path and os.path.exists(sa_path):
        with open(sa_path, 'r') as f:
            project_id = json.load(f).get('project_id')
            ee.Initialize(project=project_id)
except:
    pass

dummy = {"type": "Polygon", "coordinates": [[[0,0], [0,1], [1,1], [1,0], [0,0]]]}

print("Testing geometry parsing & reduction...")
try:
    geom = ee.Geometry(dummy)
    img = ee.Image.constant(1).rename('B1')
    res = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=geom, scale=10)
    print("Result:", res.getInfo())
except Exception as e:
    print("Error:", e)
