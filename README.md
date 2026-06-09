# Travel Planner

AI 驱动的智能旅行规划助手 — 基于 **LangGraph** 多 Agent 协作架构，提供一站式行程规划服务。

[![Python](https://img.shields.io/badge/python-3.14-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-≥1.1-orange)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 技术栈

| 类别 | 技术 |
|---|---|
| **Agent 框架** | LangGraph（有状态图编排）、LangChain |
| **大模型** | DeepSeek / OpenAI-compatible API |
| **后端** | Python 3.14 + FastAPI + Uvicorn + Pydantic |
| **前端** | Vanilla JS + Leaflet 地图 + Fetch API |
| **数据源** | 高德地图 API（POI / 路线）、百度搜索 API |
| **工具库** | Tenacity（重试）、SlowAPI（限流）、Rich（CLI） |

## 架构

```
用户输入（自然语言）
        │
        ▼
  ┌─────────────┐
  │ Orchestrator │   LangGraph StateGraph
  │    Agent     │   状态机编排多步推理
  └──────┬──────┘
         │
    ┌────┴─────────────────────┐
    │  并行分发子任务            │
    └────┬────┬────┬────┬──────┘
         │    │    │    │
    ┌────┴┐ ┌┴───┐┌┴───┐┌┴───┐┌┴─────┐
    │目的地│ │机票│ │酒店│ │餐饮│ │ 预算 │
    │Agent│ │Agent││Agent││Agent││Agent │
    └──┬──┘ └──┬─┘└──┬─┘└──┬─┘└──┬───┘
       │       │     │     │     │
    ┌──┴───────┴─────┴─────┴─────┴───┐
    │        工具调用层                │
    │  ┌─────────┐ ┌──────────┐      │
    │  │高德地图  │ │ 百度搜索  │      │
    │  │POI/路线  │ │ 实时信息  │      │
    │  └─────────┘ └──────────┘      │
    │  ┌─────────┐ ┌──────────┐      │
    │  │LLM 调用 │ │ 缓存/重试 │      │
    │  └─────────┘ └──────────┘      │
    └────────────────────────────────┘
        │
        ▼
  ┌─────────────┐
  │  Itinerary  │   行程聚合编排 Agent
  │    Agent    │
  └──────┬──────┘
        │
        ▼
  Web UI 展示（前端 + 地图可视化）
```

## 核心特性

### 多 Agent 协作
| Agent | 职责 |
|---|---|
| **Destination Agent** | 目的地推荐、景点分析、最佳旅行时间 |
| **Flight Agent** | 航班查询比价、航线规划 |
| **Hotel Agent** | 酒店推荐、区域分析、价格评估 |
| **Dining Agent** | 餐饮推荐、美食攻略 |
| **Budget Agent** | 预算分配、费用估算、性价比分析 |
| **Itinerary Agent** | 行程编排、路线优化、冲突检测 |

### 图状态编排
- 基于 **LangGraph StateGraph** 构建有向图工作流
- 节点间通过 TypedDict State 传递结构化数据
- 支持条件分支、并行执行、动态重入
- 内置错误恢复与重试机制（Tenacity）

### 数据源
- **高德地图 API**：POI 搜索（景点/餐饮/酒店）、路线规划（驾车/公交/步行）、地理编码
- **百度搜索**：实时旅游攻略、景点评价、天气信息等
- **LLM**：通过 DeepSeek 进行意图识别、信息提取、自然语言生成

### Web 前端
- FastAPI 提供 REST API
- 响应式界面，适配桌面与移动端
- **Leaflet** 地图组件展示地理位置
- 流式响应展示 Agent 推理过程

## 快速开始

### 环境要求
- Python ≥ 3.11
- DeepSeek API Key（或其他 OpenAI 兼容 API）
- 高德地图开发者 Key

### 安装

```bash
git clone https://github.com/kongchenga/travel-planner.git
cd travel-planner
pip install -r requirements.txt
```

### 配置

```bash
# .env 文件（参考 .env.example）
DEEPSEEK_API_KEY=your_deepseek_api_key
AMAP_KEY=your_amap_web_api_key
```

### 启动

```bash
# 启动后端服务
python backend/api.py

# 浏览器打开前端
# 直接打开 frontend/index.html
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/plan` | 提交旅行需求，触发多 Agent 规划 |
| GET | `/api/plan/{id}` | 获取规划结果 |
| GET | `/api/status` | 服务状态 |

## 项目结构

```
├── backend/                # FastAPI 后端服务
│   ├── api.py              # REST API 路由
│   ├── agent_runner.py     # Agent 执行器（Graph 编译与调用）
│   └── auth.py             # API Key 认证
├── frontend/               # Web 前端
│   ├── index.html          # 主页面
│   ├── app.js              # 应用主逻辑
│   ├── map.js              # Leaflet 地图组件
│   ├── ui.js               # UI 交互逻辑
│   ├── net.js              # 网络请求封装
│   ├── state.js            # 前端状态管理
│   └── style.css           # 样式表
├── src/                    # 核心业务逻辑
│   ├── agents/             # 专业 Agent
│   │   ├── destination.py  # 目的地规划 Agent
│   │   ├── flight.py       # 机票查询 Agent
│   │   ├── hotel.py        # 酒店推荐 Agent
│   │   ├── dining.py       # 餐饮推荐 Agent
│   │   ├── budget.py       # 预算管理 Agent
│   │   └── itinerary.py    # 行程编排 Agent
│   ├── tools/              # 工具函数库
│   │   ├── amap.py         # 高德地图 API 封装
│   │   ├── baidu_search.py # 百度搜索 API 封装
│   │   ├── llm.py          # LLM 调用封装
│   │   ├── cache.py        # 缓存层
│   │   ├── retry.py        # Tenacity 重试装饰器
│   │   └── json_output.py  # JSON 输出格式化
│   ├── graph.py            # LangGraph 图定义
│   ├── state.py            # State TypedDict 定义
│   ├── schemas.py          # Pydantic 数据模型
│   └── main.py             # CLI 入口
├── pyproject.toml           # 项目元数据与依赖
├── .env.example             # 环境变量模板
├── check_js2.py             # JavaScript 检查工具
├── test_amap_key.py         # 高德地图 Key 测试
└── test_deepseek.py         # DeepSeek API 测试
```

## 依赖

```txt
langgraph>=1.1.0          # Agent 图编排框架
langchain>=1.2.0          # LLM 抽象层
langchain-openai>=1.1.0   # OpenAI 协议适配
fastapi>=0.115.0          # Web 框架
uvicorn[standard]>=0.30.0 # ASGI 服务器
pydantic>=2.0.0           # 数据验证
requests>=2.31.0          # HTTP 客户端
python-dotenv>=1.0.0      # 环境变量加载
tenacity>=8.2.0           # 重试逻辑
slowapi>=0.1.9            # 速率限制
rich>=13.0.0              # CLI 美化输出
```
