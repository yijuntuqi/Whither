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
| Embedding | Ollama bge-m3 / DashScope qwen3.7-text-embedding（1024 维） |
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

> 推荐顺序：**先部署 Railway 拿到后端域名，再部署 Netlify，最后在页面右上角 ⚙ 里填入后端域名**。
> 全程使用各平台免费额度即可。

### 第 1 步：后端部署到 Railway

仓库已含 `Dockerfile` 与 `railway.toml`（指定 Dockerfile 构建），启动命令会自动读取 Railway 注入的 `$PORT`，无需手动配置端口。

1. 打开 [Railway](https://railway.app)，用 GitHub 登录 → **New Project → Deploy from repo**，选择本仓库
2. 进入 **Variables** 标签，逐个添加环境变量（见 `.env.example`）：

   | 变量 | 值 |
   |---|---|
   | `EMBEDDING_PROVIDER` | `dashscope` |
   | `DASHSCOPE_API_KEY` | 你的阿里云百炼 Key |
   | `LLM_PROVIDER` | `openai` |
   | `OPENAI_API_KEY` | 你的 API Key |
   | `OPENAI_API_BASE` | 如 `https://api.chatanywhere.tech/v1` |
   | `LLM_MODEL` | 如 `gpt-4o-mini` |
   | `TAVILY_API_KEY` | 你的 Tavily Key |
   | `AMAP_MCP_URL` | `https://mcp.amap.com/mcp?key=你的KEY`（没有可留空降级） |
   | `CORS_ORIGINS` | 可留空（默认放行所有来源）；第 2 步拿到 Netlify 域名后可填它做白名单 |

3. 等待 **Build → Deploy** 完成（首次构建约 5–10 分钟，含 Playwright Chromium）
4. 在 **Settings → Networking → Generate Domain** 生成公网域名，形如 `https://whither-production.up.railway.app`
5. 打开该域名确认页面 200，**复制这个域名**备用

### 第 2 步：前端部署到 Netlify

前端是纯静态目录 `backend/web`（含 `index.html` 和 `assets/`），仓库根目录的 `netlify.toml` 已把发布目录指向它，无需构建命令。

1. 打开 [Netlify](https://app.netlify.com)，用 GitHub 登录 → **Add new site → Import an existing project**，选择本仓库
2. Netlify 自动识别 `netlify.toml`（Publish directory = `backend/web`，Build command 留空）→ **Deploy**
3. 部署完成后获得域名，形如 `https://whither.netlify.app`，打开确认页面与 logo 正常

### 第 3 步：把前端指向 Railway 后端

1. 在 Netlify 站点页面，点右上角 **⚙（后端设置）**
2. 粘贴第 1 步的 Railway 域名（如 `https://whither-production.up.railway.app`）→ **保存**
3. 刷新页面，发条消息验证：出现工具调用提示、流式回复、PDF 卡片即为成功
   - 设置只存在浏览器本地（localStorage），换设备/浏览器需再设一次

### （可选）推送到 Docker Hub

```bash
docker login                       # 按提示输入 Docker Hub 账号密码
docker build -t whither:latest .
docker tag whither:latest <你的Docker用户名>/whither:latest
docker push <你的Docker用户名>/whither:latest
```

### （可选）自定义 Hero 头图

把一张 16:9 旅行风景图命名为 `hero.jpg`，放到 `backend/web/assets/` 目录即可自动显示；不放则使用默认青绿渐变背景（页面已内置兜底，不会出现破图）。

### Docker 本地构建与运行

```bash
# 构建镜像
docker build -t whither:latest .

# 运行容器（本地默认 8000 端口；-e PORT 可改，模拟 Railway）
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
│   │   ├── index.html       # 前端单页应用
│   │   └── assets/          # logo、hero.jpg 等静态资源
│   └── data/                # 运行时数据（SQLite/导出）
├── data/
│   └── rag.sqlite           # 知识库向量库（4288 条）
├── scripts/                 # 爬虫/OCR/向量化脚本
├── Dockerfile               # Docker 构建
├── railway.toml             # Railway 部署配置
├── netlify.toml             # Netlify 部署配置
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
| `DASHSCOPE_EMBED_MODEL` | `qwen3.7-text-embedding` | DashScope 模型 |
| `TAVILY_API_KEY` | — | Tavily 联网搜索 Key |
| `AMAP_MCP_URL` | — | 高德 MCP URL（留空则降级） |
| `CORS_ORIGINS` | 空（`*`） | 跨域白名单，逗号分隔，如 `https://whither.netlify.app` |
| `AGENT_CHECKPOINT_DB` | `agent_checkpoints.db` | 会话持久化 DB |

## 开发说明

- **Embedding 切换**：开发用 Ollama（本地 bge-m3），部署用 DashScope（qwen3.7-text-embedding，1024 维兼容）
- **MCP 降级**：12306/高德 MCP 不可用时自动降级，不影响核心功能
- **首站逻辑**：`first_stop_hotel=true` 时 PDF 去掉绝对时间，只显景点间隔

## License

MIT
