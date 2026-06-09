from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import DestinationInfo
from src.tools.baidu_search import baidu_search
from src.tools.amap import amap_weather, amap_poi_search
from src.tools.json_output import json_prompt, json_schema_of, parse_json

PROMPT = json_prompt(
    """你是旅行目的地研究专家。基于工具数据和知识，填写目的地信息。

summary: 目的地一句话概况（10字内）
best_season: 最佳旅行季节（5字内）
attractions: 必去景点列表，5个左右（引用高德POI）
weather: 实时天气（如无则"未知"）
tips: 实用贴士（一句话）""",
    json_schema_of(DestinationInfo)
)


def create_destination_agent(llm: DirectLLM):
    def destination_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")

        tool_parts = []
        if dest:
            try:
                w = amap_weather(dest)
                if w:
                    tool_parts.append(f"天气：{w['city']} {w['weather']} {w['temperature']}°C")
            except ValueError:
                pass
            try:
                pois = amap_poi_search(f"{dest}景点", types="110200", city=dest, offset=5)
                if pois:
                    tool_parts.append("知名景点：" + "、".join(p["name"] for p in pois))
            except ValueError:
                pass
        tool_text = "\n".join(tool_parts) or "（无实时数据，请根据知识回答）"

        user = f"目的地：{dest}\n兴趣：{', '.join(req.get('interests',['观光']))}\n{tool_text}"
        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=user)])
        result = parse_json(resp, DestinationInfo)
        return {"destination_research": result.model_dump_json(), "completed_agents": ["destination"]}

    return destination_node
