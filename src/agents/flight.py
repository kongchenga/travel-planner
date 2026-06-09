from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import FlightOption
from src.tools.json_output import json_prompt, list_schema_of, parse_json

PROMPT = json_prompt(
    "推荐2-3个航班选项，覆盖不同价位。\n\n每个选项：\n- airline: 航空公司\n- route: 出发地→目的地\n- price_estimate: 预估单人价格（元）\n- duration_min: 飞行时长（分钟）\n- recommendation: 一句话推荐理由",
    list_schema_of(FlightOption)
)


def create_flight_agent(llm: DirectLLM):
    def flight_node(state: AgentState) -> dict:
        req = state["travel_request"]
        origin = req.get("origin", "未指定")
        dest = req.get("destination", "未指定")
        user = f"{origin} → {dest}\n日期：{req.get('start_date','?')} → {req.get('end_date','?')}\n人数：{req.get('travelers',1)}"
        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=user)])
        result = parse_json(resp, FlightOption)
        if not isinstance(result, list): result = [result]
        return {"flight_options": [r.model_dump() for r in result], "completed_agents": ["flight"]}

    return flight_node
