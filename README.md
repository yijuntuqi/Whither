<div align="center">
  <img src="backend/web/assets/whither-logo.svg" width="120" alt="Whither Logo">
  <h1>Whither · 何之</h1>
  <p><strong>问一句何之，答一段旅程</strong> —— 懂旅行的 AI 规划助手</p>
  <p>
    <a href="#在线体验">在线体验</a> ·
    <a href="#功能特性">功能特性</a> ·
    <a href="#技术栈">技术栈</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#docker-部署">Docker</a> ·
    <a href="#支持-whither">支持</a>
  </p>
</div>

---

## 在线体验

🚀 **无需安装，立即使用：<https://whither-production.up.railway.app/>**

告诉 Whither 你想去哪里，它会问几个出行偏好，随后自动完成攻略检索、天气与车次查询，并生成一份可以下载带走的 PDF 旅行手册。

## 功能特性

- **🧭 智能行程规划**：覆盖国内 107 城，自动生成逐日行程、景点、餐饮与住宿安排
- **📚 RAG 攻略知识库**：马蜂窝自由行攻略本地向量检索（bge-m3，4288 条 1024 维向量）
- **🌤️ 官方天气预报**：高德官方气象数据，逐日天气、气温区间、风力风向
- **🚄 12306 真实车次**：官方接口直连，跨城火车的车次、余票、票价真实可查，拒绝编造
- **🗺️ 景点间交通**：高德地图查询真实公交、地铁、步行路线
- **🏨 真实酒店推荐**：基于地图 POI 的真实在营酒店名称与地址
- **📄 PDF 旅行手册**：一键生成杂志级 A4 手册（逐日时间线、预算饼图、打包清单）
- **🎯 偏好询问**：首次规划主动询问 7 项偏好（节奏 / 预算 / 酒店 / 餐饮 / 交通 / 首站 / 特殊需求）
- **🔑 自带模型 Key**：使用你自己的大模型 API 额度，Key 只保存在浏览器本地

## 技术栈

| 层级 | 技术 |
|---|---|
| Agent 框架 | LangChain 1.x + LangGraph |
| LLM | OpenAI 协议模型（用户自带 Key）/ Ollama 本地模型 |
| Embedding | Ollama bge-m3 / DashScope 向量模型（1024 维） |
| RAG 知识库 | SQLite + 向量检索（cosine 相似度） |
| 联网搜索 | Tavily |
| 火车票 | 12306 官方接口直连 |
| 天气 | 高德官方气象（MCP） |
| 景点交通 / 酒店 | 高德地图 MCP |
| Web 服务 | FastAPI + SSE 流式输出 |
| 前端 | 原生 HTML / CSS / JS（无构建依赖） |
| PDF | Playwright + Chromium（A4） |
| 会话持久化 | SQLite 检查点 |

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/yijuntuqi/Whither.git
cd Whither

# 创建虚拟环境（Python 3.11+）
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 安装依赖与 Chromium
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，按需填入：

```ini
# LLM（本地开发可用 Ollama；线上由用户在页面填写自己的 Key）
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.example.com/v1
LLM_MODEL=gpt-4o-mini

# Embedding：本地用 Ollama bge-m3
EMBEDDING_PROVIDER=ollama
EMBED_MODEL=bge-m3

# 外部工具
TAVILY_API_KEY=tvly-xxx
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=YOUR_KEY
```

### 3. 启动服务

```bash
# 本地 Embedding 模式需先启动 Ollama
ollama serve

# 启动后端
python -m uvicorn backend.app.main:app --port 8000
```

浏览器打开 <http://localhost:8000> 即可使用。

### 4. 开始规划

1. 输入目的地（如“成都 3 日游”）
2. 回答 Whither 的 7 项出行偏好
3. 自动生成完整逐日行程
4. 说“导出 PDF”，点击下载按钮保存旅行手册

也可以运行 `python backend/run_agent.py` 在命令行中与 Whither 交互。

## Docker 部署

镜像已发布到 Docker Hub，在任意支持 Docker 的服务器上执行以下两步即可部署。

### 1. 准备配置

在部署目录创建 `.env`（大模型 Key 由最终用户在页面填写，服务端只需配置知识库检索与工具）：

```ini
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx
TAVILY_API_KEY=tvly-xxx
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=YOUR_KEY
```

### 2. 拉取镜像并运行

```bash
docker pull yijuntuqixx/whither:latest

docker run -d --name whither \
  -p 8080:8000 --env-file .env \
  --restart unless-stopped \
  yijuntuqixx/whither:latest
```

浏览器访问 `http://服务器IP:8080` 即可。

> `-p 8080:8000` 表示「服务器 8080 端口 → 容器内 8000 端口」；
> 容器内服务固定监听 8000，左边可改成服务器上任一未占用端口（如 `-p 9000:8000` 则访问 9000）。

常用运维命令：

```bash
docker logs -f whither     # 查看日志
docker stop whither        # 停止
docker rm whither          # 删除容器
```

## 项目结构

```
whither/
├── backend/
│   ├── app/
│   │   ├── agent/        # Agent 核心：graph / tools / 高德 MCP
│   │   ├── pdf/          # PDF 模板与生成器（Playwright）
│   │   ├── rag/          # 马蜂窝攻略向量检索
│   │   ├── trains/       # 12306 官方接口直连
│   │   └── main.py       # FastAPI + SSE 入口
│   ├── web/              # 聊天页面（原生 HTML/CSS/JS）
│   │   └── assets/       # 背景视频、Logo
│   ├── data/             # 运行时缓存（不入库）
│   └── run_agent.py      # 命令行交互入口
├── data/
│   └── rag.sqlite        # 知识库（4288 条向量）
├── scripts/              # 爬虫 / OCR / 向量化脚本
├── tests/                # 单元测试
├── assets/               # 赞赏码等 README 资源
├── Dockerfile
├── railway.toml
├── .env.example
├── requirements.txt
└── README.md
```

## 支持 Whither

如果 Whither 为你的旅途带来了便利，欢迎请作者喝杯奶茶 🧋

<p align="center">
  <img src="assets/wechat-pay.png" width="270" alt="微信赞赏码">
  <img src="assets/alipay.png" width="270" alt="支付宝付款码">
</p>

## License

MIT
