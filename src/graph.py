import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import StateGraph, START, END
from src.tools.llm import DirectLLM
from src.state import AgentState
from src.agents.destination import create_destination_agent
from src.agents.flight import create_flight_agent
from src.agents.hotel import create_hotel_agent
from src.agents.dining import create_dining_agent
from src.agents.route_planner import create_route_planner_agent
from src.schemas import TripPlan, RoutePlan
from src.tools.amap import amap_geocode

log = logging.getLogger("graph")


def create_travel_graph(llm: DirectLLM) -> StateGraph:
    da = create_destination_agent(llm)
    fa = create_flight_agent(llm)
    ha = create_hotel_agent(llm)
    dia = create_dining_agent(llm)
    rpa = create_route_planner_agent(llm)

    def parallel_agents(state):
        out = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            fs = {
                pool.submit(da, state): "dest",
                pool.submit(fa, state): "flight",
                pool.submit(ha, state): "hotel",
                pool.submit(dia, state): "dining",
            }
            for f in as_completed(fs):
                try:
                    out.update(f.result())
                except Exception as e:
                    log.error("parallel agent %s failed: %s", fs[f], e)
        return out

    def compile_plan(state):
        req = state["travel_request"]
        dd = req.get("destination", "")
        dest_info = {}
        raw = state.get("destination_research", "{}")
        if isinstance(raw, str) and raw.startswith("{"):
            try:
                dest_info = json.loads(raw)
            except json.JSONDecodeError:
                pass

        routes = state.get("routes", []) or []
        if isinstance(routes, str):
            try:
                routes = json.loads(routes)
            except Exception as e:
                log.error("compile_plan: failed to parse routes json: %s", e)
                routes = []
        if not isinstance(routes, list):
            log.error("compile_plan: routes is not a list, got %s", type(routes).__name__)
            routes = []

        # For each route: geocode hotel/dining locations, normalize map_data
        for route in routes:
            if not isinstance(route, dict):
                log.warning("compile_plan: skipping non-dict route: %s", type(route).__name__)
                continue
            md = route.get("map_data", {})
            if "markers" not in md:
                md["markers"] = []

            for h in (route.get("hotels") or []):
                loc = h.get("location", "") or ""
                if not loc and h.get("address"):
                    try:
                        geo = amap_geocode(h["address"], city=dd or "")
                        if geo:
                            loc = geo.get("location", "")
                            h["location"] = loc
                    except:
                        pass
                if loc and h.get("name"):
                    md["markers"].append({"name": h["name"], "location": loc, "day": 0, "type": "hotel"})

            for d in (route.get("dining") or []):
                loc = d.get("location", "") or ""
                if not loc and d.get("address"):
                    try:
                        geo = amap_geocode(d["address"], city=dd or "")
                        if geo:
                            loc = geo.get("location", "")
                            d["location"] = loc
                    except:
                        pass
                if loc and d.get("name"):
                    md["markers"].append({"name": d["name"], "location": loc, "day": 0, "type": "restaurant"})

        # Build RoutePlan objects
        route_plans = []
        for r in routes:
            route_plans.append(RoutePlan(
                name=r.get("name", ""),
                description=r.get("description", ""),
                total_cost=r.get("total_cost", 0),
                flights=r.get("flights", []),
                hotels=r.get("hotels", []),
                dining=r.get("dining", []),
                budget=r.get("budget", []),
                days=r.get("days", []),
                map_data=r.get("map_data", {}),
            ))

        plan = TripPlan(
            destination=dd or "", origin=req.get("origin") or "",
            travelers=req.get("travelers", 1), total_budget=req.get("budget", 0) or 0,
            currency=req.get("currency", "CNY"),
            start_date=req.get("start_date") or "", end_date=req.get("end_date") or "",
            destination_info={
                "summary": dest_info.get("summary", ""),
                "best_season": dest_info.get("best_season", ""),
                "attractions": dest_info.get("attractions", []),
                "weather": dest_info.get("weather", ""),
                "tips": dest_info.get("tips", ""),
            },
            routes=[r.model_dump(mode="json") for r in route_plans],
        )
        return {"trip_plan": plan.model_dump(mode="json")}

    builder = StateGraph(AgentState)
    builder.add_node("parallel", parallel_agents)
    builder.add_node("route_planner", lambda s: rpa(s))
    builder.add_node("finalize", compile_plan)

    builder.add_edge(START, "parallel")
    builder.add_edge("parallel", "route_planner")
    builder.add_edge("route_planner", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()
