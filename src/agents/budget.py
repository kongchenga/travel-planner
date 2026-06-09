from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import BudgetItem
from src.tools.json_output import json_prompt, list_schema_of, parse_json


PROMPT = json_prompt(
    """基于用户总预算和下方提供的真实价格数据，合理分配预算。

每个选项：
- category: 类别（"交通"/"住宿"/"餐饮"/"门票"/"购物"/"其他"）
- amount: 金额（元）
- percentage: 占总预算百分比（0-100，所有项之和应为100）

输出5-7个类别。""",
    list_schema_of(BudgetItem)
)


def create_budget_agent(llm: DirectLLM):
    def budget_node(state: AgentState) -> dict:
        req = state["travel_request"]
        total = req.get("budget", 5000)

        ctx = [f"总预算：{total}元"]
        ctx.append(f"人数：{req.get('travelers',1)}")
        ctx.append(f"天数：{req.get('start_date','?')} → {req.get('end_date','?')}")

        flights = state.get("flight_options") or []
        if isinstance(flights, list) and flights:
            prices = [f.get("price_estimate", 0) or 0 for f in flights if f.get("price_estimate")]
            if prices:
                ctx.append(f"\n航班参考价：{int(min(prices))}-{int(max(prices))}元/人")

        hotels = state.get("hotel_options") or []
        if isinstance(hotels, list) and hotels:
            hp = [h.get("price_per_night", 0) or 0 for h in hotels if h.get("price_per_night")]
            if hp:
                ctx.append(f"住宿参考价：{int(min(hp))}-{int(max(hp))}元/晚")

        dining = state.get("dining_recommendations") or []
        if isinstance(dining, list) and dining:
            dp = [d.get("price_per_person", 0) or 0 for d in dining if d.get("price_per_person")]
            if dp:
                ctx.append(f"餐饮参考价：{int(min(dp))}-{int(max(dp))}元/人")

        try:
            from src.tools.amap import amap_poi_search
            dest = req.get("destination", "")
            if dest:
                pois = amap_poi_search(dest + "景点", types="110200", city=dest, offset=5, extensions="all")
                tickets = [p.get("cost", "") for p in pois if p.get("cost")]
                if tickets:
                    ctx.append(f"门票参考价：{', '.join(tickets[:4])}元")
        except Exception:
            pass

        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content="\n".join(ctx))])
        result = parse_json(resp, BudgetItem)
        if not isinstance(result, list): result = [result]
        return {"budget_plan": [r.model_dump() for r in result], "completed_agents": ["budget"]}

    return budget_node
