# Travel Planner

AI 驱动的智能旅行规划助手，基于多 Agent 协作架构，提供一站式行程规划服务。

[![Python](https://img.shields.io/badge/python-3.14-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 架构

```
用户输入 → Orchestrator Agent → 多 Agent 并行规划 → 聚合输出
                                    ↓
        ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    Destination  Flight     Hotel     Dining    Budget
      Agent      Agent      Agent      Agent     Agent
        ↓          ↓          ↓          ↓          ↓
    ┌──────────────────────────────────────────────────────┐
    │              工具层（高德地图 / 百度搜索 / LLM）               │
    └──────────────────────────────────────────────────────┘
```

## 核心特性

- **多 Agent 协作**：6 个专业 Agent（目的地、机票、酒店、餐饮、预算、行程）并行工作
- **图状态编排**：基于 LangGraph 的状态机驱动多步推理流程
- **实时数据**：对接高德地图 API（POI 搜索、路线规划）+ 百度搜索
- **Web 界面**：响应式前端，支持地图可视化
- **LLM 驱动**：接入 DeepSeek 大模型进行智能决策与自然语言理解

## 快速开始

```bash
pip install -r requirements.txt

# 设置 API Key
set DEEPSEEK_API_KEY=your_key
set AMAP_KEY=your_amap_key

# 启动后端
python backend/api.py

# 打开前端
# 浏览器打开 frontend/index.html
```

## 项目结构

```
├── backend/              # FastAPI 后端服务
│   ├── api.py            # API 路由
│   ├── agent_runner.py   # Agent 执行器
│   └── auth.py           # 认证
├── frontend/             # Web 前端
│   ├── index.html        # 主页面
│   ├── app.js            # 应用逻辑
│   ├── map.js            # 地图组件
│   └── style.css         # 样式
├── src/                  # 核心逻辑
│   ├── agents/           # 专业 Agent
│   │   ├── destination.py  # 目的地规划
│   │   ├── flight.py       # 航班查询
│   │   ├── hotel.py        # 酒店推荐
│   │   ├── dining.py       # 餐饮推荐
│   │   ├── budget.py       # 预算管理
│   │   └── itinerary.py    # 行程编排
│   ├── tools/            # 工具集
│   │   ├── amap.py         # 高德地图 API
│   │   ├── baidu_search.py # 百度搜索
│   │   ├── llm.py          # LLM 调用
│   │   └── cache.py        # 缓存
│   └── graph.py          # 图状态编排
└── pyproject.toml         # 项目配置
```
