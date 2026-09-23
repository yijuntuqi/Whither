"""
Whither 最小 Web Demo（P1-2）
- GET  /      单页对话界面（backend/web/index.html，无 React/Vite/Tailwind）
- POST /chat  SSE 流式返回 Agent 输出（token + 工具调用提示）

启动（项目根目录）:
  E:\\conda_envs\\langchain\\python.exe -m uvicorn backend.app.main:app --port 8000
"""
import hashlib
import json as _json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessageChunk
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.app.agent.graph import build_agent, build_model

# backend/web/index.html（本文件在 backend/app/main.py）
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
# Agent 生成的 PDF 输出目录（项目根 data/exports）
EXPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    # 用户自己的 LLM API Key（必填，本站不提供公共额度）
    api_keys: dict[str, str] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 本站不提供公共模型额度：不构建站方默认 Agent。
    # 所有对话必须携带用户自己的 LLM Key，按 key 哈希缓存对应 Agent。
    app.state.agent_cache: dict[str, object] = {}
    yield


app = FastAPI(title="Whither", lifespan=lifespan)
_SSE_APP = app  # 供 _resolve_agent 访问 app.state

# ===== 跨域 CORS（Netlify 前端 → Railway 后端分离部署必需）=====
# 环境变量 CORS_ORIGINS 可填逗号分隔的白名单，如 https://whither.netlify.app
# 未设置时放行所有来源（本接口不使用 Cookie，线程ID在请求体中传递，安全可接受）
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
if _cors_env:
    _allow_origins = [o.strip().rstrip("/") for o in _cors_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    _allow_origins = ["*"]
    _allow_credentials = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    # no-cache：浏览器每次必须带 etag 向服务器校验，防止改版后用户仍运行缓存的旧 JS
    # （曾因此导致 Markdown 渲染修复"看起来没生效"）；文件未变时服务器回 304，不浪费流量
    return FileResponse(
        WEB_DIR / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


# 静态资源：logo 等（web/assets 目录，与 Netlify 部署目录结构一致）
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")


# PDF 下载：暴露 data/exports/（StaticFiles 内置目录穿越防护，不允许越界访问）
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


@app.get("/health/upstream")
async def health_upstream():
    """从当前容器（海外）探测 12306 官方接口连通性：用于确认车次工具可用。"""
    import httpx
    result = {"kyfw_12306": {"ok": False}}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            r = await c.get(
                "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js",
                headers={"User-Agent": "Mozilla/5.0"})
            result["kyfw_12306"] = {
                "ok": r.status_code == 200 and "station_names" in r.text,
                "http_status": r.status_code,
                "bytes": len(r.content),
            }
    except Exception as e:
        result["kyfw_12306"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return result


@app.get("/download/{filename}")
async def download_pdf(filename: str):
    """网页端直接下载 PDF：/download/成都2日游_20260921_120000.pdf"""
    # 安全：只允许 .pdf 文件，且不允许路径穿越
    if not filename.endswith(".pdf") or "/" in filename or "\\" in filename or ".." in filename:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="无效的文件名")
    path = EXPORTS_DIR / filename
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=filename,
    )


def _key_overrides(api_keys: dict[str, str]) -> dict | None:
    """把前端传来的 api_keys 映射成 build_model 的 overrides；只有填了 LLM Key 才算用户自带。"""
    llm_key = (api_keys.get("llm_api_key") or "").strip()
    if not llm_key:
        return None
    return {
        "llm_provider": "openai",
        "api_key": llm_key,
        "api_base": (api_keys.get("llm_api_base") or "").strip()
                    or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        "llm_model": (api_keys.get("llm_model") or "").strip()
                     or os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


async def _resolve_agent(api_keys: dict[str, str] | None):
    """必须自带 LLM Key：否则直接 400。合法 Key 按哈希缓存对应 Agent。"""
    from fastapi import HTTPException
    overrides = _key_overrides(api_keys)
    if overrides is None:
        raise HTTPException(
            status_code=400,
            detail="请先点击右上角 🔑，填写你自己的模型 API Key 后再开始对话（本站不提供公共额度）",
        )
    h = hashlib.sha256(_json.dumps(overrides, sort_keys=True).encode()).hexdigest()[:16]
    cache = _SSE_APP.state.agent_cache
    if h not in cache:
        cache[h] = await build_agent(model=build_model(overrides))
    return cache[h]


@app.post("/chat")
async def chat(req: ChatRequest):
    agent = await _resolve_agent(req.api_keys)
    thread_id = req.thread_id or uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 80}

    async def event_gen():
        logger.info(f"[chat] 开始 thread={thread_id} msg={req.message[:40]!r}")
        yield {"event": "meta", "data": thread_id}
        inputs = {"messages": [{"role": "user", "content": req.message}]}
        try:
            async for mode, data in agent.astream(
                inputs,
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    chunk, _metadata = data
                    # 只转发模型的文本增量（工具消息是整条 ToolMessage，不在此列）
                    if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str) \
                            and chunk.content:
                        yield {"event": "token", "data": chunk.content}
                elif mode == "updates":
                    for _node, node_state in data.items():
                        if not isinstance(node_state, dict):
                            continue
                        for msg in node_state.get("messages", []):
                            for tc in getattr(msg, "tool_calls", None) or []:
                                logger.info(f"[chat] 工具 {tc.get('name')}")
                                yield {"event": "tool", "data": tc.get("name", "")}
        except Exception as e:
            logger.exception(f"[chat] 异常 thread={thread_id}")
            yield {"event": "error", "data": f"{type(e).__name__}: {e}"}
        logger.info(f"[chat] 结束 thread={thread_id}")
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_gen())
