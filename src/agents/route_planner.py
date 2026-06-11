"""Route planner agent — produces 2-3 diverse, budget-balanced route plans.

Replaces the old budget.py + itinerary.py with a single agent that:
1. Reads destination research (attractions), flights, hotels, dining options
2. Produces 2-3 route plans, each self-contained with its own budget, hotels, and itinerary
3. Ensures each plan totals within the user's budget
4. Each plan has a distinct theme (e.g., classic, luxury, budget, cultural)
"""

import json
import logging
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import RoutePlan
from src.tools.llm import DirectLLM
from src.tools.amap import (
    amap_poi_search, amap_poi_around, amap_poi_detail,
    amap_distance, amap_direction, amap_geocode, amap_polyline,
)
from src.tools.json_output import json_prompt, parse_json

log = logging.getLogger("route_planner")

ROUTE_SCHEMA = """
Return an ARRAY of 2-3 route objects. Each route object has:
- name: string, route label (e.g. "经典打卡路线", "性价比路线", "深度文化路线")
- description: string, one-line summary
- total_cost: number, sum of all costs in this route (MUST be <= total budget)
- flights: array of flight objects (pick 1 from the provided options, or reuse)
- hotels: array of hotel objects (pick 1 suitable hotel for this route from provided options)
- dining: array of dining objects (pick 3-5 suitable restaurants from provided options)
- budget: array of budget objects, each {category: string, amount: number, percentage: number (0-100)}
- days: array of day-plan objects, each {day_number: int, date: string, title: string, activities: array of {time_slot, description, location, poi_location, duration_min, cost, transport}}
- map_data: {center: string, markers: array of {name, location, day, type}, routes: array of {from, to, from_loc, to_loc, distance_km, duration_min, mode}}

【CRITICAL RULES】
1. Each route's total_cost MUST NOT exceed the overall budget
2. Different routes should use DIFFERENT attractions from the destination research list — spread them across routes! Route A uses the first 2-3 attractions, Route B uses the next 2-3, etc.
3. Hotels: assign a different hotel tier to each route (economy -> budget route, comfort -> mid, luxury -> high-end)
4. Restaurants: assign different restaurants to each route (don't reuse the same ones)
5. All activity locations MUST come from the provided real POI data
6. Each route's budget allocation MUST sum to its total_cost
7. Respond ONLY with valid JSON array
"""

PROMPT = json_prompt(
    """你是旅行路线规划专家。根据目的地研究结果、航班选项、酒店列表、餐厅列表，生成2-3条不同的旅行路线。

每条路线必须：
- 有独特的主题和风格
- 预算完全平衡（总花费 <= 用户总预算）
- 使用不同的景点组合（从目的地研究中分配）
- 使用不同的酒店（不同档次对应不同路线）
- 使用不同的餐厅
- 每天的行程4-6个活动，包含真实地点和时间段""",
    ROUTE_SCHEMA,
)


def _parse_lnglat(loc: str):
    try:
        parts = loc.split(",")
        return float(parts[0]), float(parts[1])
    except (ValueError, IndexError):
        return None


def _build_route_map_data(route: dict, dest_base_info: dict) -> dict:
    """Enrich a route with real map data from Amap: polyline routes, distances."""
    days = route.get("days", [])
    attractions = []
    seen_keys = set()
    skip_kw = ["机场", "航站楼", "火车", "寄存", "入住", "取行李", "返回", "早餐", "附近", "酒店附近"]
    for day in days:
        for act in day.get("activities", []):
            loc = act.get("location", "") or ""
            ploc = act.get("poi_location", "") or ""
            key = (loc, ploc)
            if loc and ploc and key not in seen_keys:
                skip = any(kw in loc for kw in skip_kw)
                if not skip:
                    seen_keys.add(key)
                    attractions.append({"name": loc, "location": ploc})

    md = {"center": "", "markers": [], "routes": []}
    if attractions:
        md["center"] = attractions[0]["location"]
        for i, a in enumerate(attractions):
            md["markers"].append({
                "name": a["name"],
                "location": a["location"],
                "day": i + 1,
                "type": "attraction",
            })

        # Use amap_distance to avoid slow polyline fetch during realtime
        locs = [a["location"] for a in attractions]
        import math
        for i in range(len(locs) - 1):
            a, b = locs[i], locs[i + 1]
            if not a or not b:
                continue
            ca, cb = _parse_lnglat(a), _parse_lnglat(b)
            is_walkable = False
            if ca and cb:
                lat_mid = (ca[1] + cb[1]) / 2
                dx = (ca[0] - cb[0]) * 111320 * math.cos(abs(lat_mid) * math.pi / 180)
                dy = (ca[1] - cb[1]) * 111320
                is_walkable = (dx * dx + dy * dy) ** 0.5 < 2000

            mode = "walking" if is_walkable else "driving"
            dist_result = amap_distance(origins=a, destination=b)
            d_km = 0
            dur = 0
            if dist_result:
                d_km = round(int(dist_result[0]["distance_m"]) / 1000, 1)
                dur = round(int(dist_result[0]["duration_s"]) / 60)

            md["routes"].append({
                "from": attractions[i]["name"], "to": attractions[i + 1]["name"],
                "from_loc": a, "to_loc": b,
                "distance_km": d_km, "duration_min": dur,
                "mode": mode,
                "polyline": [],
            })

        # One polyline call for the full route (lazily computed)
        coords_list = []
        for loc in locs:
            parsed = _parse_lnglat(loc)
            if parsed:
                coords_list.append([parsed[0], parsed[1]])
        if len(coords_list) >= 2:
            try:
                polyline = amap_polyline(coords_list)
                if polyline and md["routes"]:
                    md["routes"].append({
                        "from": attractions[0]["name"],
                        "to": attractions[-1]["name"],
                        "from_loc": attractions[0]["location"],
                        "to_loc": attractions[-1]["location"],
                        "distance_km": 0,
                        "duration_min": 0,
                        "mode": "driving",
                        "polyline": polyline,
                    })
            except Exception:
                pass

    return md


def _enrich_poi_locations(pois: list[dict], city: str):
    """Try to geocode POIs that don't have location data."""
    if not pois:
        return
    for p in pois:
        if p.get("location"):
            continue
        addr = p.get("address", "") or ""
        name = p.get("name", "") or ""
        if not addr and not name:
            continue
        try:
            geo = amap_geocode(f"{city}{name}" if name else addr, city=city)
            if geo:
                p["location"] = geo.get("location", "")
        except Exception:
            pass


def create_route_planner_agent(llm: DirectLLM):
    def route_planner_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")
        origin = req.get("origin", "出发地")
        budget_total = req.get("budget", 3000) or 3000
        travelers = req.get("travelers", 1)
        sd, ed = req.get("start_date", ""), req.get("end_date", "")

        num_days = 3
        if sd and ed:
            try:
                d1 = datetime.strptime(sd, "%Y-%m-%d")
                d2 = datetime.strptime(ed, "%Y-%m-%d")
                num_days = max(1, (d2 - d1).days + 1)
            except:
                pass

        # Parse destination research
        dest_info = {}
        dest_raw = state.get("destination_research", "{}") or "{}"
        if isinstance(dest_raw, str) and "{" in dest_raw:
            try:
                dest_info = json.loads(dest_raw)
            except json.JSONDecodeError:
                pass

        attractions_list = dest_info.get("attractions", []) or []

        # Flights
        flights = state.get("flight_options", []) or []
        if isinstance(flights, str):
            try:
                flights = json.loads(flights)
            except:
                flights = []

        # Hotels — fetch real geolocations
        hotels = state.get("hotel_options", []) or []
        if isinstance(hotels, str):
            try:
                hotels = json.loads(hotels)
            except:
                hotels = []
        _enrich_poi_locations(hotels, dest)

        # Dining — fetch real geolocations
        dining = state.get("dining_recommendations", []) or []
        if isinstance(dining, str):
            try:
                dining = json.loads(dining)
            except:
                dining = []
        _enrich_poi_locations(dining, dest)

        # Try to get real POI locations for attractions
        attraction_poi_data = []
        if attractions_list and dest:
            poi_pool = []
            seen = set()
            for a_name in attractions_list:
                if a_name in seen:
                    continue
                seen.add(a_name)
                try:
                    results = amap_poi_search(a_name, city=dest, offset=3, extensions="all")
                    for r in results:
                        if r.get("location"):
                            poi_pool.append(r)
                except ValueError:
                    pass
                try:
                    results2 = amap_poi_search(f"{dest}{a_name}", city=dest, offset=2, extensions="all")
                    for r in results2:
                        n = r.get("name", "")
                        if n not in seen and r.get("location"):
                            seen.add(n)
                            poi_pool.append(r)
                except ValueError:
                    pass

            for p in poi_pool[:20]:
                attraction_poi_data.append({
                    "name": p.get("name", ""),
                    "location": p.get("location", ""),
                    "address": p.get("address", ""),
                    "cost": p.get("cost", ""),
                    "rating": p.get("rating", ""),
                })

        # Build rich context for the LLM
        context_parts = []

        context_parts.append(f"目的地：{dest}")
        context_parts.append(f"出发地：{origin}")
        context_parts.append(f"日期：{sd} -> {ed}（共{num_days}天）")
        context_parts.append(f"人数：{travelers}")
        context_parts.append(f"总预算：{budget_total}元")
        context_parts.append(f"兴趣：{', '.join(req.get('interests', ['观光']))}")

        if dest_info.get("summary"):
            context_parts.append(f"\n目的地概况：{dest_info['summary']}")
        if dest_info.get("best_season"):
            context_parts.append(f"最佳季节：{dest_info['best_season']}")
        if dest_info.get("tips"):
            context_parts.append(f"贴士：{dest_info['tips']}")

        if attractions_list:
            context_parts.append(f"\n【必去景点列表（请分配到不同路线中）】")
            context_parts.append("  " + " | ".join(attractions_list))

        if attraction_poi_data:
            context_parts.append(f"\n【景点真实POI数据（共{len(attraction_poi_data)}个，定位和费用以这里为准）】")
            for a in attraction_poi_data:
                extra = ""
                if a.get("cost"):
                    extra += f" 门票{a['cost']}元"
                context_parts.append(f"  {a['name']} loc={a['location']} addr={a.get('address','')}{extra}")

        if flights:
            context_parts.append(f"\n【航班选项（每条路线选1个）】")
            for f in flights:
                context_parts.append(
                    f"  {f.get('airline','')} {f.get('route','')} "
                    f"Y{f.get('price_estimate','?')} {f.get('duration_min','?')}min "
                    f"{f.get('recommendation','')}"
                )

        if hotels:
            context_parts.append(f"\n【酒店选项（不同路线选不同酒店）】")
            for h in hotels:
                context_parts.append(
                    f"  {h.get('name','')} [{h.get('tier','comfort')}] "
                    f"Y{h.get('price_per_night','?')}/night star{h.get('rating','?')} "
                    f"addr={h.get('address','?')} loc={h.get('location','?')}"
                )

        if dining:
            context_parts.append(f"\n【餐厅选项（不同路线选不同餐厅）】")
            for d in dining:
                context_parts.append(
                    f"  {d.get('name','')} [{d.get('cuisine','?')}] "
                    f"Y{d.get('price_per_person','?')}/person star{d.get('rating','?')} "
                    f"addr={d.get('address','?')} loc={d.get('location','?')}"
                )

        context_parts.append(f"\n【要求】生成2-3条不同的路线，每条路线的total_cost <= {budget_total}元。")
        context_parts.append(f"【重要】行程共{num_days}天，每条路线必须精确包含{num_days}天的DayPlan，一天都不能少！")
        context_parts.append("每条路线每天4-5个活动，活动描述简洁即可（不超过15字）。")
        context_parts.append("请将景点分配到不同路线中。每条路线选不同的酒店和餐厅。")

        context = "\n".join(context_parts)

        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=context)])
        log.info("route_planner raw response length=%d first200=%s", len(resp), repr(resp[:200]))
        # Detect LLM error response
        if resp.startswith('{"error":'):
            log.error("route_planner: LLM returned error: %s", resp[:200])
            raise RuntimeError("LLM call failed: " + resp[:200])
        result = parse_json(resp, RoutePlan)
        if not isinstance(result, list):
            result = [result]

        # Filter out empty/broken routes
        valid_routes = []
        for r in result:
            rd = r.model_dump()
            if rd.get("name") and rd.get("days"):
                valid_routes.append(r)
            else:
                log.warning("route_planner: discarding empty route: name=%s days=%s",
                           repr(rd.get('name',''))[:30], len(rd.get('days', [])))

        if not valid_routes:
            log.warning("route_planner produced no valid routes (%d items), retrying once", len(result))
            retry_ctx = context + "\n\n[RETRY] Please output valid JSON array with 2 route objects. Each must have non-empty name and days fields. Each route must have exactly " + str(num_days) + " DayPlan objects in the days array."
            resp2 = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=retry_ctx)])
            if resp2.startswith('{"error":'):
                log.error("route_planner retry: LLM returned error: %s", resp2[:200])
                raise RuntimeError("LLM retry failed: " + resp2[:200])
            log.info("route_planner retry response length=%d", len(resp2))
            result2 = parse_json(resp2, RoutePlan)
            if isinstance(result2, list):
                for r2 in result2:
                    rd2 = r2.model_dump()
                    if rd2.get("name") and rd2.get("days"):
                        valid_routes.append(r2)
            elif result2.model_dump().get("name"):
                valid_routes.append(result2)

        # Filter routes with too few days
        valid_with_days = []
        for r in valid_routes:
            rd = r.model_dump()
            if len(rd.get("days", [])) >= num_days - 1:
                valid_with_days.append(r)
            else:
                log.warning("route_planner: route %s has only %d days, expected %d", rd.get("name"), len(rd.get("days", [])), num_days)
        if valid_with_days:
            valid_routes = valid_with_days

        if not valid_routes:
            log.error("route_planner: still no valid routes after retry, generating fallback")
            # Fallback: generate at least one basic route
            try:
                fallback = RoutePlan(
                    name=f"{dest}{num_days}日游",
                    description=f"自动生成的{num_days}日{dest}旅行路线",
                    total_cost=budget_total,
                    flights=flights[:1] if flights else [],
                    hotels=hotels[:1] if hotels else [],
                    dining=dining[:2] if dining else [],
                    budget=[],
                    days=[],
                    map_data={"center": "", "markers": [], "routes": []},
                )
                valid_routes = [fallback]
            except Exception:
                raise RuntimeError("Failed to generate any routes. Please try again.")

        # Enrich each route with real map data
        routes = []
        for r in valid_routes:
            route_dict = r.model_dump()
            total = route_dict.get("total_cost", 0)
            if total > budget_total:
                route_dict["total_cost"] = budget_total
                items = route_dict.get("budget", [])
                if items and total > 0:
                    scale = budget_total / total
                    for item in items:
                        item["amount"] = round(item.get("amount", 0) * scale, 0)
            elif total <= 0:
                route_dict["total_cost"] = budget_total

            try:
                md = _build_route_map_data(route_dict, dest_info)
                route_dict["map_data"] = md
            except Exception:
                pass

            routes.append(route_dict)

        return {"routes": routes, "completed_agents": ["route_planner"]}

    return route_planner_node
