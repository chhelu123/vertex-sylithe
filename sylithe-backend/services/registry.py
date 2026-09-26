import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as http_requests

from config import CACHE_TTL_HOURS
from db import projects_collection

logger = logging.getLogger(__name__)

INDIAN_STATES = {
    "andhra pradesh": (15.9129, 79.7400), "arunachal pradesh": (28.2180, 94.7278),
    "assam": (26.2006, 92.9376), "bihar": (25.0961, 85.3131),
    "chhattisgarh": (21.2787, 81.8661), "goa": (15.2993, 74.1240),
    "gujarat": (22.3090, 72.1373), "haryana": (29.0588, 76.0856),
    "himachal pradesh": (31.1048, 77.1734), "jharkhand": (23.6102, 85.2799),
    "karnataka": (15.3173, 75.7139), "kerala": (10.8505, 76.2711),
    "madhya pradesh": (22.9734, 78.6569), "maharashtra": (19.7515, 75.7139),
    "manipur": (24.6637, 93.9063), "meghalaya": (25.4670, 91.3662),
    "mizoram": (23.1645, 92.9376), "nagaland": (26.1584, 94.5624),
    "odisha": (20.9517, 85.0985), "punjab": (31.1471, 75.3412),
    "rajasthan": (27.0238, 74.2179), "sikkim": (27.5330, 88.5122),
    "tamil nadu": (11.1271, 78.6569), "telangana": (18.1124, 79.0193),
    "tripura": (23.9408, 91.9882), "uttar pradesh": (26.8467, 80.9462),
    "uttarakhand": (30.0668, 79.0193), "west bengal": (22.9868, 87.8550),
    "delhi": (28.7041, 77.1025), "jammu and kashmir": (33.7782, 76.5762),
    "jammu & kashmir": (33.7782, 76.5762), "j&k": (33.7782, 76.5762),
    "ladakh": (34.1526, 77.5771), "chandigarh": (30.7333, 76.7794),
    "puducherry": (11.9416, 79.8083), "pondicherry": (11.9416, 79.8083),
    "andaman and nicobar": (11.7401, 92.6586), "andaman & nicobar": (11.7401, 92.6586),
    "dadra and nagar haveli": (20.1809, 73.0169), "daman and diu": (20.4283, 72.8397),
    "lakshadweep": (10.5667, 72.6417),
    "mumbai": (19.0760, 72.8777), "pune": (18.5204, 73.8567),
    "bangalore": (12.9716, 77.5946), "bengaluru": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707), "hyderabad": (17.3850, 78.4867),
    "kolkata": (22.5726, 88.3639), "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873), "lucknow": (26.8467, 80.9462),
    "bhopal": (23.2599, 77.4126), "nagpur": (21.1458, 79.0882),
    "indore": (22.7196, 75.8577), "surat": (21.1702, 72.8311),
    "raipur": (21.2514, 81.6296), "ranchi": (23.3441, 85.3096),
    "bhubaneswar": (20.2961, 85.8245), "dehradun": (30.3165, 78.0322),
    "shimla": (31.1048, 77.1734), "thiruvananthapuram": (8.5241, 76.9366),
    "kochi": (9.9312, 76.2673), "mangalore": (12.9141, 74.8560),
    "coimbatore": (11.0168, 76.9558), "madurai": (9.9252, 78.1198),
    "visakhapatnam": (17.6868, 83.2185), "vijayawada": (16.5062, 80.6480),
}


def extract_indian_state(text):
    if not text:
        return None, None, None
    text_lower = text.lower()
    sorted_states = sorted(INDIAN_STATES.keys(), key=len, reverse=True)
    for state_name in sorted_states:
        if state_name in text_lower:
            coords = INDIAN_STATES[state_name]
            return state_name.title(), coords[0], coords[1]
    return None, None, None


def fetch_verra_india() -> list:
    projects = []
    try:
        url = "https://registry.verra.org/uiapi/resource/resource/search"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://registry.verra.org/app/search/VCS/All%20Projects",
            "User-Agent": "Mozilla/5.0",
        }
        resp = http_requests.post(
            url,
            json={"program": "VCS", "resourceStatus": "", "size": 9999, "from": 0},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = [p for p in data.get("value", []) if p.get("country") == "India"]

        for item in items:
            start_year = None
            if item.get("creditingPeriodStartDate"):
                try:
                    start_year = int(item["creditingPeriodStartDate"][:4])
                except (ValueError, TypeError):
                    pass

            proj_name = item.get("resourceName", "").strip()
            proponent = item.get("proponent", "")
            state_name, lat, lng = extract_indian_state(proj_name)
            if not state_name:
                state_name, lat, lng = extract_indian_state(proponent)
            if not state_name:
                state_name = item.get("region", "") if item.get("region", "") != "Asia" else ""

            projects.append({
                "id": f"VCS-{item.get('resourceIdentifier', '')}",
                "registry": "Verra VCS",
                "name": proj_name,
                "type": item.get("protocolCategories", ""),
                "subtype": item.get("protocolSubCategories", ""),
                "country": "India",
                "state": state_name,
                "lat": lat,
                "lng": lng,
                "developer": proponent,
                "status": item.get("resourceStatus", ""),
                "validated_by": "",
                "start_year": start_year,
                "credits_issued": 0,
                "credits_retired": 0,
                "credits_available": 0,
                "annual_issuance_avg": 0,
                "sdg_goals": [],
                "standards": ["VCS"],
                "area_ha": item.get("estAnnualEmissionReductions"),
                "last_updated": (item.get("createDate") or "")[:10],
                "registry_url": f"https://registry.verra.org/app/projectDetail/VCS/{item.get('resourceIdentifier', '')}",
                "cached_at": datetime.now(timezone.utc),
            })

        logger.info(f"Fetched {len(projects)} projects from Verra")
    except Exception as e:
        logger.error(f"Verra fetch failed: {e}")

    return projects


def fetch_gold_standard_india() -> list:
    projects = []
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    base_url = "https://public-api.goldstandard.org/projects"

    def fetch_page(page):
        try:
            resp = http_requests.get(base_url, params={"page": page}, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    try:
        if not fetch_page(1):
            return projects

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {pool.submit(fetch_page, p): p for p in range(1, 201)}
            all_items = []
            for future in as_completed(futures):
                items = future.result()
                if items:
                    all_items.extend(items)

        for item in all_items:
            if item.get("country") != "India":
                continue

            start_year = None
            if item.get("crediting_period_start_date"):
                try:
                    start_year = int(item["crediting_period_start_date"][:4])
                except (ValueError, TypeError):
                    pass

            sdg_goals = [s.get("name", "") for s in item.get("sustainable_development_goals", [])]
            projects.append({
                "id": f"GS-{item.get('id', '')}",
                "registry": "Gold Standard",
                "name": item.get("name", "").strip(),
                "type": item.get("type", ""),
                "subtype": item.get("methodology") or "",
                "country": "India",
                "state": item.get("state") or "",
                "lat": item.get("latitude"),
                "lng": item.get("longitude"),
                "developer": item.get("project_developer", ""),
                "status": item.get("status", ""),
                "validated_by": "",
                "start_year": start_year,
                "credits_issued": item.get("estimated_annual_credits") or 0,
                "credits_retired": 0,
                "credits_available": item.get("estimated_annual_credits") or 0,
                "annual_issuance_avg": item.get("estimated_annual_credits") or 0,
                "sdg_goals": sdg_goals,
                "standards": ["Gold Standard"],
                "area_ha": None,
                "last_updated": (item.get("updated_at") or "")[:10],
                "registry_url": f"https://registry.goldstandard.org/projects/details/{item.get('id', '')}",
                "cached_at": datetime.now(timezone.utc),
            })

        logger.info(f"Fetched {len(projects)} projects from Gold Standard")
    except Exception as e:
        logger.error(f"Gold Standard fetch failed: {e}")

    return projects


def fetch_and_cache_all() -> int:
    all_projects = []
    all_projects.extend(fetch_verra_india())
    all_projects.extend(fetch_gold_standard_india())

    if all_projects:
        projects_collection.delete_many({"country": "India"})
        projects_collection.insert_many(all_projects)
        logger.info(f"Cached {len(all_projects)} total India projects")

    return len(all_projects)


_refresh_running = False

def ensure_projects_cached():
    global _refresh_running
    latest = projects_collection.find_one(
        {"country": "India"}, sort=[("cached_at", -1)]
    )
    if not latest:
        # No data at all — must block once to populate
        if not _refresh_running:
            fetch_and_cache_all()
        return

    age = datetime.now(timezone.utc) - latest["cached_at"].replace(tzinfo=timezone.utc)
    if age > timedelta(hours=CACHE_TTL_HOURS) and not _refresh_running:
        # Cache stale — refresh in background, serve existing data immediately
        from threading import Thread
        _refresh_running = True
        def _bg():
            global _refresh_running
            try:
                fetch_and_cache_all()
            finally:
                _refresh_running = False
        Thread(target=_bg, daemon=True).start()
