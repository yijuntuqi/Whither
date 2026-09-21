<div align="center">
  <img src="whither-logo.svg" width="120" alt="Whither Logo">
  <h1>Whither · 何之</h1>
  <p><strong>智能旅行规划助手</strong> — 基于 LangChain + RAG 的全栈旅行规划 Agent</p>
  <p>
    <a href="#功能特性">功能特性</a> ·
    <a href="#技术栈">技术栈</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#部署">部署</a> ·
    <a href="#项目结构">项目结构</a>
  </p>
</div>

---

## 功能特性

- **🧭 智能行程规划**：覆盖国内 107 城，自动生成逐日行程、景点、餐饮、住宿
- **📚 RAG 知识库**：基于马蜂窝自由行攻略的本地向量检索（bge-m3 1024 维，4288 条向量）
- **🌤️ 实时天气**：联网查询每日天气预报，写入行程手册
- **🚄 12306 车次**：跨城交通自动查询真实车次、票价、座位类型
- **🗺️ 景点间交通**：高德 MCP 查询真实公交/地铁路线，避免编造
- **🏨 酒店推荐**：结合预算和位置偏好推荐住宿
- **📄 PDF 手册**：一键生成杂志级 A4 行程手册（含预算饼图、打包清单）
- **🎯 偏好询问**：首次规划主动询问 7 项偏好（节奏/预算/酒店/餐饮/交通/首站/特殊需求）
- **⏱️ 智能时间轴**：首站先酒店时去掉绝对时间，只显景点间隔

## 技术栈

| 层级 | 技术 |
|---|---|
| Agent 框架 | LangChain 1.x + LangGraph |
| LLM | OpenAI 协议（chatanywhere）/ Ollama (qwen2.5:7b) |
| Embedding | Ollama bge-m3 / DashScope text-embedding-v2（1024 维） |
| RAG | SQLite + 内存矩阵缓存（cosine 相似度） |
| 联网搜索 | Tavily |
| 火车票 | 12306 MCP (npx) |
| 景点交通 | 高德地图 MCP |
| Web 服务 | FastAPI + SSE 流式输出 |
| 前端 | 原生 HTML/CSS/JS（无构建依赖） |
| PDF | Playwright + Chromium（A4） |
| 持久化 | SQLite 检查点（跨会话恢复） |

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/yijuntuqi/Whither.git
cd Whither

# 创建虚拟环境（Python 3.11+）
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入以下关键值：

```ini
# LLM（二选一）
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.chatanywhere.tech/v1

# Embedding（开发用 ollama，部署用 dashscope）
EMBEDDING_PROVIDER=ollama
EMBED_MODEL=bge-m3

# 外部工具
TAVILY_API_KEY=tvly-xxx
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=YOUR_KEY
```

### 3. 启动服务

```bash
# 启动 Ollama（开发模式 embedding）
ollama serve

# 启动后端
python -m uvicorn backend.app.main:app --port 8000
```

浏览器打开 `http://localhost:8000` 即可使用。

### 4. 使用

1. 在输入框输入目的地（如"成都3日游"）
2. Agent 会先询问 7 项偏好（也可点"设置出行偏好"提前填写）
3. 回答偏好后自动生成行程并导出 PDF
4. 点击 PDF 卡片上的"下载 PDF"按钮保存手册

## 部署

### 后端（Railway）

仓库已包含 `Dockerfile` 和 `railway.toml`，Railway 会自动构建：

1. 在 [Railway](https://railway.app) 创建项目，连接 GitHub 仓库
2. 设置环境变量（见 `.env.example`）：
   - `EMBEDDING_PROVIDER=dashscope` + `DASHSCOPE_API_KEY`
   - `LLM_PROVIDER=openai` + `OPENAI_API_KEY` + `OPENAI_API_BASE`
   - `TAVILY_API_KEY` + `AMAP_MCP_URL`
3. 部署完成后获得 Railway 域名

### 前端（Netlify）

前端是单文件 `backend/web/index.html`，可直接部署到 Netlify：

1. 在 [Netlify](https://netlify.com) 拖入 `index.html`
2. 或将仓库部署，构建目录设为 `backend/web`
3. 部署后修改 `index.html` 中的 API 地址为 Railway 后端域名

### Docker 本地构建

```bash
# 构建镜像
docker build -t whither:latest .

# 运行容器
docker run -p 8000:8000 --env-file .env whither:latest
```

## 项目结构

```
whither/
├── backend/
│   ├── app/
│   │   ├── agent/          # Agent 核心（graph/tools/MCP）
│   │   │   ├── graph.py     # Agent 构建 + SYSTEM_PROMPT
│   │   │   ├── tools.py     # RAG/搜索/预算/打包/PDF 工具
│   │   │   ├── mcp_12306.py # 12306 MCP 接入
│   │   │   └── mcp_amap.py  # 高德 MCP 接入
│   │   ├── pdf/             # PDF 生成
│   │   │   ├── template.py  # HTML 模板（杂志级排版）
│   │   │   └── generator.py # Playwright 渲染 PDF
│   │   ├── rag/             # 向量检索
│   │   │   └── retriever.py # SQLite 向量检索器
│   │   └── main.py          # FastAPI 入口
│   ├── web/
│   │   └── index.html       # 前端单页应用
│   └── data/                # 运行时数据（SQLite/导出）
├── data/
│   └── rag.sqlite           # 知识库向量库（4288 条）
├── scripts/                 # 爬虫/OCR/向量化脚本
├── Dockerfile               # Docker 构建
├── railway.toml             # Railway 部署配置
├── .env.example             # 环境变量模板
├── requirements.txt         # Python 依赖
├── whither-logo.svg         # Logo
└── README.md
```

## 环境变量说明

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `openai` | LLM 提供商：`ollama` / `openai` |
| `OPENAI_API_KEY` | — | OpenAI 协议 API Key |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | API 地址（含代理） |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama 模型 |
| `EMBEDDING_PROVIDER` | `ollama` | Embedding：`ollama` / `dashscope` |
| `DASHSCOPE_API_KEY` | — | 阿里云 DashScope Key |
| `DASHSCOPE_EMBED_MODEL` | `text-embedding-v2` | DashScope 模型 |
| `TAVILY_API_KEY` | — | Tavily 联网搜索 Key |
| `AMAP_MCP_URL` | — | 高德 MCP URL（留空则降级） |
| `AGENT_CHECKPOINT_DB` | `agent_checkpoints.db` | 会话持久化 DB |

## 开发说明

- **Embedding 切换**：开发用 Ollama（本地 bge-m3），部署用 DashScope（text-embedding-v2，1024 维兼容）
- **MCP 降级**：12306/高德 MCP 不可用时自动降级，不影响核心功能
- **首站逻辑**：`first_stop_hotel=true` 时 PDF 去掉绝对时间，只显景点间隔

## License

MIT
