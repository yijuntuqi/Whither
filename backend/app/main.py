"""
Whither 最小 Web Demo（P1-2）
- GET  /      单页对话界面（backend/web/index.html，无 React/Vite/Tailwind）
- POST /chat  SSE 流式返回 Agent 输出（token + 工具调用提示）

启动（项目根目录）:
  E:\\conda_envs\\langchain\\python.exe -m uvicorn backend.app.main:app --port 8000
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessageChunk
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.app.agent.graph import build_agent

# backend/web/index.html（本文件在 backend/app/main.py）
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
# Agent 生成的 PDF 输出目录（项目根 data/exports）
EXPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Agent（含 MCP 工具拉起）只构建一次，thread_id 区分会话
    app.state.agent = await build_agent()
    yield


app = FastAPI(title="Whither", lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


# PDF 下载：暴露 data/exports/（StaticFiles 内置目录穿越防护，不允许越界访问）
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


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


@app.post("/chat")
async def chat(req: ChatRequest):
    agent = app.state.agent
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
