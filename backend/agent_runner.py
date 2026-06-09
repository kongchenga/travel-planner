import asyncio
import json
import logging
import os
import time
import uuid
from typing import AsyncGenerator

from dotenv import load_dotenv

from src.graph import create_travel_graph
from src.state import AgentState
from src.tools.llm import DirectLLM

load_dotenv()

log = logging.getLogger("agent_runner")

AGENT_LABELS = {
    "destination": "目的地研究",
    "flight": "航班搜索",
    "hotel": "住宿推荐",
    "dining": "美食推荐",
    "budget": "预算规划",
    "itinerary": "行程编排",
}

NODE_ORDER = ["destination", "flight", "hotel", "dining", "budget", "itinerary"]

DEFAULT_MAX_SESSIONS = 20
DEFAULT_SESSION_TTL = 1800


class AgentRunner:
    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS, session_ttl: int = DEFAULT_SESSION_TTL):
        self._sessions: dict[str, dict] = {}
        self._max = max_sessions
        self._ttl = session_ttl
        self._cancelled: set[str] = set()

    def _cleanup_expired(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if s.get("expires", 0) < now]
        for sid in expired:
            del self._sessions[sid]

    async def start_plan(self, travel_request: dict) -> str:
        self._cleanup_expired()
        if len(self._sessions) >= self._max:
            raise RuntimeError(f"Too many sessions ({len(self._sessions)} >= {self._max})")
        session_id = str(uuid.uuid4())[:8]
        queue: asyncio.Queue = asyncio.Queue()
        self._sessions[session_id] = {"queue": queue, "created_at": time.time(), "expires": time.time() + self._ttl}
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._run, session_id, travel_request, queue, loop)
        return session_id

    def _run(self, session_id, travel_request, queue, loop):
        try:
            if session_id in self._cancelled:
                return
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                self._put(queue, loop, ("error", {"message": "OPENAI_API_KEY not set"}))
                return

            llm = DirectLLM()
            graph = create_travel_graph(llm)

            initial: AgentState = {
                "messages": [],
                "travel_request": travel_request,
                "destination_research": "",
                "flight_options": [],
                "hotel_options": [],
                "dining_recommendations": [],
                "budget_plan": [],
                "itinerary": [],
                "map_data": {},
                "trip_plan": {},
                "completed_agents": [],
                "errors": [],
            }

            # Send agent_start for all 6 agents (for pipeline animation)
            for a in ["destination", "flight", "hotel", "dining", "budget", "itinerary"]:
                self._put(queue, loop, ("agent_start", {"agent": a, "label": AGENT_LABELS.get(a, a)}))

            for event in graph.stream(initial):
                if session_id in self._cancelled:
                    return

                for node_name, output in event.items():
                    if node_name == "finalize":
                        trip_plan = output.get("trip_plan", {})
                        self._put(queue, loop, (
                            "complete",
                            {"trip_plan": trip_plan, "map_data": trip_plan.get("map_data", {})},
                        ))
                    elif node_name == "parallel":
                        # Synthesize individual agent events from parallel output
                        agent_keys = {
                            "destination": "destination_research",
                            "flight": "flight_options",
                            "hotel": "hotel_options",
                            "dining": "dining_recommendations",
                        }
                        for agent_name, key in agent_keys.items():
                            raw = output.get(key)
                            if raw is not None or key in output:
                                content = _summarize_agent_output(agent_name, raw)
                                self._put(queue, loop, (
                                    "agent_complete",
                                    {"agent": agent_name, "label": AGENT_LABELS.get(agent_name, agent_name), "content": content},
                                ))
                    elif node_name == "budget":
                        raw = output.get("budget_plan", "")
                        content = _summarize_agent_output("budget", raw)
                        self._put(queue, loop, (
                            "agent_complete",
                            {"agent": "budget", "label": AGENT_LABELS["budget"], "content": content},
                        ))
                    elif node_name == "itinerary":
                        raw = output.get("itinerary", "")
                        content = _summarize_agent_output("itinerary", raw)
                        self._put(queue, loop, (
                            "agent_complete",
                            {"agent": "itinerary", "label": AGENT_LABELS["itinerary"], "content": content},
                        ))

        except Exception as e:
            msg = str(e)
            if "Expecting value" in msg or "JSONDecodeError" in msg:
                msg = "AI 返回格式异常，请重试"
            elif "rate limit" in msg.lower() or "429" in msg:
                msg = "请求过于频繁，请稍后重试"
            elif "timeout" in msg.lower():
                msg = "请求超时，请重试"
            log.error("session failed: %s - %s", session_id, str(e))
            self._put(queue, loop, ("error", {"message": msg}))
        finally:
            self._put(queue, loop, None)

    def _put(self, queue, loop, item):
        asyncio.run_coroutine_threadsafe(queue.put(item), loop)

    async def event_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        entry = self._sessions.get(session_id)
        if not entry:
            yield f"event: error\ndata: {json.dumps({'message': 'session not found'})}\n\n"
            return
        queue = entry["queue"]
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                event_type, data = event
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            self._cancelled.add(session_id)


def _summarize_agent_output(agent: str, raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, str):
        if raw.startswith("{"):
            return raw[:120]
        return raw
    if isinstance(raw, list):
        if agent == "flight":
            return " | ".join(f"{f.get('route','')} {f.get('price_estimate','')}元" for f in raw[:3])
        if agent == "hotel":
            return " | ".join(f"{h.get('name','')} ~{h.get('price_per_night','')}元/晚" for h in raw[:3])
        if agent == "dining":
            return " | ".join(f"{d.get('name','')} {d.get('price_per_person','')}元" for d in raw[:3])
        if agent == "budget":
            return " | ".join(f"{b.get('category','')} {b.get('amount','')}元" for b in raw[:5])
        if agent == "itinerary":
            return f"{len(raw)}天 " + " ".join(f"D{d.get('day_number','')}:{d.get('title','')}" for d in raw[:5])
        return str(raw)[:200]
    return str(raw)[:200]
