from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import DayPlan, Activity
from src.tools.amap import amap_poi_search, amap_poi_around, amap_distance, amap_direction
from src.tools.json_output import json_prompt, list_schema_of, parse_json

PROMPT = json_prompt(
     """按实际旅行天数生成每日行程。每天4-6个活动，覆盖所有天数。

【重要规则】
1. location 必须使用下方提供的真实POI名称，不能编造
2. transport 根据景点间实际距离填写（步行/驾车/地铁）
3. 餐饮活动必须引用下方给出的真实餐厅名称
4. 各项费用给出合理估算

每个 DayPlan:
- day_number: 第几天
- date: 日期
- title: 当天主题
- activities: 活动列表，每个：
  - time_slot: 时间段
  - description: 活动描述
  - location: 真实地点名称（必填）
  - poi_location: 真实经纬度 "lng,lat"（从下方数据获取）
  - duration_min: 时间（分钟）
  - cost: 费用（元）
  - transport: 交通方式""",
    list_schema_of(DayPlan)
)


def _parse_lnglat(loc: str) -> tuple[float, float] | None:
    """Parse 'lng,lat' string to (lng, lat) float tuple."""
    try:
        parts = loc.split(",")
        return float(parts[0]), float(parts[1])
    except (ValueError, IndexError):
        return None


def _nearest_neighbor_sort(attractions: list[dict]) -> list[dict]:
    """Sort attractions by geographic proximity (nearest neighbor)."""
    if len(attractions) <= 2:
        return attractions

    # Build list of (index, name, location, parsed_coords)
    items = []
    for i, a in enumerate(attractions):
        loc = a.get("location", "")
        coords = _parse_lnglat(loc)
        if coords:
            items.append({"idx": i, "name": a.get("name", ""), "location": loc, "coords": coords, "data": a})

    if len(items) <= 2:
        return attractions

    sorted_items = [items[0]]  # Start with first item
    remaining = items[1:]

    while remaining:
        last = sorted_items[-1]["coords"]
        # Find nearest remaining
        nearest_idx = 0
        nearest_dist = float("inf")
        for j, r in enumerate(remaining):
            dx = last[0] - r["coords"][0]
            dy = last[1] - r["coords"][1]
            dist = dx * dx + dy * dy  # squared distance, no sqrt needed
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = j
        sorted_items.append(remaining.pop(nearest_idx))

    # Rebuild attraction list in sorted order
    name_seen = set()
    result = []
    for item in sorted_items:
        if item["name"] not in name_seen:
            name_seen.add(item["name"])
            result.append(item["data"])
    # Add any that were lost (no coords)
    seen_names = {a.get("name", "") for a in result}
    for a in attractions:
        if a.get("name", "") not in seen_names:
            result.append(a)
            seen_names.add(a.get("name", ""))
    return result


def create_itinerary_agent(llm: DirectLLM):
    def itinerary_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")

        # Get attractions: use user-selected or auto-fetch
        attractions = []
        selected = req.get("selected_pois", [])
        if selected:
            # Use user-selected POIs
            for p in selected:
                if p.get("location"):
                    attractions.append({
                        "name": p.get("name", ""),
                        "location": p.get("location", ""),
                        "address": p.get("address", ""),
                        "type": p.get("type", "attraction"),
                    })
            attractions = _nearest_neighbor_sort(attractions)
        else:
            # Auto-fetch from Amap
            try:
                raw = amap_poi_search(f"{dest}景点", types="110200", city=dest, offset=10)
                attractions = _nearest_neighbor_sort(raw)
            except ValueError:
                pass

        # Fetch real nearby POIs with costs for dining/activities
        nearby_pois = {}
        attraction_costs = {}
        if attractions:
            # Fetch ticket prices for attractions
            for a in attractions[:6]:
                try:
                    detail = amap_poi_search(a.get("name", ""), city=dest, offset=1, extensions="all")
                    if detail and detail[0].get("cost"):
                        attraction_costs[a["name"]] = detail[0]["cost"]
                except ValueError:
                    pass

            locs = [a["location"] for a in attractions if a.get("location")]
            for i, a in enumerate(attractions[:8]):
                loc = a.get("location", "")
                if not loc:
                    continue
                try:
                    dinings = amap_poi_around(location=loc, types="050000", radius=800, offset=5)
                    shops = amap_poi_around(location=loc, types="060000", radius=500, offset=3)
                    rest_list = []
                    for d in dinings[:4]:
                        if d.get("name"):
                            entry = d["name"]
                            if d.get("distance"):
                                entry += f"({d['distance']}m)"
                            rest_list.append(entry)
                    nearby_pois[a.get("name", "")] = {
                        "restaurants": rest_list,
                        "shops": [s["name"] for s in shops[:2] if s.get("name")],
                    }
                except ValueError:
                    pass

        # Build optimized route text with REAL data
        dist_text = ""
        route_items = []
        if len(attractions) >= 2:
            locs = [a["location"] for a in attractions if a.get("location")]
            for i in range(min(len(locs) - 1, 8)):
                a, b = locs[i], locs[i + 1]
                if not a or not b:
                    continue
                routes = amap_distance(origins=a, destination=b)
                if routes:
                    d_km = round(int(routes[0]["distance_m"]) / 1000, 1)
                    t_min = round(int(routes[0]["duration_s"]) / 60)
                    line = f"{attractions[i]['name']} → {attractions[i+1]['name']}: {d_km}km 驾车{t_min}分钟"
                    if d_km < 3:
                        walk = amap_direction(origin=a, destination=b, mode="walking")
                        if walk:
                            w_min = round(int(walk[0]["duration_s"]) / 60)
                            line += f"｜步行{w_min}分钟"
                    route_items.append(line)
            if route_items:
                dist_text = "【景点间实际交通距离】\n" + "\n".join(route_items)

        # Build real cost context
        cost_parts = []
        if attraction_costs:
            cost_parts.append("【景点实际门票价格（元）】")
            for name, cost in attraction_costs.items():
                cost_parts.append(f"  {name}：{cost}元")

        if dining_recommendations := state.get("dining_recommendations"):
            if isinstance(dining_recommendations, list) and dining_recommendations:
                dp = [d.get("price_per_person", 0) for d in dining_recommendations if d.get("price_per_person")]
                if dp:
                    avg = sum(dp) / len(dp)
                    cost_parts.append(f"【周边餐厅人均消费】约{int(avg)}元")

        # Build real POI context for the LLM
        poi_context_parts = []
        if nearby_pois:
            poi_context_parts.append("【景点周边真实POI数据（请只使用以下真实名称）】")
            for attr_name, pois in nearby_pois.items():
                if pois["restaurants"]:
                    poi_context_parts.append(f"{attr_name}周边餐厅：{'、'.join(pois['restaurants'][:4])}")
                if pois["shops"]:
                    poi_context_parts.append(f"{attr_name}周边商店：{'、'.join(pois['shops'][:2])}")

        # Calculate number of days
        num_days = 3
        sd, ed = req.get("start_date", ""), req.get("end_date", "")
        if sd and ed:
            try:
                from datetime import datetime
                d1 = datetime.strptime(sd, "%Y-%m-%d")
                d2 = datetime.strptime(ed, "%Y-%m-%d")
                num_days = max(1, (d2 - d1).days)
            except: pass

        context = [
            f"目的地：{dest}",
            f"时间：{sd} → {ed}（共{num_days}天）",
            f"人数：{req.get('travelers',1)}",
            f"兴趣：{', '.join(req.get('interests',['观光']))}",
            f"预算：{req.get('budget','?')}元",
            f"【要求】请生成{num_days}天的行程，每天一个DayPlan，共{num_days}个DayPlan。",
        ]
        if dist_text:
            context.append(dist_text)
        if attractions:
            names = [a.get("name", "") for a in attractions]
            context.append(f"景点游览顺序（已按地理位置优化）：{' → '.join(names)}")
        if poi_context_parts:
            context.extend(poi_context_parts)
        if cost_parts:
            context.extend(cost_parts)
        for key, label in [("destination_research", "目的地研究")]:
            v = state.get(key)
            if v and isinstance(v, str) and v.startswith("{"):
                try:
                    import json
                    parsed = json.loads(v)
                    attrs = parsed.get("attractions", [])
                    if attrs:
                        context.append(f"推荐景点：{'、'.join(attrs[:5])}")
                except:
                    pass

        context.append("\n【规则】每个活动的 location 必须使用上面提供的真实POI名称，不能编造。")

        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content="\n".join(context))])
        result = parse_json(resp, DayPlan)
        if not isinstance(result, list): result = [result]

        # Build map_data from sorted attractions
        map_data = {"center": "", "markers": [], "routes": []}
        if attractions:
            locs = [a.get("location", "") for a in attractions if a.get("location")]
            if locs:
                map_data["center"] = locs[0]
                for i, a in enumerate(attractions):
                    poi_type = a.get("type", "attraction") or "attraction"
                    map_data["markers"].append({
                        "name": a.get("name", ""),
                        "location": a.get("location", ""),
                        "day": i + 1,
                        "type": poi_type,
                    })
            # Connect sorted attractions with mode based on straight-line distance
            for i in range(min(len(locs) - 1, 8)):
                a, b = locs[i], locs[i + 1]
                if not a or not b:
                    continue
                # Calculate Euclidean distance to decide mode
                coords_a = _parse_lnglat(a)
                coords_b = _parse_lnglat(b)
                is_walkable = False
                if coords_a and coords_b:
                    dx = (coords_a[0] - coords_b[0]) * 111320  # deg→m at ~40°N
                    dy = (coords_a[1] - coords_b[1]) * 111320
                    euclidean_m = (dx * dx + dy * dy) ** 0.5
                    is_walkable = euclidean_m < 2000  # <2km straight line

                if is_walkable:
                    walk = amap_direction(origin=a, destination=b, mode="walking")
                    if walk:
                        d_km = round(int(walk[0]["distance_m"]) / 1000, 1)
                        dur = round(int(walk[0]["duration_s"]) / 60)
                        map_data["routes"].append({
                            "from": attractions[i].get("name", ""),
                            "to": attractions[i + 1].get("name", ""),
                            "distance_km": d_km,
                            "duration_min": dur,
                            "from_loc": a, "to_loc": b,
                            "mode": "walking",
                        })
                else:
                    routes = amap_distance(origins=a, destination=b)
                    if routes:
                        r = routes[0]
                        map_data["routes"].append({
                            "from": attractions[i].get("name", ""),
                            "to": attractions[i + 1].get("name", ""),
                            "distance_km": round(int(r["distance_m"]) / 1000, 1),
                            "duration_min": round(int(r["duration_s"]) / 60),
                            "from_loc": a, "to_loc": b,
                            "mode": "driving",
                        })

        return {
            "itinerary": [r.model_dump() for r in result],
            "map_data": map_data,
            "completed_agents": ["itinerary"],
        }

    return itinerary_node
