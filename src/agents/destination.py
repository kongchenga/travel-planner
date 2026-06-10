from src.tools.llm import DirectLLM
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState
from src.schemas import DestinationInfo
from src.tools.baidu_search import baidu_search
from src.tools.amap import amap_weather, amap_poi_search
from src.tools.json_output import json_prompt, json_schema_of, parse_json

PROMPT = json_prompt(
    """你是旅行目的地研究专家。下方会提供目的地、天气、以及高德地图POI数据。

【景点选择规则（按优先级执行）】
1. 如果高德POI数据中有知名景点（如"西湖""故宫""东方明珠"等），直接使用
2. 如果高德POI数据质量差（都是些公园/商业区/学校等非核心景点），则基于你的旅游知识填写5个该城市最经典的必去景点
3. 无论来源如何，attractions必须是该城市游客真正会去的地方，不要凑数

summary: 目的地一句话概况（10字内）
best_season: 最佳旅行季节（5字内）
attractions: 5个必去景点，必须是真实存在的知名景点名称
weather: 实时天气（如无则"未知"）
tips: 实用贴士（一句话）""",
    json_schema_of(DestinationInfo)
)

# Keywords that strongly suggest a place is a real tourist attraction
_ATTRACTION_SCORE = {
    "西湖": 100, "灵隐寺": 100, "雷峰塔": 100, "千岛湖": 100, "宋城": 100,
    "故宫": 100, "长城": 100, "天安门": 100, "颐和园": 100, "天坛": 100,
    "东方明珠": 100, "外滩": 100, "豫园": 100, "迪士尼": 100, "南京路": 95,
    "兵马俑": 100, "大雁塔": 100, "华山": 100, "城墙": 95,
    "大熊猫": 100, "都江堰": 100, "青城山": 100, "宽窄巷子": 95, "锦里": 95,
    "西湖": 100, "漓江": 100, "阳朔": 100, "龙脊": 98,
    "夫子庙": 100, "中山陵": 100, "总统府": 100, "玄武湖": 98,
    "鼓浪屿": 100, "武夷山": 100, "土楼": 98,
    "拙政园": 100, "留园": 100, "虎丘": 100, "周庄": 100, "太湖": 95,
    "泰山": 100, "崂山": 100, "趵突泉": 100, "大明湖": 98,
    "黄鹤楼": 100, "长江大桥": 98, "东湖": 95, "武大": 95,
    "布达拉宫": 100, "大昭寺": 100, "纳木错": 100,
    "茶卡盐湖": 100, "青海湖": 100, "莫高窟": 100, "鸣沙山": 100,
    "石林": 100, "大理": 100, "丽江": 100, "玉龙雪山": 100,
    "天涯海角": 100, "南山寺": 98, "亚龙湾": 100,
    "栈桥": 98, "八大关": 98, "啤酒博物馆": 98,
    "磁器口": 98, "洪崖洞": 100, "解放碑": 98, "武隆": 100,
}

# Keywords that suggest a place is NOT a core tourist attraction
_UNLIKELY_ATTRACTION = (
    "公园", "广场", "街区", "码头", "教堂", "步道", "绿道",
    "路", "街", "桥", "大道", "学校", "大学", "学院",
    "科技馆", "会展", "中心", "新城", "社区", "小区",
    "CBD", "商业", "购物", "乐园", "幼儿园", "道",
    "弄", "巷", "花园", "大厦", "公寓",
)


def _is_good_attraction(poi: dict) -> tuple[bool, int]:
    """Return (is_good, score) for a POI. Score 0-100, higher = more likely a real attraction."""
    name = poi.get("name", "")
    typ = poi.get("type", "")

    # Direct keyword match against known attractions
    for kw, score in _ATTRACTION_SCORE.items():
        if kw in name:
            return True, score

    # Reject by keyword blacklist
    for bad in _UNLIKELY_ATTRACTION:
        if bad in name:
            return False, 0

    # Type-based scoring
    if "风景名胜" in typ:
        return True, 70
    if "旅游景点" in typ:
        return True, 60

    # Default: accept but low confidence
    return True, 30


def create_destination_agent(llm: DirectLLM):
    def destination_node(state: AgentState) -> dict:
        req = state["travel_request"]
        dest = req.get("destination", "")

        tool_parts = []
        if dest:
            # Weather
            try:
                w = amap_weather(dest)
                if w:
                    tool_parts.append(f"天气：{w['city']} {w['weather']} {w['temperature']}°C")
            except ValueError:
                pass

            # POI — collect from multiple type codes, score and rank
            all_pois = []
            seen_names = set()
            try:
                for types_code in ("110000", "141200"):
                    batch = amap_poi_search(dest, types=types_code, city=dest, offset=10, extensions="all")
                    for p in batch:
                        name = p.get("name", "")
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        good, score = _is_good_attraction(p)
                        if good:
                            all_pois.append((score, p))
            except ValueError:
                pass

            # Sort by score descending, take top 12
            all_pois.sort(key=lambda x: x[0], reverse=True)
            top_pois = [p for _, p in all_pois[:12]]

            if top_pois:
                poi_texts = []
                for p in top_pois:
                    extra_parts = []
                    if p.get("rating"):
                        extra_parts.append(f"⭐{p['rating']}")
                    if p.get("cost"):
                        extra_parts.append(f"门票{p['cost']}元")
                    extra = " ".join(extra_parts)
                    addr = p.get("address", "") or p.get("adname", "")
                    poi_texts.append(f"  - {p['name']}" + (f"（{addr}）" if addr else "") + (f" [{extra}]" if extra else ""))
                tool_parts.append(f"高德POI（{len(top_pois)}个，仅供参考，如质量差请使用你的知识）：\n" + "\n".join(poi_texts))

        tool_text = "\n".join(tool_parts) or "（无实时数据，请根据你的旅游知识回答）"

        user = f"目的地：{dest}\n兴趣：{', '.join(req.get('interests',['观光']))}\n{tool_text}"
        resp = llm.invoke([SystemMessage(content=PROMPT), HumanMessage(content=user)])
        result = parse_json(resp, DestinationInfo)
        return {"destination_research": result.model_dump_json(), "completed_agents": ["destination"]}

    return destination_node
