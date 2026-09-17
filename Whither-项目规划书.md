# Whither · 何之 — 项目规划书（商业计划书）

| 项目 | 内容 |
|---|---|
| 项目名称 | Whither（中文名：何之） |
| Slogan | 问一句何之，答一段旅程 · Ask whither, get a journey. |
| 一句话定位 | 查真实车票、懂你偏好、交付精美行程手册的 AI 旅行规划 Agent |
| 项目形态 | Web 端对话式应用 · 开源（GitHub）· BYOK（用户自带模型 Key） |
| 技术栈 | LangChain 1.x + LangGraph + MCP + FastAPI + React |
| 文档版本 | v3.0（2026-09-17） |
| GitHub 仓库 | git@github.com:yijuntuqi/Whither.git |

---

## 一、项目概述

Whither（何之）是一个基于 LangChain 1.x 构建的对话式旅行规划 Agent。

"何之"出自古文，意为"去哪里"。用户只需一句话（如"周六早上从北京出发去天津，预算500，带娃"），Agent 自动完成：

```
理解需求 → 查询真实火车票(12306) → 搜索马蜂窝攻略/天气/景点
       → RAG检索本地知识库 → 结合偏好记忆
       → 生成逐日行程 → 输出精美 HTML 行程手册 → 转 PDF 下载
```

**核心设计原则**：不与内容平台拼"攻略数量"，拼"**决策质量**"和"**交付物美感**"。

---

## 二、市场背景与痛点

### 2.1 现有方案的不足

| 类型 | 代表产品 | 不足 |
|---|---|---|
| 内容平台 | 马蜂窝、小红书、携程攻略 | 信息碎片化，用户要自己看十几篇攻略拼行程；软文广告多 |
| 通用 AI 助手 | 豆包、元宝、ChatGPT | ① 查不到实时余票/票价 ② 不记住用户长期偏好 ③ 输出是一大段文字，没有可执行、可打印的交付物 |
| 行程工具 App | 各类行程助手 | 填表式交互，模板化，不智能 |

### 2.2 用户真实需求

> 用户需要的不是"看攻略"，而是"**帮我定好方案**"。

- 周末想去某地 → 直接告诉我坐几点的车、去哪玩、花多少钱
- 结果要**可执行**（有真实车次）、**可调整**（改预算自动重排）、**可带走**（精美 PDF 手册）

---

## 三、产品定位与差异化亮点

### 3.1 对比竞品

| 能力 | 马蜂窝 | 豆包/元宝 | Whither |
|---|---|---|---|
| 真实火车票余票查询 | ❌ | ❌ | ✅（12306 MCP） |
| 马蜂窝攻略数据检索 | ✅（人工搜索） | 部分 | ✅（爬虫+RAG自动检索） |
| 逐日结构化行程 | ❌（UGC长文） | 文字堆砌 | ✅（时间线卡片） |
| 精美 PDF 行程手册导出 | ❌ | ❌ | ✅（LLM+设计Skill生成HTML→Playwright转PDF） |
| 改预算/日期自动重排 | ❌ | 部分可对话 | ✅ |
| 长期偏好记忆 | ❌ | 部分 | ✅（LangGraph Store） |
| 服务端模型成本 | — | 平台承担 | ✅ 零成本（BYOK） |
| 开源可定制 | ❌ | ❌ | ✅ |

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

---

## 四、马蜂窝爬虫与 RAG 知识库（核心模块）

### 4.1 数据来源

| 来源 | 获取方式 | 内容 |
|---|---|---|
| 用户提供的城市攻略 PDF | 手动放入 `data/pdfs/` | 国内有名城市的旅行攻略 |
| 马蜂窝游记/景点/自由行 | 爬虫爬取到 `data/crawled/` | 游记正文、景点信息、自由行方案 |
| 马蜂窝实时搜索 | Agent 工具（MCP fetch / Playwright） | 实时获取最新攻略 |

### 4.2 马蜂窝爬虫方案

**参考文章**：https://juejin.cn/post/7322662132091568180

#### 反爬机制与对策

| 反爬类型 | 机制 | 对策 |
|---|---|---|
| Cookie 校验 | 521 三次跳转，`__jsl_clearance_s` 生成 | Playwright 无头浏览器渲染（自动执行 JS） |
| _sn 参数摘要 | MD5 哈希拼接参数 | 已有算法，直接实现 |

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

| 数据 | 接口 | 方法 | 校验 |
|---|---|---|---|
| 目的地 | `mafengwo.cn/mdd` | GET | Cookie |
| 城市列表 | `mafengwo.cn/mdd/base/list/pagedata_citylist` | POST | Cookie |
| 景点 | `mafengwo.cn/ajax/router.php` | POST | Cookie + _sn |
| 游记列表 | `mafengwo.cn/yj/index.php/pagedata` | POST | Cookie + _sn |
| 自由行 | `mafengwo.cn/gonglve/ziyouxing/list/list_page?mddid={id}&page={n}` | GET | **无校验** |

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

| 工具 | 类型 | 用途 |
|---|---|---|
| `search_travel_guide` | RAG 检索 | 从本地知识库检索攻略（快，离线） |
| `search_mafengwo` | MCP fetch / Playwright | 实时搜索马蜂窝网站（慢，最新） |

Agent 默认用 RAG 检索（快），如果用户问的是知识库未覆盖的城市/主题，自动降级到实时搜索马蜂窝。

---

## 五、核心功能规划

### 5.1 MVP（V1.0）

1. 对话式旅行规划（LangGraph create_agent 单 Agent 多工具）
2. 工具集：
   - 12306 余票/票价查询（MCP）
   - Tavily 联网搜索（天气、开放时间）
   - RAG 攻略检索（FAISS 知识库）
   - 马蜂窝实时搜索（MCP fetch）
   - 预算核算工具（本地计算）
3. 逐日行程结构化输出（JSON Schema → 前端时间线卡片）
4. 精美 PDF 行程手册导出（LLM + taste-skill 生成 HTML → Playwright 转 PDF）
5. BYOK 设置页
6. 多轮对话（内存 Checkpointer）

### 5.2 V1.1

7. 长期记忆（LangGraph Store）
8. 云端 PostgreSQL（Neon）持久化
9. 爬虫定期更新知识库

### 5.3 V2.0（远期）

10. 酒店比价、地图 MCP
11. 多 Agent 协作
12. 行程分享页、移动端适配

---

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

---

## 七、项目官网

用 3 个设计 Skill 协作打造 Whither 官网（Netlify 部署）：

| 区域 | 内容 |
|---|---|
| Hero | Slogan + 演示（输入"周六北京→天津"→ 展示行程卡片） |
| 功能亮点 | 9 大亮点卡片 |
| 对比竞品 | 和马蜂窝/豆包的对比表 |
| 在线体验 | 嵌入式对话框 |
| 开源信息 | GitHub 星标、技术栈、一键部署 |
| FAQ | BYOK 安全性、数据来源等 |

Skill 协作：`/impeccable init` → `ui-ux-pro-max 设计系统` → `taste-skill 防套路` → `/impeccable craft` → `/impeccable polish`

---

## 八、技术架构

```
┌─────────────────────┐        ┌──────────────────────────────┐
│  前端 React (静态)    │  HTTPS │  后端 FastAPI + LangChain      │
│  Netlify 托管        │ ─────► │  HF Spaces (Docker)           │
│                     │  SSE   │                              │
│  - 对话界面          │        │  - LangGraph create_agent     │
│  - 行程时间线卡片     │        │  - Checkpointer / Store       │
│  - BYOK 设置页       │        │  - init_chat_model (BYOK)     │
│  - PDF 下载          │        │  - Playwright HTML→PDF         │
│  - 官网介绍页        │        │  - FAISS RAG 检索              │
└─────────────────────┘        └──────────┬───────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────┐
              ▼                ▼           ▼                   ▼
        ┌──────────┐   ┌──────────┐  ┌──────────┐      ┌──────────┐
        │ 12306 MCP│   │ Tavily   │  │ FAISS    │      │马蜂窝    │
        │ (内置)   │   │ 搜索 API │  │ 向量库   │      │爬虫/fetch│
        └──────────┘   └──────────┘  └──────────┘      └──────────┘
```

### 技术栈清单

| 层 | 技术 |
|---|---|
| Agent 框架 | LangChain 1.x、LangGraph 1.x |
| 工具协议 | MCP（12306 stdio 内置）、MCP fetch（马蜂窝搜索） |
| 后端 | Python 3.13 + FastAPI + SSE + Playwright |
| RAG | FAISS + langchain-text-splitters + Ollama Embedding |
| 爬虫 | Playwright 无头浏览器（复用 PDF 的 Chromium） |
| 前端 | React 18 + Vite + TailwindCSS |
| PDF 生成 | Playwright Python（HTML→PDF） |
| 设计 Skill | impeccable + taste-skill + ui-ux-pro-max |
| 部署 | GitHub → Netlify（前端）、HF Spaces（后端） |
| 数据库 | Neon 免费云 PostgreSQL（V1.1） |
| 可观测 | LangSmith |

---

## 九、商业模式

| 阶段 | 模式 | 说明 |
|---|---|---|
| 1 开源增长 | 完全免费 + BYOK + MIT | 攒星标、技术文章、作品集；零运营成本 |
| 2 增值 | Freemium | 免费：对话+基础PDF；付费：高级模板、定制皮肤 |
| 3 B端 | 白标/私有化 | 旅行社、民宿、自媒体批量行程生成 |

**成本 ≈ ¥0/年**（BYOK + Netlify免费 + HF Spaces免费 + FAISS内存）

---

## 十、仓库结构

```
whither/
├── README.md
├── LICENSE                ← MIT
├── .gitignore
├── .env.example
├── frontend/              ← React 前端 + 官网（Netlify）
│   ├── src/
│   │   ├── components/    ← 对话框、行程时间线、BYOK设置、PDF下载
│   │   ├── pages/         ← 官网页面
│   │   └── App.jsx
│   └── package.json
├── backend/               ← FastAPI 后端（HF Spaces）
│   ├── app/
│   │   ├── agent/         ← LangGraph Agent、工具、prompt
│   │   ├── mcp/           ← 12306 MCP 启动与连接
│   │   ├── memory/        ← Checkpointer / Store
│   │   ├── pdf/           ← HTML 模板 + Playwright 转 PDF
│   │   ├── rag/           ← FAISS 索引 + 检索工具
│   │   ├── crawler/       ← 马蜂窝爬虫（Playwright）
│   │   └── main.py        ← FastAPI 入口 + SSE
│   ├── Dockerfile         ← HF Spaces（含 Node + Chromium）
│   └── requirements.txt
├── data/                  ← 知识库资料（.gitignore 排除大文件）
│   ├── pdfs/              ← 用户手动放入攻略 PDF
│   ├── crawled/           ← 爬虫数据 JSON
│   └── processed/         ← FAISS 索引
└── docs/                  ← 架构图、规划书
```

---

## 十一、里程碑

| 里程碑 | 交付物 | 验收标准 |
|---|---|---|
| M1 核心链路 | Agent + 12306 + Tavily + 结构化行程 | 本地跑通"北京→天津"完整规划 |
| M1.5 知识库 | 爬虫 + PDF导入 + FAISS索引 + RAG检索 | 能检索到马蜂窝攻略片段 |
| M2 Web 化 | FastAPI SSE + React + BYOK | 浏览器可对话 |
| M3 PDF 交付 | 行程卡片 + HTML模板 + Playwright转PDF | 导出杂志级PDF |
| M3.5 官网 | 设计Skill打造介绍页 | 官网上线 |
| M4 上线 | HF Spaces + Netlify | 外网可访问 |
| M5 增强 | Store偏好记忆 + Neon持久化 | 第二次访问记住偏好 |
| M6 增长 | README/GIF/技术文章 | 星标与用户反馈 |

---

## 十二、已安装设计 Skill

| Skill | 安装位置 | 用途 |
|---|---|---|
| impeccable | `~/.trae-cn/skills/impeccable/` | 24命令设计指导+61检测规则 |
| ui-ux-pro-max | `~/.trae-cn/skills/ui-ux-pro-max/` | 192行业规则+79风格+192配色 |
| design-taste-frontend | `~/.trae-cn/skills/design-taste-frontend/` | 防AI套路前端，3旋钮 |
| ui-styling / design-system / brand / design / banner-design / slides | `~/.trae-cn/skills/` | uipro 附带 |

---

## 十三、风险与对策

| 风险 | 对策 |
|---|---|
| 12306 接口变动 | 跟进 MCP 社区更新；兜底返回官网链接 |
| 马蜂窝反爬升级 | Playwright 渲染绕过；降级为 Tavily 搜索 |
| BYOK 门槛 | 设置页内置 OpenRouter 免费模型教程 |
| 大模型幻觉 | 车次/票价强制来自工具；景点信息附来源 |
| Key 隐私 | Key 只存浏览器、请求头直传、后端不落库 |
| HF Spaces 冷启动 | 首屏提示加载中 |

---

## 十四、下一步操作

1. ✅ GitHub 仓库已建：`git@github.com:yijuntuqi/Whither.git`
2. 本地目录改名：`project` → `whither`
3. 用户把城市攻略 PDF 放入 `data/pdfs/`
4. 开始 M1：项目骨架 + LangGraph Agent + 12306 工具
5. 开始 M1.5：马蜂窝爬虫 + PDF导入 + FAISS索引

---

*文档版本 v3.0 · 2026-09-17*
