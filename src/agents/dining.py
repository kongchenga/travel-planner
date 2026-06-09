from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import DiningOption
from src.tools.amap import amap_poi_search
from src.tools.json_output import json_prompt, list_schema_of, parse_json

PROMPT = json_prompt(
    """推荐3-5个餐厅，覆盖不同价位和特色，引用高德真实数据。

每个选项：
- name: 餐厅名称
- address: 地址
- cuisine: 菜系，如"北京菜/川菜/日料"
- price_per_person: 人均价格（元）
- rating: 评分（1-5）
- phone: 电话（如有）
- location: "lng,lat"（如有）""",
    list_schema_of(DiningOption)
)


def create_dining_agent(llm: DirectLLM):
    def dining_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")

        pois = []
        try:
            pois = amap_poi_search(f"{dest}美食", types="050000", city=dest, offset=6, extensions="all")
        except ValueError:
            pass
        tool = ""
        if pois:
            tool = "高德数据：\n" + "\n".join(
                f"- {p['name']} 地址:{p.get('address','')} 评分:{p.get('rating','')} 人均:{p.get('cost','')}元"
                for p in pois[:6]
            )
        else:
            tool = "（无实时数据，请根据知识推荐）"

        user = f"目的地：{dest}\n兴趣：{', '.join(req.get('interests',['观光']))}\n\n{tool}"
        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=user)])
        result = parse_json(resp, DiningOption)
        if not isinstance(result, list): result = [result]
        return {"dining_recommendations": [r.model_dump() for r in result], "completed_agents": ["dining"]}

    return dining_node
