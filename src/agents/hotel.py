from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import HotelOption
from src.tools.amap import amap_poi_search
from src.tools.json_output import json_prompt, list_schema_of, parse_json

PROMPT = json_prompt(
    "推荐3个不同档次的住宿选项（经济/舒适/豪华），引用高德真实数据。\n\n每个选项：\n- name: 酒店名称\n- address: 地址\n- price_per_night: 每晚价格（元）\n- rating: 评分（1-5）\n- tier: economy/comfort/luxury\n- phone: 电话（如有）\n- location: lng,lat（如有）",
    list_schema_of(HotelOption)
)


def create_hotel_agent(llm: DirectLLM):
    def hotel_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")

        pois = []
        try:
            pois = amap_poi_search(f"{dest}酒店", types="100000", city=dest, offset=6, extensions="all")
        except ValueError:
            pass
        tool = ""
        if pois:
            tool = "高德数据：\n" + "\n".join(
                f"- {p['name']} 地址:{p.get('address','')} 评分:{p.get('rating','')} 参考价:{p.get('cost','')}元"
                for p in pois[:6]
            )
        else:
            tool = "（无实时数据，请根据知识推荐）"

        user = f"目的地：{dest}\n预算：{req.get('budget','?')}元\n人数：{req.get('travelers',1)}\n\n{tool}"
        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=user)])
        result = parse_json(resp, HotelOption)
        if not isinstance(result, list): result = [result]
        return {"hotel_options": [r.model_dump() for r in result], "completed_agents": ["hotel"]}

    return hotel_node
