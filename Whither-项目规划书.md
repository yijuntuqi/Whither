# Whither · 何之 — 项目规划书（商业计划书）

| 项目        | 内容                                                |
| --------- | ------------------------------------------------- |
| 项目名称      | Whither（中文名：何之）                                   |
| Slogan    | 问一句何之，答一段旅程 · Ask whither, get a journey.         |
| 一句话定位     | 查真实车票、懂你偏好、交付精美行程手册的 AI 旅行规划 Agent                |
| 项目形态      | Web 端对话式应用 · 开源（GitHub）· BYOK（用户自带模型 Key）         |
| 技术栈       | LangChain 1.x + LangGraph + MCP + FastAPI + React |
| 文档版本      | v3.0（2026-09-17）                                  |
| GitHub 仓库 | <git@github.com>:yijuntuqi/Whither.git            |

***

## 一、项目概述

Whither（何之）是一个基于 LangChain 1.x 构建的对话式旅行规划 Agent。

"何之"出自古文，意为"去哪里"。用户只需一句话（如"周六早上从北京出发去天津，预算500，带娃"），Agent 自动完成：

```
理解需求 → 查询真实火车票(12306) → 搜索马蜂窝攻略/天气/景点
       → RAG检索本地知识库 → 结合偏好记忆
       → 生成逐日行程 → 输出精美 HTML 行程手册 → 转 PDF 下载
```

**核心设计原则**：不与内容平台拼"攻略数量"，拼"**决策质量**"和"**交付物美感**"。

***

## 二、市场背景与痛点

### 2.1 现有方案的不足

| 类型       | 代表产品          | 不足                                                |
| -------- | ------------- | ------------------------------------------------- |
| 内容平台     | 马蜂窝、小红书、携程攻略  | 信息碎片化，用户要自己看十几篇攻略拼行程；软文广告多                        |
| 通用 AI 助手 | 豆包、元宝、ChatGPT | ① 查不到实时余票/票价 ② 不记住用户长期偏好 ③ 输出是一大段文字，没有可执行、可打印的交付物 |
| 行程工具 App | 各类行程助手        | 填表式交互，模板化，不智能                                     |

### 2.2 用户真实需求

> 用户需要的不是"看攻略"，而是"**帮我定好方案**"。

- 周末想去某地 → 直接告诉我坐几点的车、去哪玩、花多少钱
- 结果要**可执行**（有真实车次）、**可调整**（改预算自动重排）、**可带走**（精美 PDF 手册）

***

## 三、产品定位与差异化亮点

### 3.1 对比竞品

| 能力            | 马蜂窝      | 豆包/元宝 | Whither                             |
| ------------- | -------- | ----- | ----------------------------------- |
| 真实火车票余票查询     | ❌        | ❌     | ✅（12306 MCP）                        |
| 马蜂窝攻略数据检索     | ✅（人工搜索）  | 部分    | ✅（爬虫+RAG自动检索）                       |
| 逐日结构化行程       | ❌（UGC长文） | 文字堆砌  | ✅（时间线卡片）                            |
| 精美 PDF 行程手册导出 | ❌        | ❌     | ✅（LLM+设计Skill生成HTML→Playwright转PDF） |
| 改预算/日期自动重排    | ❌        | 部分可对话 | ✅                                   |
| 长期偏好记忆        | ❌        | 部分    | ✅（LangGraph Store）                  |
| 服务端模型成本       | —        | 平台承担  | ✅ 零成本（BYOK）                         |
| 开源可定制         | ❌        | ❌     | ✅                                   |

### 3.2 九大亮点

1. **闭环规划**：一次对话完成 目的地 → 车票 → 攻略检索 → 逐日行程
2. **真实数据**：12306 MCP 查真实余票票价（核心壁垒）
3. **马蜂窝攻略引擎**：爬虫+RAG 知识库，自动检索马蜂窝优质游记/景点/自由行数据，不靠用户手动搜
4. **双路攻略获取**：离线 RAG 知识库（PDF + 爬虫数据向量化） + 在线实时搜索马蜂窝（Agent 工具）
5. **交付物思维**：后端 LLM + 设计 Skill 生成精美 HTML 行程手册 → Playwright 转 PDF（杂志级排版）
6. **多轮可调**：换日期、改预算、换交通方式，Agent 只重排受影响部分
7. **偏好记忆**：长期记忆记住"不吃辣 / 亲子游 / 穷游"
8. **BYOK 零成本**：用户自带 API Key，服务端零模型开支
9. **设计驱动**：impeccable + taste-skill + ui-ux-pro-max 三大设计 Skill 保证专业级审美

***

## 四、马蜂窝爬虫与 RAG 知识库（核心模块）

### 4.1 数据来源

| 来源            | 获取方式                             | 内容              |
| ------------- | -------------------------------- | --------------- |
| 用户提供的城市攻略 PDF | 手动放入 `data/pdfs/`                | 国内有名城市的旅行攻略     |
| 马蜂窝游记/景点/自由行  | 爬虫爬取到 `data/crawled/`            | 游记正文、景点信息、自由行方案 |
| 马蜂窝实时搜索       | Agent 工具（MCP fetch / Playwright） | 实时获取最新攻略        |

> **爬取优先级（2026-09-20 修订）**：**景点结构化数据（评分/地址/开放时间/建议时长）> mafengwo_free 自由行**（现有 4487 chunk 仅标题+亮点，信息量薄）。下一批爬虫应优先补景点接口（Cookie + \_sn），自由行方案仅作行程模板参考。

### 4.2 马蜂窝爬虫方案

**参考文章**：<https://juejin.cn/post/7322662132091568180>

#### 反爬机制与对策

| 反爬类型      | 机制                              | 对策                          |
| --------- | ------------------------------- | --------------------------- |
| Cookie 校验 | 521 三次跳转，`__jsl_clearance_s` 生成 | Playwright 无头浏览器渲染（自动执行 JS） |
| \_sn 参数摘要 | MD5 哈希拼接参数                      | 已有算法，直接实现                   |

#### 爬虫技术选型

```
方案 A（推荐）：Playwright 渲染
  - 项目已依赖 Playwright（PDF 生成用），复用运行时
  - 无头浏览器自动执行 JS，绕过所有 Cookie 校验
  - 用 XPath/CSS 选择器提取数据
  - 爬取速度慢但稳定，适合知识库构建（一次性+定期更新）

方案 B（备选）：httpx + _sn 算法
  - 轻量，速度快
  - 需手动实现 _sn 生成 + Cookie 处理
  - 适合大批量爬取
```

#### 爬取数据结构

```
data/
├── pdfs/              ← 用户手动放入的城市攻略 PDF
├── crawled/           ← 爬虫爬取的马蜂窝数据
│   ├── destinations.json    # 目的地列表（mddId, 城市名, 省份）
│   ├── scenics/             # 景点数据（按城市分文件）
│   │   ├── beijing.json
│   │   └── ...
│   ├── travels/             # 游记数据（按城市分文件）
│   │   ├── beijing.json
│   │   └── ...
│   └── free_travels/        # 自由行方案（GET接口无校验，最易爬）
│       ├── beijing.json
│       └── ...
└── processed/         ← RAG 处理后的向量化数据
    ├── chunks/               # 切分后的文本块
    └── faiss_index/          # FAISS 向量索引
```

#### 爬虫接口

| 数据   | 接口                                                                 | 方法   | 校验            |
| ---- | ------------------------------------------------------------------ | ---- | ------------- |
| 目的地  | `mafengwo.cn/mdd`                                                  | GET  | Cookie        |
| 城市列表 | `mafengwo.cn/mdd/base/list/pagedata_citylist`                      | POST | Cookie        |
| 景点   | `mafengwo.cn/ajax/router.php`                                      | POST | Cookie + \_sn |
| 游记列表 | `mafengwo.cn/yj/index.php/pagedata`                                | POST | Cookie + \_sn |
| 自由行  | `mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid={id}&page={n}` | GET  | **无校验**       |

### 4.3 RAG 知识库流程

```
PDF 文档 + 爬虫 JSON
    │
    ▼
langchain PDFLoader / JSON 解析 → 统一文本
    │
    ▼
RecursiveCharacterTextSplitter 切分（chunk_size=500, overlap=50）
    │
    ▼
Embedding（Ollama nomic-embed-text / 线上 Embedding）
    │
    ▼
FAISS 向量索引（存 data/processed/faiss_index/）
    │
    ▼
Agent 工具：retriever.invoke(query) → 检索相关攻略片段
```

### 4.4 Agent 攻略工具设计

Agent 配备两个攻略获取工具：

| 工具                    | 类型                     | 用途               |
| --------------------- | ---------------------- | ---------------- |
| `search_travel_guide` | RAG 检索                 | 从本地知识库检索攻略（快，离线） |
| `search_mafengwo`     | MCP fetch / Playwright | 实时搜索马蜂窝网站（慢，最新）  |

Agent 默认用 RAG 检索（快），如果用户问的是知识库未覆盖的城市/主题，自动降级到实时搜索马蜂窝。

***

## 五、核心功能规划

### 5.1 MVP（V1.0） — 核心竞争力

> **定位说明（2026-09-20）**：当前 MVP 为**单机版** —— 向量库与 Checkpointer 均用本地 SQLite，无用户系统；Neon/pgvector 云端化、多用户隔离统一挪至 V1.1。

1. **对话式旅行规划**（LangGraph create\_agent 单 Agent 多工具）
2. **12306 真实数据**：余票/票价查询（MCP）
3. **RAG 攻略检索**：本地知识库检索马蜂窝攻略片段（快、离线）
4. **马蜂窝实时搜索**：知识库未覆盖时自动降级到实时 fetch（慢、最新）
5. **逐日行程结构化输出**（JSON Schema → 前端时间线卡片）
6. **精美 PDF 行程手册导出**（HTML → Playwright 转 PDF，杂志级排版）
7. **预算可视化图表**：交通/住宿/餐饮/门票占比饼图嵌在 PDF 里（竞品没有）
8. **天气感知自动调整**：查询天气预报，雨天自动换室内景点
9. **多城市行程拼接**：支持"北京→西安→成都"自动分配停留天数
10. **打包清单自动生成**：根据目的地气候/活动/天数生成打包建议
11. **BYOK 设置页**：用户自带 API Key
12. **多轮对话**（内存 Checkpointer）

**MVP 工具集**：
| 工具 | 类型 | 用途 |
|------|------|------|
| 12306 MCP | stdio MCP Server | 余票/票价/车次查询 |
| Tavily | HTTP Search API | 天气/开放时间/景区限流信息 |
| search_travel_guide | RAG 检索 | 从本地 SQLite 知识库（bge-m3 1024 维向量）检索攻略 |
| search_mafengwo | MCP fetch | 实时搜索马蜂窝网站 |
| calculate_budget | 本地函数 | 预算核算 + 可视化分类 |
| generate_packing_list | 本地函数 | 天气+活动→打包清单 |
| reschedule_for_weather | 本地函数 | 雨天/高温自动调整行程 |

### 5.2 V1.1 — 用户系统 + 体验增强

#### 用户账号系统（新增）
- **注册/登录**：Neon Managed Better Auth（托管式，开箱即用）
- **JWT Token 鉴权**：前后端分离，请求头携带
- **BYOK API Key 加密存储**：AES-256 加密，后端不落库明文
- **用户隔离**：每个用户独立的对话历史、偏好、行程数据
- **跨设备同步**：登录后自动恢复历史对话和偏好

> **BYOK 现状矛盾记录（2026-09-20）**：当前 MVP 的模型 Key 写死在 `.env`（服务端统一 Key），与 3.1"BYOK 零成本"卖点矛盾。V1.1 落地方案：前端设置页填 Key → 请求头（如 `X-Api-Key`）传给后端 → 后端仅透传给模型厂商、不落库明文；Neon 侧仅存 AES-256 加密副本供跨设备同步。

#### 长期记忆架构（新增）
- **LangGraph Checkpointer（Neon PostgreSQL 持久化）**：
  - per-user thread\_id → 保存完整对话历史
  - 断电/刷新页面不丢失上下文
  - 跨设备登录自动恢复上次对话

- **LangGraph Store（Neon PostgreSQL per-user namespace）**：
  - `"user:{id}:preferences"` → 长期偏好（不吃辣/亲子/穷游）
  - `"user:{id}:past_trips"` → 历史行程记录
  - `"user:{id}:saved_plans"` → 收藏的行程方案

- **共享 RAG 知识库（Neon pgvector）**：
  - 爬取的马蜂窝攻略 → 所有人共用
  - 不需要按用户隔离（知识是公共的）

#### 体验增强功能
1. **节假日/景区限流感知**：自动避开故宫周一闭馆、黄山旺季限流
2. **交通方式智能推荐**：高铁 vs 飞机综合时间/价格做推荐
3. **景点拥挤度提示**：基于游记时间分布，提示最佳游览时段
4. **行程日历导出（iCal）**：生成 `.ics` 文件导入手机日历
5. **爬虫定期更新知识库**：Neon Cron Function 每天增量爬取
6. **RAG 知识库云端化**：pgvector 替代本地 FAISS，所有用户共享

### 5.3 V2.0 — 长期竞争力

1. **多人出行协作**：生成分享链接，朋友投票选景点，合并最终方案
2. **同类型成熟方案推荐**：从马蜂窝自由行数据中找相似方案作参考模板
3. **本地特色美食地图**：游记挖掘，按"本地人常去"vs"游客打卡"分类
4. **行程完成率追踪**：旅行后标记，下次优化偏好记忆
5. **酒店比价 MCP + 地图 MCP**
6. **多 Agent 协作**（Planner Agent + Research Agent + Budget Agent）
7. **移动端适配 + 离线 PDF 缓存**

***

## 六、PDF 行程手册生成方案

```
用户确认行程 → Agent 输出行程 JSON
    │
    ▼
后端 LLM + taste-skill 设计规则 → 生成精美 HTML
    │  · 杂志级排版（逐日时间线、车次信息卡、预算明细表）
    │  · 响应式 CSS + 嵌入字体 + 品牌色系
    ▼
Playwright 无头浏览器 → HTML 渲染 → 导出 PDF
    │  · A4 分页 + 打印优化
    ▼
返回 PDF 给用户下载
```

HTML 模板和项目官网共用一套设计系统，保证品牌一致性。

***

## 七、项目官网

用 3 个设计 Skill 协作打造 Whither 官网（Netlify 部署）：

| 区域   | 内容                               |
| ---- | -------------------------------- |
| Hero | Slogan + 演示（输入"周六北京→天津"→ 展示行程卡片） |
| 功能亮点 | 9 大亮点卡片                          |
| 对比竞品 | 和马蜂窝的对比表                         |
| 在线体验 | 嵌入式对话框                           |
| 开源信息 | GitHub 星标、技术栈、一键部署               |
| FAQ  | BYOK 安全性、数据来源等                   |

Skill 协作：`/impeccable init` → `ui-ux-pro-max 设计系统` → `taste-skill 防套路` → `/impeccable craft` → `/impeccable polish`

***

## 八、技术架构

### 8.1 总体分层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ① 用户界面层 (Frontend)                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  React 18 + Vite + TailwindCSS（Netlify 静态托管）                │    │
│  │  ├── 登录/注册页 (Neon Managed Better Auth)                      │    │
│  │  ├── 对话界面 (SSE 流式)                                         │    │
│  │  ├── 行程时间线卡片                                               │    │
│  │  ├── 预算图表（ECharts）+ iCal 导出                              │    │
│  │  ├── BYOK 设置页（API Key 仅存浏览器 localStorage）               │    │
│  │  └── 官网介绍页                                                   │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                             │ HTTPS + JWT Bearer + SSE                  │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────────┐
│                    ② Agent 服务层 (Backend)                              │
│  ┌──────────────────────────▼──────────────────────────────────────┐    │
│  │  FastAPI + LangGraph（HF Spaces Docker 部署）                    │    │
│  │                                                                  │    │
│  │  LangGraph create_agent（单 Agent 多工具）                        │    │
│  │  ├── 状态：messages + user_preferences + budget + weather        │    │
│  │  ├── 节点：llm_node → tool_node → weather_adjust_node           │    │
│  │  └── Checkpointer: LangGraph PostgresCheckpointer (Neon)        │    │
│  │                                                                  │    │
│  │  工具集                                                          │    │
│  │  ├── 12306 MCP (stdio)       真实余票/票价查询                    │    │
│  │  ├── Tavily Search API       天气/开放时间/限流                    │    │
│  │  ├── search_travel_guide     RAG pgvector 检索                    │    │
│  │  ├── search_mafengwo         MCP fetch 实时爬取                   │    │
│  │  ├── calculate_budget        预算分类计算                         │    │
│  │  ├── generate_packing_list   打包清单生成                         │    │
│  │  ├── reschedule_for_weather  雨天自动调整                         │    │
│  │  └── export_itinerary_pdf    HTML→Playwright→PDF                 │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                              │                                           │
│  ┌───────────────────────────┼──────────────────────────────────────┐   │
│  │                        Agent Memory                               │   │
│  │  ┌─────────────────┐   ┌─────────────────────────┐              │   │
│  │  │ Checkpointer    │   │ LangGraph Store (per-user)│              │   │
│  │  │ per-user thread │   │ "user:{id}:preferences" │              │   │
│  │  │ → 对话历史持久化 │   │ "user:{id}:past_trips"   │              │   │
│  │  └─────────────────┘   │ "user:{id}:saved_plans"  │              │   │
│  │                         └─────────────────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────────────┐
│                     ③ 数据层 (Neon)                                       │
│                              │                                           │
│  ┌───────────────────────────▼──────────────────────────────────────┐   │
│  │  Neon Lakebase Postgres（免费计划 + 自动伸缩到零）                  │   │
│  │                                                                  │   │
│  │  ┌─────────────────────┐  ┌───────────────────────────────────┐  │   │
│  │  │ 共享 RAG 知识库       │  │ 用户私有数据                      │  │   │
│  │  │                     │  │                                   │  │   │
│  │  │ ● pgvector 扩展      │  │ ● users 表（Auth 托管）           │  │   │
│  │  │   向量存储 + ANN 索引 │  │ ● checkpoints 表（对话历史）      │  │   │
│  │  │ ● 所有用户共享       │  │ ● store 表（偏好/行程）            │  │   │
│  │  │ ● 马蜂窝攻略向量化    │  │ ● api_keys 表（AES-256 加密）     │  │   │
│  │  └─────────────────────┘  └───────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│  ┌───────────────────────────▼──────────────────────────────────────┐   │
│  │  Neon S3 兼容对象存储                                               │   │
│  │  ├── whither-data bucket                                           │   │
│  │  │   ├── crawled/        原始爬虫 JSON（马蜂窝攻略/景点/自由行）      │   │
│  │  │   ├── pdfs/          用户上传的城市攻略 PDF                      │   │
│  │  │   ├── embeddings/    向量化前的文本块                            │   │
│  │  │   └── exports/       用户导出的 PDF 行程手册（短期缓存）          │   │
│  │  └── boto3 SDK 访问                                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│  ┌───────────────────────────▼──────────────────────────────────────┐   │
│  │  Neon Managed Better Auth（托管式用户系统）                          │   │
│  │  ├── 注册/登录（邮箱+密码，可扩展微信/Google OAuth）                  │   │
│  │  ├── JWT Token 签发与验证                                            │   │
│  │  ├── Row Level Security（RLS）：用户只能访问自己的数据                │   │
│  │  └── 与 PostgreSQL 无缝集成（auth.uid() 函数）                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────────────┐
│                    ④ 外部服务（工具调用）                                  │
│                              │                                           │
│  ┌─────────────┐  ┌──────────┴──────────┐  ┌────────────────────────┐   │
│  │ 12306 MCP   │  │ Tavily Search API    │  │ 马蜂窝                │   │
│  │ (stdio)     │  │ (天气/限流/开放时间)   │  │ Playwright 爬虫       │   │
│  └─────────────┘  └─────────────────────┘  │ + MCP fetch 实时搜索   │   │
│                                             └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Agent 记忆架构详解

```
用户注册登录（Neon Managed Better Auth）
    │
    ▼
JWT Token → 后端解析出 user_id
    │
    ├── 每次对话 → thread_id = f"user:{user_id}:session:{session_id}"
    │   → LangGraph PostgresCheckpointer 持久化到 Neon
    │   → 完整对话历史、Agent 中间状态、工具调用记录全部保存
    │   → 刷新页面/换设备 → 用 thread_id 恢复上下文
    │
    ├── LangGraph Store（per-user namespace）
    │   → namespace = f"user:{user_id}"
    │   → key = "preferences" → {"budget_level": "frugal", "with_kids": true, "diet": "no_spicy"}
    │   → key = "past_trips" → [{"date": "...", "route": "北京→天津", "rating": 5}]
    │   → key = "saved_plans" → [plan_json, ...]
    │   → Agent 自动读取偏好 → 所有行程生成都基于用户偏好
    │
    └── 共享 RAG 知识库（pgvector，所有人共用）
        → 爬取马蜂窝攻略 → 清洗 → 切分 → Embedding → pgvector.embeddings
        → Agent 检索时带 filters（如只搜"成都"的攻略）
        → 不按用户隔离（知识是公共的，偏好是私有的）
```

### 8.3 Neon 数据库表结构规划

```sql
-- ① 启用 pgvector 扩展（Whither 专用）
CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;

-- ② Whither 用户表（可选，若不用 Neon Managed Auth 则自建）
CREATE TABLE whither_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    api_key_encrypted TEXT,        -- AES-256 加密存储 BYOK
    api_key_iv TEXT,               -- 加密用 IV
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ③ RAG 向量表（共享知识库，所有用户共用）
CREATE TABLE whither_rag_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,     -- 'mafengwo_travel' / 'mafengwo_scenic' / 'pdf' / 'mafengwo_free'
    source_id TEXT,                -- 马蜂窝原始 ID 或 PDF 文件名
    city TEXT,                     -- 方便按城市 filter
    chunk_text TEXT NOT NULL,
    embedding vector(1024),        -- Embedding 维度取决于模型（Ollama nomic-embed-text=768 / openai-embedding-3=1024）
    metadata JSONB,                -- 原文章标题/URL/日期等
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX whither_rag_city_idx ON whither_rag_embeddings (city);
CREATE INDEX whither_rag_embedding_ann ON whither_rag_embeddings
    USING lakebase_ann (embedding vector_cosine_ops)
    WITH (build_mode = 'standard');

-- ④ LangGraph Checkpointer 表（per-user 对话历史）
-- langgraph-checkpoint-postgres 自动创建，首次运行 Agent 时自动初始化

-- ⑤ LangGraph Store 表（per-user 长期偏好）
-- 同样由 langgraph-checkpoint-postgres 自动管理
```

### 8.4 技术栈清单（更新版）

| 层 | 技术 | 说明 |
|---|---|---|
| **Agent 框架** | LangChain 1.x、LangGraph 1.x | 单 Agent 多工具模式 |
| **记忆/存储** | langgraph-checkpoint-postgres | Neon PostgreSQL 持久化对话历史 + Store |
| **RAG** | pgvector (lakebase\_vector) | Neon PostgreSQL 向量检索 |
| **Embedding** | Ollama nomic-embed-text / OpenAI text-embedding-3-small | BYOK，用户自选 |
| **爬虫** | Playwright 无头浏览器 | 复用 PDF 生成的 Chromium |
| **Auth** | Neon Managed Better Auth | 托管式，JWT + RLS |
| **后端** | Python 3.13 + FastAPI + SSE | HF Spaces Docker 部署 |
| **对象存储** | Neon S3 兼容存储 + boto3 | 存原始爬虫数据/PDF/导出文件 |
| **工具协议** | MCP（12306 stdio 内置）、MCP fetch | 工具调用 |
| **前端** | React 18 + Vite + TailwindCSS | Netlify 静态托管 |
| **PDF 生成** | Playwright Python | HTML → PDF |
| **设计 Skill** | impeccable + taste-skill + ui-ux-pro-max | 三大设计 Skill |
| **部署** | GitHub → Netlify（前端）、HF Spaces（后端） | 免费额度足够 |
| **数据库** | Neon Lakebase Postgres | 免费计划 + pgvector 扩展 |
| **可观测** | LangSmith | 调试 Agent 行为 |
| **Neon Skills** | neon + neon-postgres | 已安装于 `.agents/skills/` |

### 8.5 与原方案的关键变化

| 原方案 | 新方案（Neon 化） | 变化原因 |
|---|---|---|
| 本地 FAISS 向量库 | Neon pgvector (lakebase\_ann 索引) | 所有用户共享知识库；持久化；支持 ANN 近似检索 |
| 内存 Checkpointer | PostgresCheckpointer (Neon) | 用户刷新/换设备不丢对话；跨设备同步 |
| 无 Store | LangGraph Store per-user namespace | 长期偏好记忆；行程历史 |
| 无用户系统 | Neon Managed Better Auth + JWT | 多用户隔离；BYOK 安全存储 |
| 原始数据存本地 `data/` | Neon S3 兼容对象存储 | 云端持久化；爬虫数据可定期清理/更新 |
| V1.1 才上 Neon | 从 MVP 就上 Neon 架构 | 架构越早统一越好；pgvector 替代 FAISS |

***

## 九、商业模式

| 阶段     | 模式                | 说明                       |
| ------ | ----------------- | ------------------------ |
| 1 开源增长 | 完全免费 + BYOK + MIT | 攒星标、技术文章、作品集；零运营成本       |
| 2 增值   | Freemium          | 免费：对话+基础PDF；付费：高级模板、定制皮肤 |
| 3 B端   | 白标/私有化            | 旅行社、民宿、自媒体批量行程生成         |

**成本 ≈ ¥0/年**（BYOK + Netlify免费 + HF Spaces免费 + FAISS内存）

***

## 十、仓库结构

```
whither/
├── README.md
├── LICENSE                ← MIT
├── .gitignore
├── .env.example           ← 复制成 .env 后填写密钥
├── .agents/
│   └── skills/
│       ├── neon/          ← Neon 概述 + CLI + Functions + Auth
│       └── neon-postgres/ ← pgvector + Lakebase Search + 连接池
├── scripts/
│   ├── test_neon_connection.py  ← 测试 S3/Data API/Postgres 连接
│   ├── setup_neon_schema.py     ← 创建 pgvector 扩展 + Whither 表
│   └── crawler_mfw_free.py      ← 马蜂窝自由行爬虫（无校验 GET）
├── frontend/              ← React 前端 + 官网（Netlify）
│   ├── src/
│   │   ├── components/    ← 对话框、行程时间线、BYOK设置、PDF下载
│   │   ├── pages/         ← 官网页面 + 登录页
│   │   └── App.jsx
│   └── package.json
├── backend/               ← FastAPI 后端（HF Spaces）
│   ├── app/
│   │   ├── agent/         ← LangGraph Agent、工具、prompt
│   │   ├── auth/          ← JWT 鉴权 + BYOK 加密
│   │   ├── mcp/           ← 12306 MCP 启动与连接
│   │   ├── memory/        ← PostgresCheckpointer + LangGraph Store
│   │   ├── pdf/           ← HTML 模板 + Playwright 转 PDF
│   │   ├── rag/           ← pgvector 向量表 + 检索工具
│   │   ├── crawler/       ← 马蜂窝爬虫（Playwright）
│   │   ├── s3/            ← Neon S3 对象存储读写
│   │   └── main.py        ← FastAPI 入口 + SSE + Auth 中间件
│   ├── Dockerfile         ← HF Spaces（含 Node + Chromium）
│   └── requirements.txt
├── data/                  ← 本地缓存（.gitignore 排除大文件）
│   ├── pdfs/              ← 用户手动放入攻略 PDF
│   ├── crawled/           ← 爬虫数据（生产环境上传 Neon S3）
│   └── processed/         ← 向量化前的文本块
└── docs/                  ← 架构图、规划书
```

***

## 十一、里程碑

| 里程碑 | 交付物 | 验收标准 |
|---|---|---|
| **M0 Neon 基建** | Neon 项目关联 + pgvector 扩展 + Neon S3 bucket + 表结构创建 | SQL 直连成功；`CREATE EXTENSION lakebase_vector` 通过 **⚠️ 本地网络无法直连 Neon Postgres（SSL 超时），S3 已通（bucket: whither），pgvector 延后** |
| **M1 核心链路** | Agent + 12306 + Tavily + 天气调整 + 预算计算 + 打包清单 | 本地跑通"北京→天津"带完整天气适配 **✅ 2026-09-19 完成：12306 MCP 真实车次 + Tavily 天气 + 预算核算 + 打包清单 + itinerary JSON 输出** |
| **M1.5 知识库** | 马蜂窝自由行爬虫（GET无校验接口先行）+ PDF导入 + pgvector索引 + RAG检索 | 能检索到成都/北京的马蜂窝攻略片段 **✅ 2026-09-19 完成：107 城 4651 方案向量化（SQLite + 城市过滤检索），原始数据已备份 Neon S3**（注：当时 129 个 PDF 实际未导入；**2026-09-20 已修复**——CID 乱码修复 + 换 bge-m3 全量重建，现 8776 chunk 全部 1024 维 BLOB、乱码=0，实调 search\_travel\_knowledge 验收通过；pgvector 迁移待 Neon 网络通） |
| **M2 用户系统** | Neon Managed Better Auth 注册登录 + JWT 鉴权 + 用户表 + RLS | 两个不同账号，数据互相隔离；偏好记忆自动生效 |
| **M3 Web 化** | FastAPI SSE + React + BYOK 设置页 + Budget 图表 + iCal 导出 | 浏览器可对话；预算饼图嵌入 PDF；可导出 .ics |
| **M3.5 PDF 交付** | 行程时间线卡片 + HTML模板 + Playwright转PDF | 导出杂志级 PDF；打包清单、预算图表、天气调整全包含 **✅ 2026-09-19 完成：纯 CSS 模板（封面/车次徽章时间线/conic饼图/打包清单）+ export_itinerary_pdf 工具，对话中一句话出 PDF，样例 288KB** |
| **M4 上线** | HF Spaces + Netlify + Neon 生产环境 | 外网可访问；pgvector 共享知识库正常检索 |
| **M5 增强功能** | 拥挤度提示 + 交通推荐 + 限流感知 + 爬虫定时更新（Neon Cron） | Agent 提示"故宫周一闭馆"；每天增量爬取 |
| **M6 增长** | README/GIF/技术文章 | GitHub 星标增长 |

***

## 十二、已安装设计 Skill

| Skill                                                                | 安装位置                                       | 用途                 |
| -------------------------------------------------------------------- | ------------------------------------------ | ------------------ |
| impeccable                                                           | `~/.trae-cn/skills/impeccable/`            | 24命令设计指导+61检测规则    |
| ui-ux-pro-max                                                        | `~/.trae-cn/skills/ui-ux-pro-max/`         | 192行业规则+79风格+192配色 |
| design-taste-frontend                                                | `~/.trae-cn/skills/design-taste-frontend/` | 防AI套路前端，3旋钮        |
| ui-styling / design-system / brand / design / banner-design / slides | `~/.trae-cn/skills/`                       | uipro 附带           |

***

## 十三、风险与对策

| 风险            | 对策                            |
| ------------- | ----------------------------- |
| 12306 接口变动    | 跟进 MCP 社区更新；兜底返回官网链接          |
| 马蜂窝反爬升级       | Playwright 渲染绕过；降级为 Tavily 搜索 |
| BYOK 门槛       | 设置页内置 OpenRouter 免费模型教程       |
| 大模型幻觉         | 车次/票价强制来自工具；景点信息附来源           |
| Key 隐私        | Key 只存浏览器、请求头直传、后端不落库         |
| HF Spaces 冷启动 | 首屏提示加载中                       |

***

## 十四、下一步操作

1. ✅ GitHub 仓库已建：`git@github.com:yijuntuqi/Whither.git`
2. 本地目录改名：`project` → `whither`
3. 用户把城市攻略 PDF 放入 `data/pdfs/`
4. 开始 M1：项目骨架 + LangGraph Agent + 12306 工具
5. 开始 M1.5：马蜂窝爬虫 + PDF导入 + FAISS索引

***

*文档版本 v3.0 · 2026-09-17*
