# Whither 交接摘要 — 下次 SSD 插回后继续

**生成时间**: 2026-09-22
**最后 Commit**: `e87ee58 fix: rag.sqlite加入git仓库 + Netlify Python版本锁定3.11` → main ✅ 已推 GitHub
**上一个 Commit**: `46bcf4e fix: 部署报错修复 - netlify auto-py/railway apt/dashscope模型`

---

## 已修复的三个部署报错

### ✅ 问题 1：Netlify 前端 — `No matching distribution found for unstructured==0.20.6`
**根因**: `netlify.toml` 里 `command = ""` 被 Netlify 视为"未设置"，触发自动检测 → 发现根目录 `requirements.txt` → 当作 Python 项目跑 pip install → unstructured==0.20.6 不兼容 Netlify 的 Python 3.14
**修复（双保险）**:
1. `netlify.toml` 的 command 改为显式 no-op: `command = "echo 'static site, no build step needed'"` (46bcf4e)
2. 新增 `.python-version` 文件写入 `3.11`，即使触发 Python 检测也用 3.11 而非 3.14 (e87ee58)
**状态**: ✅ 已提交 e87ee58

### ✅ 问题 2：Railway 后端 — `sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|...` 失败
**根因**: Railway 在 US West 节点，清华 apt 源连不上（同理 pip 清华源也连不上）
**修复**: Dockerfile 默认 **不换清华源**，用官方 Debian apt + PyPI。国内本地构建用 `--build-arg USE_TUNA=1` 加速
**注意**: 本地测试时发现清华 apt 源的 trixie Packages 文件被 Ign（临时网络/GFW 干扰？），但之前已经成功构建过（摘要里的冒烟测试），所以本地构建应该还是可以的。如果本地清华 apt 也不行，临时去掉 apt 换源的 sed 命令就行
**状态**: ✅ 已提交 46bcf4e

### ✅ 问题 4：Railway — `COPY data/rag.sqlite` 找不到文件
**根因**: `.gitignore` 第 29/37 行 `data/*.sqlite` 把 rag.sqlite 排除了 → git 没追踪 → Railway clone 仓库时没有此文件 → Dockerfile `COPY` 失败
**修复**: `.gitignore` 添加 `!data/rag.sqlite` 例外规则，然后 `git add -f data/rag.sqlite` 强制加入仓库（55MB，在 GitHub 100MB 限制内）
**状态**: ✅ 已提交 e87ee58

### ✅ 问题 3：DashScope Embedding 模型更新
**用户给的新模型**: `qwen3.7-text-embedding`（默认 1024 维，与 bge-m3 完全兼容）
**用户给的 API Key**: `sk-ws-H.PIPMLYH.oJ0f.MEYCIQDnuIGeWsfWOmcrEiW-q-TcuNy6Y3jArKo_w6G_5mPSDAIhAN-7qnBGYZTNL-Hqn4v0oGcLsBOiOCmUxOvwskaMRtWZ`
**验证结果**: 本地调用 `dashscope.TextEmbedding.call(model="qwen3.7-text-embedding", ...)` → **status=200, dim=1024, OK** ✅
**端到端 RAG 测试**: 城市识别("成都3日游"→"成都") + 向量检索("成都 大熊猫基地 游玩攻略") → 搜到成都熊猫旅拍攻略 ✅
**修复文件**:
- `backend/app/rag/retriever.py`: 默认值 `text-embedding-v2` → `qwen3.7-text-embedding`
- `.env.example`: 同步更新注释行（默认仍是 ollama，部署时切 dashscope）
- `README.md`: 全文替换 `text-embedding-v2` → `qwen3.7-text-embedding`
- `.env`: **写入 API Key**（已被 .gitignore 保护，不会提交）
**状态**: ✅ 已提交 46bcf4e（代码改动）+ .env 已写入（本地 only）

---

## API Key 安全提醒

以下 Key **只在本地 .env 文件里**，绝对没有提交到 git（.gitignore 已覆盖 .env）：
- DashScope: `sk-ws-H.PIPMLYH...`
- 其他已有 Key: ChatAnywhere、LangSmith、高德、Tavily、Neon DB/S3（都在 .env 里）

Railway 部署时：在 Railway 项目的 **Variables** 标签里逐个添加（见 README 部署章节的变量表）。

---

## 下次 Session 需要做的事

### 🔴 必须做（Railway + Netlify 重新部署）

1. **Railway 重新部署**:
   - 打开 Railway Whither 项目 → Deployments → 找到最新的 `46bcf4e` → 点 **Deploy**
   - 这次应该能成功（Dockerfile 默认不换清华源，apt 用官方源）
   - 如果还是失败，打开 Build Logs 看具体报错（可能是 Playwright Chromium 下载超时 → 加镜像源）
   - 部署成功后，**进入 Variables** 标签添加环境变量（当前是 0 Variables！）：
     ```
     EMBEDDING_PROVIDER=dashscope
     DASHSCOPE_API_KEY=sk-ws-H.PIPMLYH.oJ0f.MEYCIQDnuIGeWsfWOmcrEiW-q-TcuNy6Y3jArKo_w6G_5mPSDAIhAN-7qnBGYZTNL-Hqn4v0oGcLsBOiOCmUxOvwskaMRtWZ
     DASHSCOPE_EMBED_MODEL=qwen3.7-text-embedding
     LLM_PROVIDER=openai
     OPENAI_API_KEY=<用户自己的 key>
     OPENAI_API_BASE=https://api.chatanywhere.tech/v1
     TAVILY_API_KEY=<用户自己的 key>
     AMAP_MCP_URL=https://mcp.amap.com/mcp?key=<用户自己的 key>
     CORS_ORIGINS=<Netlify 域名>    ← Netlify 部署后填
     ```
   - 环境变量加完后会自动触发重新部署

2. **Netlify 重新部署**:
   - Netlify 可能已经自动拉取了最新 commit → 检查最新一次部署状态
   - 成功的话直接访问 Netlify 域名验证
   - 失败的话打开 Build Logs 看具体报错

3. **Netlify 前端指向 Railway 后端**:
   - 页面右上角点 ⚙（后端设置）
   - 粘贴 Railway 域名 → 保存
   - 发条消息验证（出现工具调用 + 流式回复 + PDF 卡片 = 成功）

### 🟡 可选做

4. **Docker Hub 推送**: `docker login` → tag → push（README 里有命令）
5. **本地 Docker 重建**: `docker build --build-arg USE_TUNA=1 -t whither:latest .`（清华 apt 源如果还是 Ign 临时去掉 sed 换源）
6. **性能观察**: qwen3.7-text-embedding 比 bge-m3 更大，检索速度可能稍慢，但 1024 维兼容性保证效果不会差

---

## 关键文件清单（部署相关）

| 文件 | 作用 | 上次改动 |
|---|---|---|
| `Dockerfile` | Railway/本地 Docker 构建 | 默认不换清华源，USE_TUNA ARG 控制 |
| `netlify.toml` | Netlify 静态部署 | command 改为显式 echo（禁用自动 Python 检测） |
| `railway.toml` | Railway 强制 Dockerfile 构建 | 之前已修复 |
| `backend/app/main.py` | FastAPI CORS + 静态挂载 | 之前已加 CORS 中间件 |
| `backend/app/rag/retriever.py` | RAG 检索器 | 默认模型 qwen3.7-text-embedding |
| `.env.example` | 环境变量模板 | 注释同步更新 |
| `README.md` | 部署文档 | 全量替换模型名 + 分步部署指南 |
| `.env` | 本地环境变量 | **已写入 DashScope API Key**（gitignore） |

---

## 已验证的事实

- ✅ DashScope `qwen3.7-text-embedding` 真实存在，默认 1024 维
- ✅ 本地调用 DashScope embedding → 200 OK, 1024 维
- ✅ 本地端到端 RAG（DashScope embed + SQLite 检索）→ 成功检索到攻略
- ✅ Railway CORS 中间件 → OPTIONS 预检 200, `access-control-allow-origin: *`
- ✅ Dockerfile 动态 PORT 注入 → `-e PORT=9000` 测试通过
- ✅ 本地 Docker 镜像之前成功构建并冒烟测试（12306+高德 MCP 全部加载）
