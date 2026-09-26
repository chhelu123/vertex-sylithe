import requests
import json

payload = {
    "year": 2023,
    "geojson": {
        "type": "Polygon",
        "coordinates": [[[78.9629, 20.5937], [78.9639, 20.5937], [78.9639, 20.5947], [78.9629, 20.5947], [78.9629, 20.5937]]]
    }
}

try:
    res = requests.post('http://127.0.0.1:5000/api/chm/predict', json=payload)
    data = res.json()
    points = data.get('results', {}).get('model_prediction', {}).get('points', [])
    print(f"Points count: {len(points)}")
    if len(points) > 0:
        print(f"First point: {points[0]}")
    else:
        print("Error or empty:")
        print(data)
except Exception as e:
    print(f"Request failed: {e}")
