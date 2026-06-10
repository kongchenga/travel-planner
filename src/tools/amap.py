"""Amap (高德地图) API tools — POI search, weather, distance, directions.

Register: https://lbs.amap.com/ -> 创建应用 -> 添加 Key（Web 服务类型）
Set env:  AMAP_KEY=your-key-here

POI type codes (常见):
  050000  餐饮         060000  购物             070000  生活服务
  080000  体育休闲     090000  医疗保健         100000  住宿
  110000  风景名胜     120000  商务住宅         130000  政府机构
  141200  旅游景点     150000  交通设施         160000  金融保险
  170000  公司企业     180000  道路附属         190000  地名地址

子类: 060100 超市 / 060200 便利店 / 110100 公园广场 / 110200 风景名胜
完整列表: https://lbs.amap.com/api/webservice/download
"""

import logging
import os
from typing import Optional

import requests

from .cache import cache_result
from .retry import retry_http

log = logging.getLogger("tools.amap")


POI_TYPES = {
    "餐饮": "050000",
    "中餐厅": "050100",
    "外国餐厅": "050200",
    "小吃": "050300",
    "购物": "060000",
    "超市": "060100",
    "便利店": "060200",
    "商场": "060300",
    "住宿": "100000",
    "酒店": "100100",
    "民宿": "100200",
    "风景名胜": "110000",
    "公园广场": "110100",
    "景点": "110200",
    "旅游": "141200",
}


def _get_key() -> str:
    key = os.getenv("AMAP_KEY")
    if not key:
        raise ValueError("AMAP_KEY not set. Register at https://lbs.amap.com/")
    return key


def _request(path: str, params: dict) -> Optional[dict]:
    """Low-level Amap API request with error handling."""
    params["key"] = _get_key()
    params["output"] = "JSON"
    try:
        resp = requests.get(
            f"https://restapi.amap.com/v3/{path}",
            params=params,
            timeout=10,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("Amap request failed: %s - %s", path, e)
        return None

    if data.get("status") != "1":
        log.warning("Amap API error: %s - %s", path, data.get("info", ""))
        return None

    return data


@cache_result(ttl=3600)
@retry_http
def amap_poi_search(
    keywords: str,
    city: str = "",
    types: str = "",
    offset: int = 10,
    page: int = 1,
    extensions: str = "base",
) -> list[dict]:
    """Text search POIs. Returns list of {name, address, location, tel, type, ...}.

    Args:
        keywords: Search keywords, e.g. "北京故宫".
        city: City name or adcode. Empty = nationwide.
        types: POI type code, e.g. "100000" for hotels, "110200" for attractions.
        offset: Results per page (max 25).
        page: Page number (default 1).
        extensions: "base" (basic) or "all" (includes photos, rating, open_time).

    Returns:
        List of POI dicts.
    """
    data = _request("place/text", {
        "keywords": keywords,
        "city": city,
        "offset": min(offset, 25),
        "page": page,
        "extensions": extensions,
        "types": types,
    })
    if not data:
        return []

    pois = []
    for poi in data.get("pois", []):
        entry = {
            "id": poi.get("id", ""),
            "name": poi.get("name", ""),
            "address": poi.get("address", ""),
            "location": poi.get("location", ""),
            "tel": poi.get("tel", ""),
            "type": poi.get("type", ""),
            "distance": poi.get("distance", ""),
            "biz_area": poi.get("biz_area", ""),
            "adname": poi.get("adname", ""),
        }
        if extensions == "all":
            entry.update({
                "website": poi.get("website", ""),
                "rating": poi.get("biz_ext", {}).get("rating", ""),
                "cost": poi.get("biz_ext", {}).get("cost", ""),
                "open_time": poi.get("biz_ext", {}).get("opentime", ""),
            })
        pois.append(entry)
    return pois


@cache_result(ttl=3600)
@retry_http
def amap_poi_around(
    location: str,
    keywords: str = "",
    types: str = "",
    radius: int = 1000,
    offset: int = 10,
) -> list[dict]:
    """Search POIs near a location (周边搜索). Useful for "景点附近有什么餐厅/酒店".

    Args:
        location: "lng,lat" coordinate.
        keywords: Optional keywords.
        types: POI type code.
        radius: Search radius in meters (default 1000, max 50000).
        offset: Results per page (max 25).

    Returns:
        List of POI dicts with distance from center.
    """
    data = _request("place/around", {
        "location": location,
        "keywords": keywords,
        "types": types,
        "radius": min(radius, 50000),
        "offset": min(offset, 25),
        "page": 1,
        "extensions": "base",
    })
    if not data:
        return []

    pois = []
    for poi in data.get("pois", []):
        pois.append({
            "name": poi.get("name", ""),
            "address": poi.get("address", ""),
            "location": poi.get("location", ""),
            "tel": poi.get("tel", ""),
            "type": poi.get("type", ""),
            "distance": poi.get("distance", ""),  # meters from center
        })
    return pois


@cache_result(ttl=86400)
@retry_http
def amap_poi_detail(poi_id: str) -> Optional[dict]:
    """Get detailed info for a specific POI by ID.

    Args:
        poi_id: POI ID from search results, e.g. "B0FFHXQS6C".

    Returns:
        Single POI dict with all available fields.
    """
    data = _request("place/detail", {
        "id": poi_id,
    })
    if not data:
        return None

    pois = data.get("pois", [])
    if not pois:
        return None

    p = pois[0]
    biz = p.get("biz_ext", {})
    return {
        "name": p.get("name", ""),
        "address": p.get("address", ""),
        "location": p.get("location", ""),
        "tel": p.get("tel", ""),
        "type": p.get("type", ""),
        "website": p.get("website", ""),
        "rating": biz.get("rating", ""),
        "cost": biz.get("cost", ""),
        "open_time": biz.get("opentime2", ""),
        "photos": [img.get("url", "") for img in p.get("photos", [])[:5]],
        "adname": p.get("adname", ""),
    }


@cache_result(ttl=1800)
@retry_http
def amap_weather(city: str) -> Optional[dict]:
    """Query live weather. city can be name ("北京市") or adcode ("110000")."""
    data = _request("weather/weatherInfo", {
        "city": city,
        "extensions": "base",
    })
    if not data:
        return None

    lives = data.get("lives", [])
    if not lives:
        return None

    w = lives[0]
    return {
        "city": w.get("city", ""),
        "weather": w.get("weather", ""),
        "temperature": w.get("temperature", ""),
        "wind_direction": w.get("winddirection", ""),
        "wind_power": w.get("windpower", ""),
        "humidity": w.get("humidity", ""),
        "report_time": w.get("reporttime", ""),
    }


@cache_result(ttl=86400)
@retry_http
def amap_distance(
    origins: str,
    destination: str,
    waypoints: str = "",
    strategy: int = 0,
) -> list[dict]:
    """Driving distance between points.

    Args:
        origins: "lng,lat" (or multiple "x1,y1|x2,y2" for vehicle heading)
        destination: "lng,lat"
        waypoints: "lng,lat;lng,lat" (max 16)
        strategy: 0=(default) speed first, 10=avoid congestion, 13=no highway, 19=highway first

    Returns:
        [{distance_m, duration_s, tolls, steps, strategy, taxi_cost}]
    """
    params = {
        "origin": origins,
        "destination": destination,
        "strategy": strategy,
        "extensions": "base",
    }
    if waypoints:
        params["waypoints"] = waypoints

    data = _request("direction/driving", params)
    if not data:
        return []

    route_info = data.get("route", {})
    taxi_cost = route_info.get("taxi_cost", "")
    results = []
    for path in route_info.get("paths", []):
        results.append({
            "distance_m": path.get("distance", ""),
            "duration_s": path.get("duration", ""),
            "tolls": path.get("tolls", ""),
            "steps": len(path.get("steps", [])),
            "strategy": strategy,
            "taxi_cost": taxi_cost,
        })
    return results


@cache_result(ttl=86400)
@retry_http
def amap_direction(
    origin: str,
    destination: str,
    city: str = "",
    cityd: str = "",
    waypoints: str = "",
    mode: str = "driving",
    strategy: int = 0,
    date: str = "",
    time: str = "",
) -> list[dict]:
    """Multi-mode route planning between two coordinates.

    Args:
        origin: "lng,lat"
        destination: "lng,lat"
        city: Required for transit — city name or adcode, e.g. "010" or "北京市".
        cityd: Destination city for cross-city transit.
        waypoints: Driving only — "lng,lat;lng,lat" (max 16).
        mode: "driving" | "walking" | "transit" | "bicycling"
        strategy:
            Driving: 0=fast, 10=avoid congestion, 13=no highway, 19=highway first.
            Transit: 0=fastest, 1=cheapest, 2=min transfers, 3=min walk, 5=no subway.
        date: Transit only — "2026-06-01".
        time: Transit only — "08:00".

    Returns:
        [{distance_m, duration_s, mode, strategy, tolls/cost, ...}]
    """
    api_paths = {
        "driving": "direction/driving",
        "walking": "direction/walking",
        "bicycling": "direction/bicycling",
        "transit": "direction/transit/integrated",
    }
    path = api_paths.get(mode, "direction/driving")

    params = {
        "origin": origin,
        "destination": destination,
        "strategy": strategy,
        "extensions": "base",
    }
    if waypoints:
        params["waypoints"] = waypoints

    if mode == "transit":
        if not city:
            return []
        params["city"] = city
        if cityd:
            params["cityd"] = cityd
        if date:
            params["date"] = date
        if time:
            params["time"] = time

    data = _request(path, params)
    if not data:
        return []

    route_key = "routes" if mode == "transit" else "paths"
    results = []

    if mode == "transit":
        for t in data.get("route", {}).get("transits", []):
            segments = []
            for seg in t.get("segments", []):
                if "walking" in seg:
                    w = seg["walking"]
                    segments.append({
                        "type": "walking",
                        "distance_m": w.get("distance", ""),
                        "duration_s": w.get("duration", ""),
                    })
                if "bus" in seg:
                    buslines = seg["bus"].get("buslines", [])
                    if buslines:
                        bus = buslines[0]
                        segments.append({
                            "type": "bus" if "公交" in bus.get("name", "") or "路" in bus.get("name", "") else "subway",
                            "name": bus.get("name", ""),
                            "depart": bus.get("departure_stop", {}).get("name", ""),
                            "arrive": bus.get("arrival_stop", {}).get("name", ""),
                            "distance_m": bus.get("distance", ""),
                            "duration_s": bus.get("duration", ""),
                        })
            results.append({
                "distance_m": t.get("distance", ""),
                "duration_s": t.get("duration", ""),
                "cost": t.get("cost", ""),
                "walking_distance_m": t.get("walking_distance", ""),
                "mode": "transit",
                "strategy": strategy,
                "segments": segments,
            })
    else:
        for route in data.get("route", {}).get(route_key, []):
            # Extract polyline from steps
            polyline = []
            for step in route.get("steps", []):
                poly = step.get("polyline", "")
                if poly:
                    for pt in poly.split(";"):
                        parts = pt.split(",")
                        if len(parts) == 2:
                            try:
                                polyline.append([float(parts[1]), float(parts[0])])
                            except ValueError:
                                pass
            results.append({
                "distance_m": route.get("distance", ""),
                "duration_s": route.get("duration", ""),
                "tolls": route.get("tolls", ""),
                "mode": mode,
                "strategy": strategy,
                "steps": len(route.get("steps", [])),
                "polyline": polyline,  # [[lat, lng], ...]
            })
    return results


def amap_polyline(coords: list[list[float]]) -> list[list[float]]:
    """Convert Amap polyline from step polylines to [[lat,lng],...] route.
    This calls the driving direction API with extensions=all to get the full polyline.
    """
    if not coords or len(coords) < 2:
        return []
    origin = ",".join(str(c) for c in coords[0])
    destination = ",".join(str(c) for c in coords[-1])
    ways = ""
    if len(coords) > 2:
        ways = ";".join(",".join(str(c) for c in pt) for pt in coords[1:-1])

    params = {"origin": origin, "destination": destination, "extensions": "all", "strategy": 0}
    if ways:
        params["waypoints"] = ways

    data = _request("direction/driving", params)
    if not data:
        return []
    route_data = data.get("route", {})
    paths = route_data.get("paths", [])
    if not paths:
        return []

    polyline = []
    for step in paths[0].get("steps", []):
        poly = step.get("polyline", "")
        if poly:
            for pt in poly.split(";"):
                parts = pt.split(",")
                if len(parts) == 2:
                    try:
                        polyline.append([float(parts[1]), float(parts[0])])
                    except ValueError:
                        pass
    return polyline


@cache_result(ttl=86400)
@retry_http
def amap_geocode(address: str, city: str = "") -> Optional[dict]:
    """Convert address text to coordinates."""
    data = _request("geocode/geo", {"address": address, "city": city})
    if not data:
        return None
    geocodes = data.get("geocodes", [])
    if not geocodes:
        return None
    g = geocodes[0]
    return {
        "location": g.get("location", ""),
        "address": g.get("formatted_address", ""),
    }
